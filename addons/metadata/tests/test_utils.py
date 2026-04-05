# -*- coding: utf-8 -*-
"""Reporting test for metadata addon"""
import copy
import json
import mock
from nose.tools import *  # noqa (PEP8 asserts)
import pytest
from tests.base import OsfTestCase

from ..models import RegistrationReportFormat
from ..utils import (
    make_report_as_csv,
    _name_to_str_ja,
    _name_to_str_en,
    transform_name_fields_item,
    transform_name_fields_entry,
)


class TestMakeReportAsCsv(OsfTestCase):

    def test_simple(self):
        format = RegistrationReportFormat.objects.create(
            csv_template='{{example}}',
        )
        data = {
            'example': {
                'value': 'TEST',
            }
        }
        schema = {'pages': []}
        filename, result = make_report_as_csv(format, data, schema)
        assert_equal(filename, 'report.csv')
        assert_equal(result, 'TEST')

    def test_complex_name(self):
        format = RegistrationReportFormat.objects.create(
            csv_template='{{example_data}}',
        )
        data = {
            'example-data': {
                'value': 'TEST',
            }
        }
        schema = {'pages': []}
        filename, result = make_report_as_csv(format, data, schema)
        assert_equal(filename, 'report.csv')
        assert_equal(result, 'TEST')

    def test_quoted(self):
        format = RegistrationReportFormat.objects.create(
            csv_template='{{example_data | quotecsv}}',
        )
        data = {
            'example-data': {
                'value': 'TEST,DATA',
            }
        }
        schema = {'pages': []}
        filename, result = make_report_as_csv(format, data, schema)
        assert_equal(filename, 'report.csv')
        assert_equal(result, '"TEST,DATA"')

    def test_choose_tooltip(self):
        format = RegistrationReportFormat.objects.create(
            csv_template='{{example}},{{example_tooltip}},{{example_tooltip_0}},{{example_tooltip_1}},{{example_tooltip_2}},{{example_tooltip_3}}',
        )
        data = {
            'example': {
                'value': '2',
            }
        }
        schema = {'pages': [
            {
                'questions': [
                    {
                        'qid': 'example',
                        'type': 'choose',
                        'options': [
                            {
                                'text': '1',
                                'tooltip': '一|one',
                            },
                            {
                                'text': '2',
                                'tooltip': '二|two',
                            },
                            {
                                'text': '3',
                                'tooltip': '三|three',
                            },
                        ],
                    }
                ],
            }
        ]}
        filename, result = make_report_as_csv(format, data, schema)
        assert_equal(filename, 'report.csv')
        assert_equal(result, '2,二|two,二,two,,')


