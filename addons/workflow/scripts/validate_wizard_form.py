"""Validate an RDM Wizard Form JSON against the rdmWizard spec.

Usage:
    python -m addons.workflow.scripts.validate_wizard_form FORM.json [FORM2.json ...]

Exit code 0 if all files are valid, 1 if any errors found.
"""
import json
import sys
from typing import Any, Dict, List, Set, Tuple


# ---------------------------------------------------------------------------
# Visibility expression parser (recursive descent per spec BNF)
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, msg: str, pos: int):
        super().__init__(msg)
        self.pos = pos


class _ExprParser:
    """Parses and validates a visibility expression string.

    Grammar:
        expression  = or_expr
        or_expr     = and_expr ( "||" and_expr )*
        and_expr    = not_expr ( "&&" not_expr )*
        not_expr    = "!" not_expr | compare
        compare     = primary ( ( "==" | "!=" ) primary )?
        primary     = "(" expression ")"
                    | "true"
                    | "false"
                    | string_literal
                    | field_ref

        string_literal = "'" [^']* "'"
        field_ref      = [^&|!=()' \\t]+
    """

    STOP_CHARS = frozenset("&|!=()' \t")

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.field_refs: List[str] = []

    def parse(self) -> List[str]:
        self._skip_ws()
        if self.pos >= len(self.source):
            raise ParseError('empty expression', 0)
        self._or_expr()
        self._skip_ws()
        if self.pos < len(self.source):
            raise ParseError(
                f'unexpected character {self.source[self.pos]!r} at position {self.pos}',
                self.pos,
            )
        return self.field_refs

    def _skip_ws(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t':
            self.pos += 1

    def _peek(self, s: str) -> bool:
        return self.source[self.pos:self.pos + len(s)] == s

    def _consume(self, s: str):
        if not self._peek(s):
            raise ParseError(f'expected {s!r} at position {self.pos}', self.pos)
        self.pos += len(s)

    def _or_expr(self):
        self._and_expr()
        while self.pos < len(self.source):
            self._skip_ws()
            if self._peek('||'):
                self._consume('||')
                self._skip_ws()
                self._and_expr()
            else:
                break

    def _and_expr(self):
        self._not_expr()
        while self.pos < len(self.source):
            self._skip_ws()
            if self._peek('&&'):
                self._consume('&&')
                self._skip_ws()
                self._not_expr()
            else:
                break

    def _not_expr(self):
        self._skip_ws()
        if self.pos < len(self.source) and self.source[self.pos] == '!':
            # Ensure it's not '!='
            if not self._peek('!='):
                self.pos += 1
                self._skip_ws()
                self._not_expr()
                return
        self._compare()

    def _compare(self):
        self._primary()
        self._skip_ws()
        if self.pos < len(self.source):
            if self._peek('=='):
                self._consume('==')
                self._skip_ws()
                self._primary()
            elif self._peek('!='):
                self._consume('!=')
                self._skip_ws()
                self._primary()

    def _primary(self):
        self._skip_ws()
        if self.pos >= len(self.source):
            raise ParseError('unexpected end of expression', self.pos)

        ch = self.source[self.pos]

        if ch == '(':
            self.pos += 1
            self._skip_ws()
            self._or_expr()
            self._skip_ws()
            self._consume(')')
        elif ch == "'":
            self._string_literal()
        elif self.source[self.pos:self.pos + 4] == 'true' and (
            self.pos + 4 >= len(self.source) or self.source[self.pos + 4] in self.STOP_CHARS
        ):
            self.pos += 4
        elif self.source[self.pos:self.pos + 5] == 'false' and (
            self.pos + 5 >= len(self.source) or self.source[self.pos + 5] in self.STOP_CHARS
        ):
            self.pos += 5
        else:
            self._field_ref()

    def _string_literal(self):
        self._consume("'")
        end = self.source.find("'", self.pos)
        if end == -1:
            raise ParseError('unterminated string literal', self.pos)
        self.pos = end + 1

    def _field_ref(self):
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] not in self.STOP_CHARS:
            self.pos += 1
        ref = self.source[start:self.pos]
        if not ref:
            raise ParseError(f'expected field reference at position {start}', start)
        self.field_refs.append(ref)


def parse_expression(expr: str) -> Tuple[List[str], str]:
    """Parse an expression, return (field_refs, error_or_empty)."""
    try:
        refs = _ExprParser(expr).parse()
        return refs, ''
    except ParseError as e:
        return [], str(e)


# ---------------------------------------------------------------------------
# Form validator
# ---------------------------------------------------------------------------

