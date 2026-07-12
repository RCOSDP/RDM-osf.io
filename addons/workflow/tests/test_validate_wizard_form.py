"""Unit tests for `addons.workflow.scripts.validate_wizard_form`.

Pure pytest, no Django DB — exercises the metadata placeholder filter
parser, schema registry, and placeholder-level validation.
"""
import json
import subprocess
import sys

import pytest

from addons.workflow.scripts.validate_wizard_form import (
    FilterParseError,
    SchemaRegistry,
    parse_metadata_filter,
    parse_metadata_placeholder_args,
    validate_form,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _schema_a() -> dict:
    return {
        'name': 'SchemaA',
        'pages': [
            {
                'id': 'p1',
                'title': 'page 1',
                'questions': [
                    {
                        'qid': 'file-type',
                        'type': 'choose',
                        'options': [
                            {'text': 'dataset'},
                            {'text': 'software'},
                        ],
                    },
                    {'qid': 'title', 'type': 'string'},
                    {'qid': 'contrib', 'type': 'array'},
                ],
            },
        ],
    }


def _schema_duplicate() -> dict:
    return {'name': 'SchemaDup', 'pages': []}


@pytest.fixture
def schema_dir(tmp_path):
    (tmp_path / 'schema-a.json').write_text(json.dumps(_schema_a()))
    (tmp_path / 'schema-dup1.json').write_text(json.dumps(_schema_duplicate()))
    (tmp_path / 'schema-dup2.json').write_text(json.dumps(_schema_duplicate()))
    return tmp_path


@pytest.fixture
def registry(schema_dir):
    return SchemaRegistry(schema_dir)


def _form_with_placeholder(placeholder: str) -> dict:
    return {
        'editorJson': {
            'fields': [
                {
                    'fieldType': 'FormField',
                    'id': 'f1',
                    'name': 'f1',
                    'type': 'multi-line-text',
                    'placeholder': placeholder,
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# parse_metadata_filter / parse_metadata_placeholder_args
# ---------------------------------------------------------------------------

def test_parse_filter_single_eq():
    assert parse_metadata_filter('k=="v"') == [('k', '==', 'v')]


def test_parse_filter_single_neq():
    assert parse_metadata_filter('k!="v"') == [('k', '!=', 'v')]


def test_parse_filter_multi_clause_and():
    assert parse_metadata_filter('a=="x" and b!="y"') == [
        ('a', '==', 'x'),
        ('b', '!=', 'y'),
    ]


def test_parse_filter_quoted_comma_preserved():
    # Split on " and " happens outside quotes — comma inside value is fine.
    assert parse_metadata_filter('k=="a,b"') == [('k', '==', 'a,b')]


def test_parse_filter_unquoted_value_fails():
    with pytest.raises(FilterParseError):
        parse_metadata_filter('k==dataset')


def test_parse_filter_single_eq_fails():
    with pytest.raises(FilterParseError):
        parse_metadata_filter('k="v"')


def test_parse_filter_unknown_op_fails():
    with pytest.raises(FilterParseError):
        parse_metadata_filter('k<>"v"')


def test_parse_filter_or_fails():
    with pytest.raises(FilterParseError):
        parse_metadata_filter('a=="x" or b=="y"')


def test_parse_placeholder_args_duplicate_filter_fails():
    with pytest.raises(FilterParseError):
        parse_metadata_placeholder_args('SchemaA, filter=a=="x", filter=b=="y"')


def test_parse_placeholder_args_multiselect_and_filter():
    name, multi, filters = parse_metadata_placeholder_args(
        'SchemaA, MULTISELECT, filter=k=="v"',
    )
    assert name == 'SchemaA'
    assert multi is True
    assert filters == [('k', '==', 'v')]


# ---------------------------------------------------------------------------
# SchemaRegistry
# ---------------------------------------------------------------------------

def test_registry_resolves_known_schema(registry):
    schema = registry.resolve('SchemaA')
    assert schema['name'] == 'SchemaA'


def test_registry_missing_schema_raises(registry):
    with pytest.raises(LookupError):
        registry.resolve('Nope')


def test_registry_ambiguous_schema_raises(registry):
    with pytest.raises(LookupError):
        registry.resolve('SchemaDup')


def test_registry_qid_index_top_level(registry):
    schema = registry.resolve('SchemaA')
    idx = registry.qid_index(schema)
    assert set(idx.keys()) == {'file-type', 'title', 'contrib'}
    assert idx['file-type']['type'] == 'choose'


# ---------------------------------------------------------------------------
# validate_form (placeholder-level)
# ---------------------------------------------------------------------------

def _validate(placeholder: str, registry: SchemaRegistry):
    form = _form_with_placeholder(placeholder)
    return validate_form(form, '<test>', schema_registry=registry)


def test_filter_eq_happy_path(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type=="dataset")',
        registry,
    )
    assert errors == []


def test_filter_neq_happy_path(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type!="software")',
        registry,
    )
    assert errors == []


def test_filter_multi_clause_mixed_ops(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type=="dataset" and title!="draft")',
        registry,
    )
    assert errors == []


def test_filter_with_multiselect(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, MULTISELECT, filter=file-type=="dataset")',
        registry,
    )
    assert errors == []


def test_filter_value_with_comma(registry):
    # title is a string qid — no option value check applies.
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=title=="a,b")',
        registry,
    )
    assert errors == []