class TestTransformNameFields:
    """Tests for name field migration transform functions."""

    def test_item_creators_underscore_string(self):

        data = {
            'grdm-file:creators': {
                'value': [
                    {'number': '111', 'name_ja': '情報太郎', 'name_en': 'Taro Joho'}
                ]
            }
        }
        assert transform_name_fields_item(data) is True
        row = data['grdm-file:creators']['value'][0]
        assert 'name_ja' not in row
        assert row['name-ja'] == {'last': '情報太郎', 'middle': '', 'first': ''}
        assert row['name-en'] == {'last': 'Taro Joho', 'middle': '', 'first': ''}

    def test_item_creators_hyphen_string(self):

        data = {
            'grdm-file:creators': {
                'value': [
                    {'number': '111', 'name-ja': '情報太郎', 'name-en': 'Taro Joho'}
                ]
            }
        }
        assert transform_name_fields_item(data) is True
        row = data['grdm-file:creators']['value'][0]
        assert row['name-ja'] == {'last': '情報太郎', 'middle': '', 'first': ''}

    def test_item_creators_json_string_value(self):
        """creators value stored as JSON string."""

        data = {
            'grdm-file:creators': {
                'value': json.dumps([
                    {'number': '111', 'name_ja': '情報太郎', 'name_en': 'Taro Joho'}
                ])
            }
        }
        assert transform_name_fields_item(data) is True
        row = data['grdm-file:creators']['value'][0]
        assert row['name-ja'] == {'last': '情報太郎', 'middle': '', 'first': ''}

    def test_item_creators_already_object(self):

        data = {
            'grdm-file:creators': {
                'value': [
                    {'number': '111', 'name-ja': {'last': '情報', 'middle': '', 'first': '太郎'}}
                ]
            }
        }
        assert transform_name_fields_item(data) is False

    def test_item_data_man_name(self):

        data = {
            'grdm-file:data-man-name-ja': {'value': '管理花子'},
            'grdm-file:data-man-name-en': {'value': 'Hanako Manager'},
        }
        assert transform_name_fields_item(data) is True
        assert data['grdm-file:data-man-name-ja']['value'] == {'last': '管理花子', 'middle': '', 'first': ''}
        assert data['grdm-file:data-man-name-en']['value'] == {'last': 'Hanako Manager', 'middle': '', 'first': ''}

    def test_item_data_man_name_already_object(self):

        data = {
            'grdm-file:data-man-name-ja': {'value': {'last': '管理', 'middle': '', 'first': '花子'}},
        }
        assert transform_name_fields_item(data) is False

    def test_item_idempotent(self):

        data = {
            'grdm-file:creators': {
                'value': [
                    {'number': '111', 'name_ja': '情報太郎', 'name_en': 'Taro Joho'}
                ]
            },
            'grdm-file:data-man-name-ja': {'value': '管理花子'},
            'grdm-file:data-man-name-en': {'value': 'Hanako Manager'},
        }
        transform_name_fields_item(data)
        snapshot = copy.deepcopy(data)
        assert transform_name_fields_item(data) is False
        assert data == snapshot

    def test_item_no_relevant_fields(self):

        data = {'grdm-file:title-ja': {'value': 'テスト'}}
        assert transform_name_fields_item(data) is False

    def test_entry_creators(self):
        """Registration/DraftRegistration format: no {value:} wrapper."""

        entry = {
            'metadata': {
                'grdm-file:creators': [
                    {'number': '111', 'name_ja': '情報太郎', 'name_en': 'Taro Joho'}
                ],
            }
        }
        assert transform_name_fields_entry(entry) is True
        row = entry['metadata']['grdm-file:creators'][0]
        assert row['name-ja'] == {'last': '情報太郎', 'middle': '', 'first': ''}

    def test_entry_data_man_name(self):
        """Registration/DraftRegistration format: plain string."""

        entry = {
            'metadata': {
                'grdm-file:data-man-name-ja': '管理花子',
                'grdm-file:data-man-name-en': 'Hanako Manager',
            }
        }
        assert transform_name_fields_entry(entry) is True
        assert entry['metadata']['grdm-file:data-man-name-ja'] == {'last': '管理花子', 'middle': '', 'first': ''}
        assert entry['metadata']['grdm-file:data-man-name-en'] == {'last': 'Hanako Manager', 'middle': '', 'first': ''}


class TestNameToStr:
    """Tests for _name_to_str_ja / _name_to_str_en filters."""

    def test_ja_basic(self):
        assert _name_to_str_ja({'last': '山田', 'middle': '', 'first': '太郎'}) == '山田太郎'

    def test_ja_with_middle(self):
        assert _name_to_str_ja({'last': '山田', 'middle': 'ミドル', 'first': '太郎'}) == '山田ミドル太郎'

    def test_ja_migrated_legacy(self):
        """Legacy data: full name in last, first is empty."""
        assert _name_to_str_ja({'last': '山田太郎', 'middle': '', 'first': ''}) == '山田太郎'

    def test_ja_legacy_str_warns(self):
        """Pre-migration str data logs warning and passes through."""
        assert _name_to_str_ja('山田太郎') == '山田太郎'

    def test_en_basic(self):
        assert _name_to_str_en({'last': 'Yamada', 'middle': '', 'first': 'Taro'}) == 'Taro Yamada'

    def test_en_with_middle(self):
        assert _name_to_str_en({'last': 'Yamada', 'middle': 'M', 'first': 'Taro'}) == 'Taro M Yamada'

    def test_en_migrated_legacy(self):
        """Legacy data: full name in last, first is empty."""
        assert _name_to_str_en({'last': 'Taro Yamada', 'middle': '', 'first': ''}) == 'Taro Yamada'

    def test_en_legacy_str_warns(self):
        """Pre-migration str data logs warning and passes through."""
        assert _name_to_str_en('Taro Yamada') == 'Taro Yamada'