class _Validator:
    def __init__(self, form: Dict[str, Any], filename: str):
        self.form = form
        self.filename = filename
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.field_ids: Set[str] = set()
        self.page_ids: Set[str] = set()
        self.referenced_fields: Set[str] = set()

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def _extract_wizard(self) -> Any:
        """Extract wizard config from _rdmWizard ExpressionFormField."""
        editor = self.form.get('editorJson', self.form)
        fields = editor.get('fields', [])
        if not isinstance(fields, list):
            return None
        for field in fields:
            if isinstance(field, dict) and field.get('id') == '_rdmWizard':
                expr = field.get('expression')
                if not isinstance(expr, str):
                    self.error('_rdmWizard field: expression must be a string')
                    return None
                try:
                    return json.loads(expr)
                except json.JSONDecodeError as e:
                    self.error(f'_rdmWizard field: invalid JSON in expression: {e}')
                    return None
        return None

    def validate(self) -> bool:
        self._collect_field_ids()
        wizard = self._extract_wizard()
        if wizard is None:
            self.error('no _rdmWizard field found (ExpressionFormField with id="_rdmWizard")')
            return False
        if not isinstance(wizard, dict):
            self.error('_rdmWizard expression must parse to an object')
            return False

        pages = wizard.get('pages')
        if not isinstance(pages, list) or not pages:
            self.error('rdmWizard.pages must be a non-empty array')
            return False

        self._validate_pages(pages, 'rdmWizard.pages')
        self._validate_alias(wizard.get('alias'))
        self._validate_navigation(wizard.get('navigation'))
        self._validate_progress(wizard.get('progress'))
        self._validate_field_hints(wizard.get('fieldHints'))
        self._validate_array_input_fields()
        self._validate_template_expressions()
        self._check_orphan_fields()
        return len(self.errors) == 0

    def _collect_field_ids(self):
        editor = self.form.get('editorJson', self.form)
        fields = editor.get('fields', [])
        if not isinstance(fields, list):
            self.error('fields must be an array')
            return
        for f in fields:
            if isinstance(f, dict) and 'id' in f:
                if f['id'] == '_rdmWizard':
                    continue
                self.field_ids.add(f['id'])

    def _validate_pages(self, pages: list, path: str):
        for i, page in enumerate(pages):
            p = f'{path}[{i}]'
            if not isinstance(page, dict):
                self.error(f'{p}: page must be an object')
                continue
            self._validate_page(page, p)

    def _validate_page(self, page: Dict[str, Any], path: str):
        # id
        page_id = page.get('id')
        if not isinstance(page_id, str) or not page_id:
            self.error(f'{path}: id is required (string)')
        elif page_id in self.page_ids:
            self.error(f'{path}: duplicate page id {page_id!r}')
        else:
            self.page_ids.add(page_id)

        # title
        title = page.get('title')
        if not isinstance(title, str) or not title:
            self.error(f'{path}: title is required (string)')

        page_type = page.get('type')

        # visible
        visible = page.get('visible')
        if visible is not None:
            self._validate_visible(visible, path)

        if page_type == 'group':
            self._validate_group_page(page, path)
        elif page_type is None:
            self._validate_normal_page(page, path)
        else:
            self.error(f'{path}: unknown page type {page_type!r} (expected "group" or omitted)')

    def _validate_normal_page(self, page: Dict[str, Any], path: str):
        fields = page.get('fields')
        if not isinstance(fields, list) or not fields:
            self.error(f'{path}: fields is required for normal pages (non-empty string array)')
            return
        for j, fid in enumerate(fields):
            if not isinstance(fid, str):
                self.error(f'{path}.fields[{j}]: must be a string (field ID)')
                continue
            self.referenced_fields.add(fid)
            if fid not in self.field_ids:
                self.error(f'{path}.fields[{j}]: field ID {fid!r} not found in form fields')
        if 'pages' in page:
            self.error(f'{path}: normal page must not have "pages" (did you mean type: "group"?)')

    def _validate_group_page(self, page: Dict[str, Any], path: str):
        if 'fields' in page:
            self.error(f'{path}: group page must not have "fields"')
        sub = page.get('pages')
        if not isinstance(sub, list) or not sub:
            self.error(f'{path}: group page requires "pages" (non-empty array)')
            return
        self._validate_pages(sub, f'{path}.pages')

    def _validate_visible(self, visible: Any, path: str):
        if isinstance(visible, bool):
            return
        if not isinstance(visible, str):
            self.error(f'{path}.visible: must be a boolean or expression string')
            return
        refs, err = parse_expression(visible)
        if err:
            self.error(f'{path}.visible: parse error: {err}')
            return
        for ref in refs:
            if ref not in self.field_ids:
                self.warn(f'{path}.visible: field reference {ref!r} not found in form fields '
                          '(may be a task variable)')

    def _validate_alias(self, alias: Any):
        if alias is None:
            return
        if not isinstance(alias, dict):
            self.error('rdmWizard.alias must be an object')
            return
        targets = set()
        for alias_id, source_id in alias.items():
            if not isinstance(alias_id, str) or not alias_id:
                self.error(f'rdmWizard.alias: key must be a non-empty string')
                continue
            if not isinstance(source_id, str) or not source_id:
                self.error(f'rdmWizard.alias[{alias_id!r}]: value must be a non-empty string')
                continue
            if alias_id == source_id:
                self.error(f'rdmWizard.alias[{alias_id!r}]: alias and source must differ')
                continue
            if alias_id not in self.field_ids:
                self.error(f'rdmWizard.alias[{alias_id!r}]: alias field not found in form fields')
            if source_id not in self.field_ids:
                self.error(f'rdmWizard.alias[{alias_id!r}]: source field {source_id!r} not found in form fields')
            if alias_id in targets:
                self.error(f'rdmWizard.alias[{alias_id!r}]: duplicate alias target')
            targets.add(alias_id)
            # Circular: A→B and B→A
            if source_id in alias and alias[source_id] == alias_id:
                self.error(f'rdmWizard.alias: circular reference between {alias_id!r} and {source_id!r}')

    def _validate_navigation(self, nav: Any):
        if nav is None:
            return
        if not isinstance(nav, dict):
            self.error('rdmWizard.navigation must be an object')
            return
        for key in nav:
            if key not in ('allowBack', 'allowHeaderNavigation'):
                self.warn(f'rdmWizard.navigation: unknown property {key!r}')
        for key in ('allowBack', 'allowHeaderNavigation'):
            if key in nav and not isinstance(nav[key], bool):
                self.error(f'rdmWizard.navigation.{key}: must be a boolean')

    def _validate_progress(self, prog: Any):
        if prog is None:
            return
        if not isinstance(prog, dict):
            self.error('rdmWizard.progress must be an object')
            return
        style = prog.get('style')
        if style is not None and style not in ('sidebar', 'steps'):
            self.error(f'rdmWizard.progress.style: must be "sidebar" or "steps", got {style!r}')

    def _validate_field_hints(self, hints: Any):
        if hints is None:
            return
        if not isinstance(hints, dict):
            self.error('rdmWizard.fieldHints must be an object')
            return
        for key, hint in hints.items():
            path = f'rdmWizard.fieldHints[{key!r}]'
            if not isinstance(key, str) or not key:
                self.error(f'{path}: key must be a non-empty string')
                continue
            if not isinstance(hint, dict):
                self.error(f'{path}: value must be an object')
                continue
            # Resolve dotted key: "arrayField.subField"
            parts = key.split('.', 1)
            base_id = parts[0]
            if base_id not in self.field_ids:
                self.error(f'{path}: field {base_id!r} not found in form fields')
            # Validate visible
            visible = hint.get('visible')
            if visible is not None:
                self._validate_visible(visible, path)
            # Validate ui
            ui = hint.get('ui')
            if ui is not None:
                self._validate_field_hint_ui(ui, path)
            # Validate suggestion
            suggestion = hint.get('suggestion')
            if suggestion is not None:
                self._validate_field_hint_suggestion(suggestion, path)
            for prop in hint:
                if prop not in ('visible', 'ui', 'suggestion'):
                    self.warn(f'{path}: unknown property {prop!r}')

    def _validate_field_hint_ui(self, ui: Any, path: str):
        if not isinstance(ui, dict):
            self.error(f'{path}.ui: must be an object')
            return
        width = ui.get('width')
        if width is not None and width not in ('narrow', 'half', 'full'):
            self.error(f'{path}.ui.width: must be "narrow", "half", or "full", got {width!r}')
        freetext = ui.get('freetext')
        if freetext is not None and not isinstance(freetext, bool):
            self.error(f'{path}.ui.freetext: must be a boolean')
        option_map = ui.get('optionMap')
        if option_map is not None:
            if not isinstance(option_map, dict):
                self.error(f'{path}.ui.optionMap: must be an object')
            elif not all(isinstance(v, str) for v in option_map.values()):
                self.error(f'{path}.ui.optionMap: all values must be strings')
        for prop in ui:
            if prop not in ('width', 'freetext', 'optionMap'):
                self.warn(f'{path}.ui: unknown property {prop!r}')

    def _validate_field_hint_suggestion(self, suggestion: Any, path: str):
        if not isinstance(suggestion, list):
            self.error(f'{path}.suggestion: must be an array')
            return
        for i, config in enumerate(suggestion):
            sp = f'{path}.suggestion[{i}]'
            if not isinstance(config, dict):
                self.error(f'{sp}: must be an object')
                continue
            if 'key' not in config or not isinstance(config['key'], str):
                self.error(f'{sp}.key: required string')
                continue
            template = config.get('template')
            if template is not None and not isinstance(template, str):
                self.error(f'{sp}.template: must be a string')
            value_field = config.get('valueField')
            if value_field is not None and not isinstance(value_field, str):
                self.error(f'{sp}.valueField: must be a string')
            autofill = config.get('autofill')
            if autofill is not None:
                if not isinstance(autofill, dict):
                    self.error(f'{sp}.autofill: must be an object')
                elif not all(isinstance(v, str) for v in autofill.values()):
                    self.error(f'{sp}.autofill: all values must be strings')

    def _validate_array_input_fields(self):
        """Validate _ARRAY_INPUT placeholder JSON in multi-line-text fields."""
        import re
        editor = self.form.get('editorJson', self.form)
        for field in editor.get('fields', []):
            if not isinstance(field, dict):
                continue
            if field.get('type') != 'multi-line-text':
                continue
            placeholder = field.get('placeholder', '')
            if not isinstance(placeholder, str):
                continue
            match = re.match(r'^_ARRAY_INPUT\((.+)\)$', placeholder, re.DOTALL)
            if not match:
                continue
            fid = field['id']
            path = f'field[{fid!r}]._ARRAY_INPUT'
            try:
                sub_fields = json.loads(match.group(1))
            except json.JSONDecodeError as e:
                self.error(f'{path}: invalid JSON: {e}')
                continue
            if not isinstance(sub_fields, list):
                self.error(f'{path}: must be a JSON array')
                continue
            for i, sf in enumerate(sub_fields):
                sp = f'{path}[{i}]'
                if not isinstance(sf, dict):
                    self.error(f'{sp}: must be an object')
                    continue
                if 'id' not in sf or not isinstance(sf['id'], str):
                    self.error(f'{sp}: id is required (string)')
                if 'type' not in sf or not isinstance(sf['type'], str):
                    self.error(f'{sp}: type is required (string)')

    def _validate_template_expressions(self):
        """Check {{ }}/{% %} balance in ExpressionFormField expressions."""
        import re
        editor = self.form.get('editorJson', self.form)
        for field in editor.get('fields', []):
            if not isinstance(field, dict):
                continue
            if field.get('type') != 'expression':
                continue
            if field.get('id') == '_rdmWizard':
                continue
            expr = field.get('expression', '')
            if not isinstance(expr, str):
                continue
            if '{{' not in expr and '{%' not in expr:
                continue
            fid = field['id']
            path = f'field[{fid!r}].expression'
            # Check {{ }} balance
            open_count = len(re.findall(r'\{\{-?', expr))
            close_count = len(re.findall(r'-?\}\}', expr))
            if open_count != close_count:
                self.error(f'{path}: unbalanced {{{{ }}}} ({open_count} open, {close_count} close)')
            # Check {% %} tag balance
            tags = re.findall(r'\{%-?\s*(\w+)', expr)
            stack = []
            for tag in tags:
                if tag in ('for', 'if'):
                    stack.append(tag)
                elif tag == 'endfor':
                    if not stack or stack[-1] != 'for':
                        self.error(f'{path}: unexpected {{% endfor %}} without matching {{% for %}}')
                    else:
                        stack.pop()
                elif tag == 'endif':
                    if not stack or stack[-1] != 'if':
                        self.error(f'{path}: unexpected {{% endif %}} without matching {{% if %}}')
                    else:
                        stack.pop()
            for unclosed in reversed(stack):
                self.error(f'{path}: unclosed {{% {unclosed} %}}')

    def _check_orphan_fields(self):
        orphans = self.field_ids - self.referenced_fields
        # Exclude display-only field types from orphan check
        editor = self.form.get('editorJson', self.form)
        for f in editor.get('fields', []):
            if not isinstance(f, dict):
                continue
            fid = f.get('id')
            ftype = f.get('type', '')
            if fid in orphans and ftype in (
                'expression', 'hyperlink', 'link', 'headline',
                'headline-with-line', 'spacer', 'horizontal-line',
            ):
                orphans.discard(fid)
        if orphans:
            self.warn(f'fields not referenced by any page: {sorted(orphans)}')


def validate_form(form: Dict[str, Any], filename: str = '<stdin>') -> Tuple[List[str], List[str]]:
    v = _Validator(form, filename)
    v.validate()
    return v.errors, v.warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} FORM.json [FORM2.json ...]', file=sys.stderr)
        sys.exit(2)

    has_errors = False
    for path in sys.argv[1:]:
        try:
            with open(path) as f:
                form = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f'{path}: {e}', file=sys.stderr)
            has_errors = True
            continue

        errors, warnings = validate_form(form, path)
        for w in warnings:
            print(f'{path}: WARNING: {w}')
        for e in errors:
            print(f'{path}: ERROR: {e}')

        if errors:
            has_errors = True
        elif not warnings:
            print(f'{path}: OK')

    sys.exit(1 if has_errors else 0)


if __name__ == '__main__':
    main()