def test_unknown_qid(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=bogus=="x")',
        registry,
    )
    assert any("qid 'bogus' not found" in e for e in errors)


def test_bad_option_value_eq(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type=="nope")',
        registry,
    )
    assert any("value 'nope' not in options" in e for e in errors)


def test_bad_option_value_neq(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type!="nope")',
        registry,
    )
    assert any("value 'nope' not in options" in e for e in errors)


def test_unsupported_type_filter(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=contrib=="x")',
        registry,
    )
    assert any('is not supported' in e for e in errors)


def test_duplicate_filter(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=a=="x", filter=b=="y")',
        registry,
    )
    assert any("duplicate 'filter='" in e for e in errors)


def test_unquoted_value(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type==dataset)',
        registry,
    )
    assert any('invalid filter clause' in e for e in errors)


def test_single_eq_operator(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type="dataset")',
        registry,
    )
    assert any('invalid filter clause' in e for e in errors)


def test_unknown_operator(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type<>"dataset")',
        registry,
    )
    assert any('invalid filter clause' in e for e in errors)


def test_or_connector_rejected(registry):
    errors, _ = _validate(
        '_FILE_METADATA(SchemaA, filter=file-type=="dataset" or file-type=="software")',
        registry,
    )
    assert any('invalid filter clause' in e for e in errors)


def test_schema_not_found(registry):
    errors, _ = _validate(
        '_FILE_METADATA(Nope, filter=file-type=="dataset")',
        registry,
    )
    assert any("schema 'Nope' not found" in e for e in errors)


def test_schema_ambiguous_even_without_filter(registry):
    errors, _ = _validate('_FILE_METADATA(SchemaDup)', registry)
    assert any('ambiguous' in e for e in errors)


def test_project_metadata_same_rules(registry):
    errors, _ = _validate(
        '_PROJECT_METADATA(SchemaA, filter=file-type=="dataset")',
        registry,
    )
    assert errors == []
    errors, _ = _validate(
        '_PROJECT_METADATA(SchemaA, filter=bogus=="x")',
        registry,
    )
    assert any("qid 'bogus' not found" in e for e in errors)


def test_cli_default_schema_dir(tmp_path):
    """End-to-end: run `python -m` with explicit schema dir and a form."""
    # Build a temporary schema dir with a single schema.
    schema_dir = tmp_path / 'schemas'
    schema_dir.mkdir()
    (schema_dir / 'a.json').write_text(json.dumps(_schema_a()))

    form = _form_with_placeholder(
        '_FILE_METADATA(SchemaA, filter=file-type=="dataset")',
    )
    # Must also contain the _rdmWizard field check — but the validator now
    # tolerates its absence for start-form shape. A minimal form is enough.
    form_path = tmp_path / 'form.json'
    form_path.write_text(json.dumps(form))

    result = subprocess.run(
        [
            sys.executable, '-m', 'addons.workflow.scripts.validate_wizard_form',
            str(form_path), '--schema-dir', str(schema_dir),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
