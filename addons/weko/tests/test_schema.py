# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import mock
from mock import call
from nose.tools import *  # noqa
import re

from osf.models.metaschema import RegistrationSchema
from osf_tests.factories import UserFactory
from tests.base import OsfTestCase

from addons.weko import schema


logger = logging.getLogger(__name__)


def _transpose(lines):
    assert len(set([len(l) for l in lines])) == 1, set([len(l) for l in lines])
    return [[row[i] for row in lines] for i in range(len(lines[0]))]


class TestWEKOSchema(OsfTestCase):

    def setUp(self):
        super(TestWEKOSchema, self).setUp()
        self.user = UserFactory()

    def tearDown(self):
        super(TestWEKOSchema, self).tearDown()

    def test_write_csv_minimal(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        files = [
            ('test.jpg', 'image/jpeg'),
        ]
        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()
        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,
                    'data': {
                        'grdm-file:title-en': {
                            'value': 'ENGLISH TITLE',
                        },
                        'grdm-file:data-description-ja': {
                            'value': '日本語説明',
                        },
                    },
                },
            ],
        }

        schema.write_csv(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [],
        )

        logger.info(f'CSV: {buf.getvalue()}')
        buf.seek(0)
        reader = csv.reader(buf)
        lines = list(reader)
        assert_equal(len(lines), 6)
        assert_equal(lines[0], [
            '#ItemType',
            'デフォルトアイテムタイプ（フル）(30002)',
            'https://localhost:8443/items/jsonschema/30002',
        ])
        props = _transpose(lines[1::])[::-1]

        assert_equal(
            props.pop(),
            ['.publish_status', '.PUBLISH_STATUS', '', 'Required', 'private'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.path[0]', '.IndexID[0]', '', 'Allow Multiple', '1000'],
        )
        assert_equal(
            props.pop(),
            ['.pos_index[0]', '.POS_INDEX[0]', '', 'Allow Multiple', 'TITLE'],
        )
        assert_equal(
            props.pop(),
            ['.file_path[0]', '.ファイルパス[0]', '', 'Allow Multiple', 'files/test.jpg'],
        )
        feedback_mail = props.pop()
        assert_equal(
            feedback_mail[:-1],
            ['.feedback_mail[0]', '', '', ''],
        )
        assert_true(
            re.match(r'[^@]+@[^@]+\.[^@]+', feedback_mail[-1])
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].displaytype', '', '', '', 'preview'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].filename', '', '', '', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].format', '', '', '', 'image/jpeg'],
        )
        pub_date = props.pop()
        assert_equal(
            pub_date[:-1],
            ['.metadata.pubdate', '', '', ''],
        )
        assert_true(
            re.match(r'[0-9]+\-[0-9]+\-[0-9]+', pub_date[-1])
        )

    def test_write_csv_full(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        files = [
            ('test.jpg', 'image/jpeg'),
        ]
        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()
        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,
                    'data': dict([(k, {
                        'value': v,
                    })for k, v in {
                        'grdm-file:data-number': '00001',
                        'grdm-file:title-en': 'TEST DATA',
                        'grdm-file:title-ja': 'テストデータ',
                        'grdm-file:date-issued-updated': '2023-09-15',
                        'grdm-file:data-description-ja': 'テスト説明',
                        'grdm-file:data-description-en': 'TEST DESCRIPTION',
                        'grdm-file:data-research-field': '189',
                        'grdm-file:data-type': 'experimental data',
                        'grdm-file:file-size': '29.9KB',
                        'grdm-file:data-policy-free': 'free',
                        'grdm-file:data-policy-license': 'CC0',
                        'grdm-file:data-policy-cite-ja': 'ライセンスのテスト',
                        'grdm-file:data-policy-cite-en': 'Test for license',
                        'grdm-file:access-rights': 'restricted access',
                        'grdm-file:available-date': '',
                        'grdm-file:repo-information-ja': 'テストリポジトリ',
                        'grdm-file:repo-information-en': 'Test Repository',
                        'grdm-file:repo-url-doi-link': 'http://localhost:5000/q3gnm/files/osfstorage/650e68f8c00e45055fc9e0ac',
                        'grdm-file:creators': [
                            {
                                'number': '22222',
                                'name-ja': '情報太郎',
                                'name-en': 'Taro Joho',
                            }
                        ],
                        'grdm-file:hosting-inst-ja': '国立情報学研究所',
                        'grdm-file:hosting-inst-en': 'National Institute of Informatics',
                        'grdm-file:hosting-inst-id': 'https://ror.org/04ksd4g47',
                        'grdm-file:data-man-type': 'individual',
                        'grdm-file:data-man-number': '11111',
                        'grdm-file:data-man-name-ja': '情報花子',
                        'grdm-file:data-man-name-en': 'Hanako Joho',
                        'grdm-file:data-man-org-ja': '国立情報学研究所',
                        'grdm-file:data-man-org-en': 'National Institute of Informatics',
                        'grdm-file:data-man-address-ja': '一ツ橋',
                        'grdm-file:data-man-address-en': 'Hitotsubashi',
                        'grdm-file:data-man-tel': 'XX-XXXX-XXXX',
                        'grdm-file:data-man-email': 'dummy@test.rcos.nii.ac.jp',
                        'grdm-file:remarks-ja': 'コメント',
                        'grdm-file:remarks-en': 'Comment',
                        'grdm-file:metadata-access-rights': 'closed access',
                    }.items()]),
                },
            ],
        }

        schema.write_csv(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [],
        )

        logger.info(f'CSV: {buf.getvalue()}')
        buf.seek(0)
        reader = csv.reader(buf)
        lines = list(reader)
        assert_equal(len(lines), 6)
        logger.info(repr(lines))
        assert_equal(lines[0], [
            '#ItemType',
            'デフォルトアイテムタイプ（フル）(30002)',
            'https://localhost:8443/items/jsonschema/30002',
        ])
        props = _transpose(lines[1::])[::-1]

        assert_equal(
            props.pop(),
            ['.publish_status', '.PUBLISH_STATUS', '', 'Required', 'private'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.path[0]', '.IndexID[0]', '', 'Allow Multiple', '1000'],
        )
        assert_equal(
            props.pop(),
            ['.pos_index[0]', '.POS_INDEX[0]', '', 'Allow Multiple', 'TITLE'],
        )
        assert_equal(
            props.pop(),
            ['.file_path[0]', '.ファイルパス[0]', '', 'Allow Multiple', 'files/test.jpg'],
        )
        feedback_mail = props.pop()
        assert_equal(
            feedback_mail[:-1],
            ['.feedback_mail[0]', '', '', ''],
        )
        assert_true(
            re.match(r'[^@]+@[^@]+\.[^@]+', feedback_mail[-1])
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].displaytype', '', '', '', 'preview'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].filename', '', '', '', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_file35[0].format', '', '', '', 'image/jpeg'],
        )
        pub_date = props.pop()
        assert_equal(
            pub_date[:-1],
            ['.metadata.pubdate', '', '', ''],
        )
        assert_true(
            re.match(r'[0-9]+\-[0-9]+\-[0-9]+', pub_date[-1])
        )