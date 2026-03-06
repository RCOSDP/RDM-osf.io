# -*- coding: utf-8 -*-
"""Reporting test for metadata addon"""
import copy
import json
import mock
from nose.tools import *  # noqa (PEP8 asserts)
import pytest
from tests.base import OsfTestCase

from ..models import RegistrationReportFormat
from ..utils import make_report_as_csv


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
        from ..utils import transform_name_fields_item
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
        from ..utils import transform_name_fields_item
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
        from ..utils import transform_name_fields_item
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
        from ..utils import transform_name_fields_item
        data = {
            'grdm-file:creators': {
                'value': [
                    {'number': '111', 'name-ja': {'last': '情報', 'middle': '', 'first': '太郎'}}
                ]
            }
        }
        assert transform_name_fields_item(data) is False

    def test_item_data_man_name(self):
        from ..utils import transform_name_fields_item
        data = {
            'grdm-file:data-man-name-ja': {'value': '管理花子'},
            'grdm-file:data-man-name-en': {'value': 'Hanako Manager'},
        }
        assert transform_name_fields_item(data) is True
        assert data['grdm-file:data-man-name-ja']['value'] == {'last': '管理花子', 'middle': '', 'first': ''}
        assert data['grdm-file:data-man-name-en']['value'] == {'last': 'Hanako Manager', 'middle': '', 'first': ''}

    def test_item_data_man_name_already_object(self):
        from ..utils import transform_name_fields_item
        data = {
            'grdm-file:data-man-name-ja': {'value': {'last': '管理', 'middle': '', 'first': '花子'}},
        }
        assert transform_name_fields_item(data) is False

    def test_item_idempotent(self):
        from ..utils import transform_name_fields_item
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
        from ..utils import transform_name_fields_item
        data = {'grdm-file:title-ja': {'value': 'テスト'}}
        assert transform_name_fields_item(data) is False

    def test_entry_creators(self):
        """Registration/DraftRegistration format: no {value:} wrapper."""
        from ..utils import transform_name_fields_entry
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
        from ..utils import transform_name_fields_entry
        entry = {
            'metadata': {
                'grdm-file:data-man-name-ja': '管理花子',
                'grdm-file:data-man-name-en': 'Hanako Manager',
            }
        }
        assert transform_name_fields_entry(entry) is True
        assert entry['metadata']['grdm-file:data-man-name-ja'] == {'last': '管理花子', 'middle': '', 'first': ''}
        assert entry['metadata']['grdm-file:data-man-name-en'] == {'last': 'Hanako Manager', 'middle': '', 'first': ''}
