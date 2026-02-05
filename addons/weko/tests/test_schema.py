# -*- coding: utf-8 -*-
import copy
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
            [('test.jpg', 'image/jpeg')],
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
            ['.metadata.item_30002_file35[0].accessrole', '', '', '', 'open_no'],
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
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description', '', '', '', '日本語説明'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description_type', '', '', '', 'Abstract'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_resource_type13.resourcetype', '', '', '', 'dataset'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[0].subitem_title', '', '', '', 'ENGLISH TITLE'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[0].subitem_title_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['#.id', '#ID', '#', '#', ''],
        )
        assert_equal(
            props.pop(),
            ['.uri', 'URI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.cnri', '.CNRI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.doi_ra', '.DOI_RA', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.doi', '.DOI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.edit_mode', 'Keep/Upgrade Version', '', 'Required', 'Keep'],
        )

    def test_write_csv_full(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        files = [
            [('test.jpg', 'image/jpeg')],
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
            ['.metadata.item_30002_file35[0].accessrole', '', '', '', 'open_login'],
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
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_access_rights4.subitem_access_right', '', '', '', 'restricted access'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].creatorNames[0].creatorName', '', '', '', '情報太郎'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].creatorNames[0].creatorNameLang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].creatorNames[1].creatorName', '', '', '', 'Taro Joho'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].creatorNames[1].creatorNameLang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'e-Rad_Researcher'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_creator2[0].nameIdentifiers[0].nameIdentifierURI', '', '', '', '22222'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description', '', '', '', 'TEST DESCRIPTION'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[0].subitem_description_type', '', '', '', 'Abstract'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[1].subitem_description', '', '', '', 'テスト説明'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[1].subitem_description_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_description9[1].subitem_description_type', '', '', '', 'Abstract'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[0].contributorName', '', '', '', 'National Institute of Informatics Hitotsubashi TEL: XX-XXXX-XXXX E-Mail: dummy@test.rcos.nii.ac.jp'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[0].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[0].nameType', '', '', '', 'Organizational'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorType', '', '', '', 'ContactPerson'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[1].contributorName', '', '', '', '国立情報学研究所 一ツ橋 TEL: XX-XXXX-XXXX E-Mail: dummy@test.rcos.nii.ac.jp'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[1].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[0].contributorNames[1].nameType', '', '', '', 'Organizational'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].contributorNames[0].contributorName', '', '', '', 'Hanako Joho'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].contributorNames[0].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].contributorType', '', '', '', 'DataManager'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].contributorNames[1].contributorName', '', '', '', '情報花子'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].contributorNames[1].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'e-Rad_Researcher'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[1].nameIdentifiers[0].nameIdentifierURI', '', '', '', '11111'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[0].subitem_rights', '', '', '', 'Test for license'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[0].subitem_rights_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[1].subitem_rights', '', '', '', 'ライセンスのテスト'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[1].subitem_rights_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[2].subitem_rights', '', '', '', '無償'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[2].subitem_rights_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[3].subitem_rights', '', '', '', 'free'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[3].subitem_rights_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[4].subitem_rights', '', '', '', 'CC0 1.0 Universal'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_rights6[4].subitem_rights_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            [
                '.metadata.item_30002_rights6[4].subitem_rights_resource',
                '',
                '',
                '',
                'https://creativecommons.org/publicdomain/zero/1.0/deed.en',
            ],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[0].subitem_subject', '', '', '', 'Life Science'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[0].subitem_subject_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[0].subitem_subject_scheme', '', '', '', 'e-Rad_field'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[1].subitem_subject', '', '', '', 'ライフサイエンス'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[1].subitem_subject_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_subject8[1].subitem_subject_scheme', '', '', '', 'e-Rad_field'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_resource_type13.resourcetype', '', '', '', 'experimental data'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].contributorNames[0].contributorName', '', '', '', 'National Institute of Informatics'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].contributorNames[0].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].contributorType', '', '', '', 'HostingInstitution'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'ROR'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].nameIdentifiers[0].nameIdentifierURI', '', '', '', 'https://ror.org/04ksd4g47'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].contributorNames[1].contributorName', '', '', '', '国立情報学研究所'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_contributor3[2].contributorNames[1].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[0].subitem_title', '', '', '', 'TEST DATA'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[0].subitem_title_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[1].subitem_title', '', '', '', 'テストデータ'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_30002_title0[1].subitem_title_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['#.id', '#ID', '#', '#', ''],
        )
        assert_equal(
            props.pop(),
            ['.uri', 'URI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.cnri', '.CNRI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.doi_ra', '.DOI_RA', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.doi', '.DOI', '', '', ''],
        )
        assert_equal(
            props.pop(),
            ['.edit_mode', 'Keep/Upgrade Version', '', 'Required', 'Keep'],
        )

    def test_write_ro_crate_json_full(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        node_id = 'rvm3q'
        files = [
            [('test.jpg', 'image/jpeg')],
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
        project_metadata = {
            'funder': {
                'value': 'JST',
            },
            'funding-stream-code': {
                'value': 'JPTEST',
            },
            'program-name-ja': {
                'value': 'テストプログラム',
            },
            'program-name-en': {
                'value': 'Test Program',
            },
            'japan-grant-number': {
                'value': 'JP123456',
            },
            'project-name-ja': {
                'value': 'テストプロジェクト',
            },
            'project-name-en': {
                'value': 'Test Project',
            },
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [project_metadata],
            node_id
        )

        logger.info(f'JSON: {buf.getvalue()}')
        expected = '''{
  "@context": [
    "https://w3id.org/ro/crate/1.1/context",
    "http://purl.org/wk/v1/wk-context.jsonld",
    {
      "ams:analysisType": "https://purl.org/rdm/ontology/analysisType",
      "ams:descriptionOfExperimentalCondition": "https://purl.org/rdm/ontology/descriptionOfExperimentalCondition",
      "ams:purposeOfExperiment": "https://purl.org/rdm/ontology/purposeOfExperiment",
      "ams:analysisOtherType": "https://purl.org/rdm/ontology/analysisOtherType",
      "ams:anonymousProcessing": "https://purl.org/rdm/ontology/anonymousProcessing",
      "ams:availabilityOfCommercialUse": "https://purl.org/rdm/ontology/availabilityOfCommercialUse",
      "ams:conflictOfInterest": "https://purl.org/rdm/ontology/conflictOfInterest",
      "ams:conflictOfInterestName": "https://purl.org/rdm/ontology/conflictOfInterestName",
      "ams:consentForProvisionToAThirdParty": "https://purl.org/rdm/ontology/consentForProvisionToAThirdParty",
      "ams:dataPolicyFree": "https://purl.org/rdm/ontology/dataPolicyFree",
      "ams:ethicsReviewCommitteeApproval": "https://purl.org/rdm/ontology/ethicsReviewCommitteeApproval",
      "ams:icIsNo": "https://purl.org/rdm/ontology/icIsNo",
      "ams:identifier": "https://purl.org/rdm/ontology/identifier",
      "ams:industrialUse": "https://purl.org/rdm/ontology/industrialUse",
      "ams:informedConsent": "https://purl.org/rdm/ontology/informedConsent",
      "ams:license": "https://purl.org/rdm/ontology/license",
      "ams:namesToBeIncludedInTheAcknowledgments": "https://purl.org/rdm/ontology/namesToBeIncludedInTheAcknowledgments",
      "ams:necessityOfContactAndPermission": "https://purl.org/rdm/ontology/necessityOfContactAndPermission",
      "ams:necessityOfIncludingInAcknowledgments": "https://purl.org/rdm/ontology/necessityOfIncludingInAcknowledgments",
      "ams:otherConditionsOrSpecialNotes": "https://purl.org/rdm/ontology/otherConditionsOrSpecialNotes",
      "ams:overseasOfferings": "https://purl.org/rdm/ontology/overseasOfferings",
      "ams:projectId": "https://purl.org/rdm/ontology/projectId",
      "ams:repository": "https://purl.org/rdm/ontology/repository",
      "ams:repositoryId": "https://purl.org/rdm/ontology/repositoryId",
      "ams:repositoryInfo": "https://purl.org/rdm/ontology/repositoryInfo",
      "ams:targetTypeOfAcquiredData": "https://purl.org/rdm/ontology/targetTypeOfAcquiredData",
      "ams:existExternalMetadata": "https://purl.org/rdm/ontology/existExternalMetadata",
      "ams:externalMetadataFiles": "https://purl.org/rdm/ontology/externalMetadataFiles",
      "rdm:Dataset": "https://purl.org/rdm/ontology/Dataset",
      "rdm:AccessRights": "https://purl.org/rdm/ontology/AccessRights",
      "rdm:MetadataDocument": "https://purl.org/rdm/ontology/MetadataDocument",
      "rdm:field": "https://purl.org/rdm/ontology/field",
      "rdm:keywords": "https://purl.org/rdm/ontology/keywords",
      "rdm:metadataFiles": "https://purl.org/rdm/ontology/metadataFiles",
      "rdm:project": "https://purl.org/rdm/ontology/project",
      "rdm:name": "https://purl.org/rdm/ontology/name",
      "dc:type": "http://purl.org/dc/elements/1.1/type",
      "jpcoar:addtionalType": "https://github.com/JPCOAR/schema/blob/master/2.0/#addtionalType"
    },
    {
      "ams": "https://purl.org/rdm/ontology/"
    },
    {
      "wk": "https://purl.org/rdm/ontology/"
    },
    {
      "rdm": "https://purl.org/rdm/ontology/"
    },
    {
      "odrl": "http://www.w3.org/ns/odrl.jsonld"
    },
    {
      "dc": "http://purl.org/dc/elements/1.1/"
    },
    {
      "jpcoar": "https://github.com/JPCOAR/schema/blob/master/2.0/"
    },
    {
      "datacite": "http://datacite.org/schema/kernel-4"
    }
  ],
  "@graph": [
    {
      "jpcoar:fundingReference": [
        {
          "@id": "_:PropertyValue1"
        }
      ],
      "@id": "./",
      "@type": "Dataset",
      "conformsTo": {
        "@id": "https://w3id.org/ro/crate/1.1"
      },
      "description": "TEST DESCRIPTION",
      "name": "TEST DATA",
      "wk:index": "1000",
      "wk:publishStatus": "private",
      "dcterms:accessRights": [
        {
          "@id": "_:PropertyValue8"
        }
      ],
      "jpcoar:creator": [
        {
          "@id": "_:Person1"
        }
      ],
      "datacite:description": [
        {
          "@id": "_:PropertyValue9"
        },
        {
          "@id": "_:PropertyValue10"
        }
      ],
      "jpcoar:contributor": [
        {
          "@id": "_:Organization1"
        },
        {
          "@id": "_:Person5"
        },
        {
          "@id": "_:Organization4"
        }
      ],
      "dc:rights": [
        {
          "@id": "_:PropertyValue11"
        },
        {
          "@id": "_:PropertyValue12"
        },
        {
          "@id": "_:PropertyValue13"
        },
        {
          "@id": "_:PropertyValue14"
        },
        {
          "@id": "_:PropertyValue15"
        },
        {
          "@id": "_:PropertyValue16"
        }
      ],
      "jpcoar:subject": [
        {
          "@id": "_:PropertyValue17"
        },
        {
          "@id": "_:PropertyValue18"
        }
      ],
      "dc:type": {
        "@id": "_:PropertyValue19"
      },
      "dc:title": [
        {
          "@id": "_:PropertyValue20"
        },
        {
          "@id": "_:PropertyValue21"
        }
      ],
      "wk:isSplited": false,
      "hasPart": [
        {
          "@id": "files/test.jpg"
        }
      ]
    },
    {
      "@type": "Organization",
      "additionalType": {
        "@id": "https://github.com/JPCOAR/schema/blob/master/2.0/#ContactPerson"
      },
      "jpcoar:contributorName": [
        {
          "@id": "_:Organization2"
        },
        {
          "@id": "_:Organization3"
        }
      ],
      "jpcoar:contributorType": "ContactPerson",
      "@id": "_:Organization1"
    },
    {
      "@type": "Organization",
      "language": "en",
      "nameType": "Organizational",
      "value": "National Institute of Informatics Hitotsubashi TEL: XX-XXXX-XXXX E-Mail: dummy@test.rcos.nii.ac.jp",
      "@id": "_:Organization2"
    },
    {
      "@type": "Organization",
      "language": "ja",
      "nameType": "Organizational",
      "value": "国立情報学研究所 一ツ橋 TEL: XX-XXXX-XXXX E-Mail: dummy@test.rcos.nii.ac.jp",
      "@id": "_:Organization3"
    },
    {
      "@type": "Organization",
      "additionalType": {
        "@id": "https://github.com/JPCOAR/schema/blob/master/2.0/#HostingInstitution"
      },
      "jpcoar:contributorName": [
        {
          "@id": "_:Organization5"
        },
        {
          "@id": "_:Organization6"
        }
      ],
      "jpcoar:contributorType": "HostingInstitution",
      "jpcoar:nameIdentifier": [
        {
          "@id": "_:Organization7"
        }
      ],
      "@id": "_:Organization4"
    },
    {
      "@type": "Organization",
      "language": "en",
      "nameType": "Organizational",
      "value": "National Institute of Informatics",
      "@id": "_:Organization5"
    },
    {
      "@type": "Organization",
      "language": "ja",
      "nameType": "Organizational",
      "value": "国立情報学研究所",
      "@id": "_:Organization6"
    },
    {
      "@type": "Organization",
      "nameIdentifierScheme": "ROR",
      "value": "https://ror.org/04ksd4g47",
      "@id": "_:Organization7"
    },
    {
      "@type": "Person",
      "jpcoar:creatorName": [
        {
          "@id": "_:Person2"
        },
        {
          "@id": "_:Person3"
        }
      ],
      "jpcoar:nameIdentifier": [
        {
          "@id": "_:Person4"
        }
      ],
      "@id": "_:Person1"
    },
    {
      "@type": "Person",
      "language": "en",
      "value": "Taro Joho",
      "@id": "_:Person2"
    },
    {
      "@type": "Person",
      "language": "ja",
      "value": "情報太郎",
      "@id": "_:Person3"
    },
    {
      "@type": "Person",
      "nameIdentifierScheme": "e-Rad_Researcher",
      "value": "22222",
      "@id": "_:Person4"
    },
    {
      "@type": "Person",
      "additionalType": {
        "@id": "https://github.com/JPCOAR/schema/blob/master/2.0/#DataManager"
      },
      "jpcoar:contributorName": [
        {
          "@id": "_:Person6"
        },
        {
          "@id": "_:Person7"
        }
      ],
      "jpcoar:contributorType": "DataManager",
      "jpcoar:nameIdentifier": [
        {
          "@id": "_:Person8"
        }
      ],
      "@id": "_:Person5"
    },
    {
      "@type": "Person",
      "language": "en",
      "value": "Hanako Joho",
      "@id": "_:Person6"
    },
    {
      "@type": "Person",
      "language": "ja",
      "value": "情報花子",
      "@id": "_:Person7"
    },
    {
      "@type": "Person",
      "nameIdentifierScheme": "e-Rad_Researcher",
      "value": "11111",
      "@id": "_:Person8"
    },
    {
      "@type": "PropertyValue",
      "jpcoar:awardNumber": {
        "@id": "_:jpcoar_awardNumber1"
      },
      "jpcoar:awardTitle": [
        {
          "@id": "_:PropertyValue2"
        },
        {
          "@id": "_:PropertyValue3"
        }
      ],
      "jpcoar:funderIdentifier": {
        "@id": "_:jpcoar_funderIdentifier1"
      },
      "jpcoar:funderName": [
        {
          "@id": "_:PropertyValue4"
        },
        {
          "@id": "_:PropertyValue5"
        }
      ],
      "jpcoar:fundingStreamIdentifier": {
        "@id": "_:jpcoar_fundingStreamIdentifier1"
      },
      "jpcoar:fundingStream": [
        {
          "@id": "_:PropertyValue6"
        },
        {
          "@id": "_:PropertyValue7"
        }
      ],
      "@id": "_:PropertyValue1"
    },
    {
      "@type": "PropertyValue",
      "descriptionType": "Abstract",
      "language": "ja",
      "value": "テスト説明",
      "@id": "_:PropertyValue10"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "Test for license",
      "@id": "_:PropertyValue11"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "ライセンスのテスト",
      "@id": "_:PropertyValue12"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "free",
      "@id": "_:PropertyValue13"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "無償",
      "@id": "_:PropertyValue14"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "rdf:resource": "https://creativecommons.org/publicdomain/zero/1.0/deed.en",
      "value": "CC0 1.0 Universal",
      "@id": "_:PropertyValue15"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "rdf:resource": "https://creativecommons.org/publicdomain/zero/1.0/deed.en",
      "value": "CC0 1.0 Universal",
      "@id": "_:PropertyValue16"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "subjectScheme": "e-Rad_field",
      "value": "Life Science",
      "@id": "_:PropertyValue17"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "subjectScheme": "e-Rad_field",
      "value": "ライフサイエンス",
      "@id": "_:PropertyValue18"
    },
    {
      "@type": "PropertyValue",
      "rdf:resource": "http://purl.org/coar/resource_type/63NG-B465/",
      "value": "experimental data",
      "@id": "_:PropertyValue19"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "Test Project",
      "@id": "_:PropertyValue2"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "TEST DATA",
      "@id": "_:PropertyValue20"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "テストデータ",
      "@id": "_:PropertyValue21"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "テストプロジェクト",
      "@id": "_:PropertyValue3"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "Japan Science and Technology Agency(JST)",
      "@id": "_:PropertyValue4"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "国立研究開発法人科学技術振興機構(JST)",
      "@id": "_:PropertyValue5"
    },
    {
      "@type": "PropertyValue",
      "language": "en",
      "value": "Test Program",
      "@id": "_:PropertyValue6"
    },
    {
      "@type": "PropertyValue",
      "language": "ja",
      "value": "テストプログラム",
      "@id": "_:PropertyValue7"
    },
    {
      "@type": "PropertyValue",
      "rdf:resource": "http://purl.org/coar/access_right/c_16ec",
      "value": "restricted access",
      "@id": "_:PropertyValue8"
    },
    {
      "@type": "PropertyValue",
      "descriptionType": "Abstract",
      "language": "en",
      "value": "TEST DESCRIPTION",
      "@id": "_:PropertyValue9"
    },
    {
      "@type": "jpcoar:awardNumber",
      "jpcoar:awardNumberType": "JGN",
      "value": "JP123456",
      "@id": "_:jpcoar_awardNumber1"
    },
    {
      "@type": "jpcoar:funderIdentifier",
      "jpcoar:funderIdentifierType": "ROR",
      "value": "https://ror.org/00097mb19",
      "@id": "_:jpcoar_funderIdentifier1"
    },
    {
      "@type": "jpcoar:fundingStreamIdentifier",
      "jpcoar:fundingStreamIdentifierType": "JGN_fundingStream",
      "value": "JPTEST",
      "@id": "_:jpcoar_fundingStreamIdentifier1"
    },
    {
      "@type": "File",
      "dcterms:accessRights": "open_login",
      "jpcoar:mimeType": "image/jpeg",
      "jpcoar:format": "preview",
      "name": "test.jpg",
      "@id": "files/test.jpg"
    },
    {
      "@id": "ro-crate-metadata.json",
      "@type": "CreativeWork",
      "about": {
        "@id": "./"
      },
      "conformsTo": {
        "@id": "https://w3id.org/ro/crate/1.1"
      }
    }
  ]
}
'''
        actual_json = json.loads(buf.getvalue())
        for item in actual_json['@graph']:
            item.pop('wk:feedbackMail', None)
            item.pop('datePublished', None)
        expected_json = json.loads(expected)
        actual_json['@graph'] = sorted(actual_json['@graph'], key=lambda entry: entry['@id'])
        expected_json['@graph'] = sorted(expected_json['@graph'], key=lambda entry: entry['@id'])
        assert_equal(actual_json, expected_json)

    def test_write_ro_crate_json_without_funder_ror(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        node_id = 'rvm3q'
        files = [
            [('test.jpg', 'image/jpeg')],
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
                        'grdm-file:creators': [
                            {
                                'number': '22222',
                                'name-ja': '情報太郎',
                                'name-en': 'Taro Joho',
                            }
                        ],
                    }.items()]),
                },
            ],
        }
        project_metadata = {
            'funder': {
                'value': 'FDMA',  # FDMA has no ROR ID
            },
            'japan-grant-number': {
                'value': 'JP123456',
            },
            'project-name-ja': {
                'value': 'テストプロジェクト',
            },
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [project_metadata],
            node_id
        )
        actual_json = json.loads(buf.getvalue())
        # funderIdentifier should not be present
        graph_items = actual_json.get('@graph', [])
        funder_identifiers = [item for item in graph_items if item.get('@type') == 'jpcoar:funderIdentifier']
        logger.info(f'DEBUG: funder_identifiers={funder_identifiers}')
        assert_equal(len(funder_identifiers), 0, 'funderIdentifier should not be created for FDMA (no ROR ID)')
        # But fundingReference should still exist with funderName
        funding_refs = [item for item in graph_items if item.get('@type') == 'PropertyValue' and 'jpcoar:funderName' in str(item)]
        assert_true(len(funding_refs) > 0, 'fundingReference with funderName should still be created')

    def test_write_ro_crate_json_grouped_supporting_files(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'Demo Index'
        node_id = 'sp3av'

        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        with open('addons/weko/scripts/example-manuscript-metadata.json') as sample_file:
            sample_payload = json.load(sample_file)

        files = [[(entry['name'], entry['type']) for entry in group] for group in sample_payload['files']]

        file_metadatas = copy.deepcopy(sample_payload['file_metadatas'])
        for metadata in file_metadatas:
            metadata['items'][0]['schema'] = target_schema._id

        project_metadatas = copy.deepcopy(sample_payload['project_metadatas'])

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            file_metadatas,
            project_metadatas,
            node_id
        )

        actual_json = json.loads(buf.getvalue())
        graph = {item['@id']: item for item in actual_json['@graph'] if '@id' in item}

        # Debug: print manuscript entity keys
        for part_ref in graph['./']['hasPart']:
            part_id = part_ref['@id']
            if part_id.startswith('#dataset-'):
                logger.info(f'Dataset {part_id} keys: {list(graph[part_id].keys())}')

        dataset_root = graph['./']
        assert_true(dataset_root.get('wk:isSplited'))
        assert_equal(dataset_root['@type'], 'Dataset')
        assert_not_in('name', dataset_root)
        assert_not_in('dc:type', dataset_root)

        part_ids = [part['@id'] for part in dataset_root['hasPart']]
        assert_equal(len(part_ids), 3)
        assert_equal(sorted(part_ids), ['#dataset-1', '#dataset-2', '#dataset-3'])

        datasets = [graph[part_id] for part_id in part_ids]
        for dataset in datasets:
            assert_true('@type' not in dataset)

        def dereference(reference):
            assert_true(isinstance(reference, dict) and '@id' in reference)
            assert_in(reference['@id'], graph)
            return graph[reference['@id']]

        def property_entities(entity, key):
            references = entity.get(key)
            if references is None:
                return []
            if isinstance(references, dict):
                references = [references]
            return [dereference(ref) for ref in references]

        def scalar_property_value(entity, key):
            values = property_entities(entity, key)
            assert_true(values)
            return values[0]['value']

        def collect_lang_map(entity, key):
            values = {}
            for value_entity in property_entities(entity, key):
                values[value_entity.get('language')] = value_entity['value']
            return values

        dataset_primary = next(
            dataset for dataset in datasets
            if scalar_property_value(dataset, 'dc:type') == 'journal article'
        )
        datasets_supporting = [
            dataset for dataset in datasets
            if scalar_property_value(dataset, 'dc:type') == 'experimental data'
        ]

        assert_equal(scalar_property_value(dataset_primary, 'dc:type'), 'journal article')
        assert_equal(len(datasets_supporting), 2)
        for dataset_supporting in datasets_supporting:
            assert_equal(scalar_property_value(dataset_supporting, 'dc:type'), 'experimental data')

        assert_equal(
            [part['@id'] for part in dataset_primary['hasPart']],
            ['files/sample-manuscript.pdf']
        )
        # Each supporting dataset now has only one file
        supporting_files = sorted([
            part['@id']
            for dataset_supporting in datasets_supporting
            for part in dataset_supporting['hasPart']
        ])
        assert_equal(supporting_files, ['files/supporting-data-1.csv', 'files/supporting-data-2.csv'])

        assert_equal(dataset_primary['name'], 'MAIN ARTICLE')
        assert_equal(dataset_primary['description'], 'Primary manuscript')

        # Both supporting datasets have the same metadata
        for dataset_supporting in datasets_supporting:
            assert_equal(dataset_supporting['name'], 'SUPPORTING DATA')
            assert_equal(dataset_supporting['description'], 'Supporting dataset')

        name_langs_primary = collect_lang_map(dataset_primary, 'dc:title')
        assert_equal(name_langs_primary['en'], 'MAIN ARTICLE')
        assert_equal(name_langs_primary['ja'], '主論文')

        # Check first supporting dataset (they have identical metadata)
        name_langs_support = collect_lang_map(datasets_supporting[0], 'dc:title')
        assert_equal(name_langs_support['en'], 'SUPPORTING DATA')
        assert_equal(name_langs_support['ja'], '根拠データ')

        desc_langs_support = collect_lang_map(datasets_supporting[0], 'datacite:description')
        assert_equal(desc_langs_support['en'], 'Supporting dataset')
        assert_equal(desc_langs_support['ja'], '論文に関連する根拠データ')

        def assert_references(dataset, key):
            values = property_entities(dataset, key)
            assert_true(values, f'Key \'{key}\' not found or empty in dataset {dataset.get("@id", "unknown")}')

        # Common fields for both manuscript and dataset
        common_reference_keys = [
            'jpcoar:fundingReference',
            'jpcoar:creator',
            'dc:type',
            'dc:title',
            'datacite:date',
        ]

        for key in common_reference_keys:
            assert_references(dataset_primary, key)
            for dataset_supporting in datasets_supporting:
                assert_references(dataset_supporting, key)

        # Manuscript-specific fields
        assert_references(dataset_primary, 'oaire:version')
        assert_references(dataset_primary, 'jpcoar:relation')

        # Dataset-specific fields (check all supporting datasets)
        for dataset_supporting in datasets_supporting:
            assert_references(dataset_supporting, 'datacite:description')
            assert_references(dataset_supporting, 'jpcoar:contributor')
            assert_references(dataset_supporting, 'dc:rights')
            assert_references(dataset_supporting, 'jpcoar:subject')
            assert_references(dataset_supporting, 'dcterms:accessRights')
            assert_references(dataset_supporting, 'jpcoar:relation')

        ro_crate_metadata = graph['ro-crate-metadata.json']
        assert_equal(ro_crate_metadata['about']['@id'], './')

        file_entities = {
            entity['@id']: entity
            for entity in actual_json['@graph']
            if entity.get('@type') == 'File'
        }

        assert_equal(
            set(file_entities.keys()),
            {
                'files/sample-manuscript.pdf',
                'files/supporting-data-1.csv',
                'files/supporting-data-2.csv',
            }
        )
        assert_equal(file_entities['files/sample-manuscript.pdf']['jpcoar:mimeType'], 'application/pdf')
        assert_equal(file_entities['files/sample-manuscript.pdf']['jpcoar:format'], 'preview')
        assert_equal(file_entities['files/supporting-data-1.csv']['jpcoar:mimeType'], 'text/csv')
        assert_equal(file_entities['files/supporting-data-1.csv']['jpcoar:format'], 'preview')
        assert_equal(file_entities['files/supporting-data-2.csv']['jpcoar:mimeType'], 'text/csv')
        assert_equal(file_entities['files/supporting-data-2.csv']['jpcoar:format'], 'preview')

        # Manuscript has links to both supporting datasets
        itemlinks_primary = property_entities(dataset_primary, 'wk:itemLinks')
        assert_equal(len(itemlinks_primary), 2)
        for link in itemlinks_primary:
            assert_equal(link['@type'], 'PropertyValue')
            assert_equal(link['value'], 'isSupplementedBy')
            assert_in(link['identifier'], [ds['@id'] for ds in datasets_supporting])

        # Each supporting dataset has a link back to the manuscript
        for dataset_supporting in datasets_supporting:
            itemlinks_supporting = property_entities(dataset_supporting, 'wk:itemLinks')
            assert_equal(len(itemlinks_supporting), 1)
            assert_equal(itemlinks_supporting[0]['@type'], 'PropertyValue')
            assert_equal(itemlinks_supporting[0]['value'], 'isSupplementTo')
            assert_equal(itemlinks_supporting[0]['identifier'], dataset_primary['@id'])

        version_entities = property_entities(dataset_primary, 'oaire:version')
        assert_equal(len(version_entities), 1)
        version = version_entities[0]
        assert_equal(version['@type'], 'PropertyValue')
        assert_equal(version['value'], 'AM')
        assert_equal(version['rdf:resource'], 'http://purl.org/coar/version/c_ab4af688f83e57aa')
        assert_equal(version['itemReviewed'], 'Peer reviewed')

        # Test jpcoar:relation relationType for AM version (should be isVersionOf)
        relation_entities = property_entities(dataset_primary, 'jpcoar:relation')
        # Find the relation with published article DOI (grdm-file:doi)
        doi_relation = next(
            (rel for rel in relation_entities
             if rel.get('jpcoar:relationType') in ['isVersionOf', 'isIdenticalTo']),
            None
        )
        assert_true(doi_relation is not None, 'DOI relation not found in jpcoar:relation')
        assert_equal(doi_relation['jpcoar:relationType'], 'isVersionOf')  # AM version should use isVersionOf

        # Verify the related identifier contains the DOI
        related_id_entities = property_entities(doi_relation, 'jpcoar:relatedIdentifier')
        assert_equal(len(related_id_entities), 1)
        related_id = related_id_entities[0]
        assert_equal(related_id['identifierType'], 'DOI')
        assert_true('10.1234/example.manuscript.2025' in related_id['value'])

    def test_manuscript_relation_type_vor(self):
        """Test jpcoar:relation relationType for VoR version manuscripts (should be isIdenticalTo)"""
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'Test Index'
        node_id = 'testnode'
        files = [[('manuscript.pdf', 'application/pdf')]]

        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,
                    'data': {
                        'grdm-file:title-en': {'value': 'VoR Manuscript'},
                        'grdm-file:file-type': {'value': 'manuscript'},
                        'grdm-file:version': {'value': 'VoR'},
                        'grdm-file:reviewed': {'value': 'yes'},
                        'grdm-file:doi': {'value': '10.1234/example.vor.2025'},
                        'grdm-file:manuscript-type': {'value': 'journal article'},
                        'grdm-file:date-published': {'value': '2025-01-01'},
                        'grdm-file:authors': {
                            'value': [
                                {
                                    'number': 'A001',
                                    'name-ja-last': 'テスト',
                                    'name-ja-middle': '',
                                    'name-ja-first': '太郎',
                                    'name-en-last': 'Test',
                                    'name-en-middle': '',
                                    'name-en-first': 'Taro',
                                }
                            ]
                        },
                    },
                },
            ],
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [],
            node_id
        )

        actual_json = json.loads(buf.getvalue())
        graph = {item['@id']: item for item in actual_json['@graph'] if '@id' in item}

        def dereference(reference):
            return graph[reference['@id']]

        def property_entities(entity, key):
            references = entity.get(key)
            if references is None:
                return []
            if isinstance(references, dict):
                references = [references]
            return [dereference(ref) for ref in references]

        dataset_root = graph['./']

        # Get jpcoar:relation entities
        relation_entities = property_entities(dataset_root, 'jpcoar:relation')
        assert_true(len(relation_entities) > 0, 'No jpcoar:relation found')

        # Find the DOI relation
        doi_relation = next(
            (rel for rel in relation_entities
             if rel.get('jpcoar:relationType') in ['isVersionOf', 'isIdenticalTo']),
            None
        )
        assert_true(doi_relation is not None, 'DOI relation not found')
        assert_equal(doi_relation['jpcoar:relationType'], 'isIdenticalTo')  # VoR version should use isIdenticalTo

        # Verify the related identifier contains the VoR DOI
        related_id_entities = property_entities(doi_relation, 'jpcoar:relatedIdentifier')
        assert_equal(len(related_id_entities), 1)
        related_id = related_id_entities[0]
        assert_equal(related_id['identifierType'], 'DOI')
        assert_true('10.1234/example.vor.2025' in related_id['value'])

    def test_write_csv_manuscript_version_am(self):
        """Test CSV output for manuscript with version type AM and peer reviewed status"""
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        files = [
            [('manuscript.pdf', 'application/pdf')],
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
                            'value': 'Test Manuscript',
                        },
                        'grdm-file:file-type': {
                            'value': 'manuscript',
                        },
                        'grdm-file:manuscript-type': {
                            'value': 'journal article',
                        },
                        'grdm-file:version': {
                            'value': 'AM',
                        },
                        'grdm-file:reviewed': {
                            'value': 'yes',
                        },
                        'grdm-file:date-published': {
                            'value': '2025-01-01',
                        },
                        'grdm-file:authors': {
                            'value': [
                                {
                                    'number': 'A001',
                                    'name-ja-last': 'テスト',
                                    'name-ja-middle': '',
                                    'name-ja-first': '太郎',
                                    'name-en-last': 'Test',
                                    'name-en-middle': '',
                                    'name-en-first': 'Taro',
                                }
                            ]
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

        # Find version_type15 related fields in the CSV
        props = _transpose(lines[1::])[::-1]
        props_list = list(props)

        # Search for subitem_version_type
        version_type_found = False
        version_resource_found = False
        peer_reviewed_found = False

        for prop in props_list:
            if '.metadata.item_30002_version_type15.subitem_version_type' in prop[0]:
                assert_equal(prop[-1], 'AM')
                version_type_found = True
            elif '.metadata.item_30002_version_type15.subitem_version_resource' in prop[0]:
                assert_equal(prop[-1], 'http://purl.org/coar/version/c_ab4af688f83e57aa')
                version_resource_found = True
            elif '.metadata.item_30002_version_type15.subitem_peer_reviewed' in prop[0]:
                assert_equal(prop[-1], 'Peer reviewed')
                peer_reviewed_found = True

        assert_true(version_type_found, 'subitem_version_type not found in CSV')
        assert_true(version_resource_found, 'subitem_version_resource not found in CSV')
        assert_true(peer_reviewed_found, 'subitem_peer_reviewed not found in CSV')

    def test_manuscript_file_access_rights_defaults_to_open_access(self):
        """Test that manuscript files default to open_access when grdm-file:access-rights is not set"""
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'Test Index'
        node_id = 'testnode'
        files = [[('manuscript.pdf', 'application/pdf')]]

        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        # Manuscript metadata WITHOUT grdm-file:access-rights
        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,
                    'data': {
                        'grdm-file:title-en': {'value': 'Test Manuscript'},
                        'grdm-file:file-type': {'value': 'manuscript'},
                        'grdm-file:version': {'value': 'VoR'},
                        'grdm-file:reviewed': {'value': 'yes'},
                        'grdm-file:doi': {'value': '10.1234/example.2025'},
                        'grdm-file:manuscript-type': {'value': 'journal article'},
                        'grdm-file:date-published': {'value': '2025-01-01'},
                        'grdm-file:authors': {
                            'value': [
                                {
                                    'number': 'A001',
                                    'name-ja-last': 'テスト',
                                    'name-ja-middle': '',
                                    'name-ja-first': '太郎',
                                    'name-en-last': 'Test',
                                    'name-en-middle': '',
                                    'name-en-first': 'Taro',
                                }
                            ]
                        },
                        # Note: grdm-file:access-rights is NOT set
                    },
                },
            ],
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [],
            node_id
        )

        actual_json = json.loads(buf.getvalue())

        # Find the File entity
        file_entities = [
            entity for entity in actual_json['@graph']
            if entity.get('@type') == 'File'
        ]
        assert_equal(len(file_entities), 1)
        file_entity = file_entities[0]

        # Manuscript should default to open_access when access-rights is not set
        assert_equal(
            file_entity.get('dcterms:accessRights'),
            'open_access',
            'Manuscript file should default to open_access when grdm-file:access-rights is not set'
        )

    def test_dataset_file_access_rights_defaults_to_open_no(self):
        """Test that dataset files default to open_no when grdm-file:access-rights is not set"""
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'Test Index'
        node_id = 'testnode'
        files = [[('data.csv', 'text/csv')]]

        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        # Dataset metadata WITHOUT grdm-file:access-rights
        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,
                    'data': {
                        'grdm-file:title-en': {'value': 'Test Dataset'},
                        'grdm-file:file-type': {'value': 'dataset'},
                        'grdm-file:data-type': {'value': 'experimental data'},
                        'grdm-file:creators': {
                            'value': [
                                {
                                    'number': 'D001',
                                    'name-ja': 'テスト太郎',
                                    'name-en': 'Taro Test',
                                }
                            ]
                        },
                        # Note: grdm-file:access-rights is NOT set
                    },
                },
            ],
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            [file_metadata],
            [],
            node_id
        )

        actual_json = json.loads(buf.getvalue())

        # Find the File entity
        file_entities = [
            entity for entity in actual_json['@graph']
            if entity.get('@type') == 'File'
        ]
        assert_equal(len(file_entities), 1)
        file_entity = file_entities[0]

        # Dataset should default to open_no when access-rights is not set
        assert_equal(
            file_entity.get('dcterms:accessRights'),
            'open_no',
            'Dataset file should default to open_no when grdm-file:access-rights is not set'
        )

    def test_write_ro_crate_json_mebyo_empty_files(self):
        """Test that MEBYO schema can generate RO-Crate without files (metadata only).

        When allow_empty_files is enabled in the mapping, the RO-Crate should be
        generated with project metadata only, without requiring file metadata.
        """
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '2000'
        index.title = 'MEBYO Test Index'
        node_id = 'mebyotest'

        target_schema = RegistrationSchema.objects \
            .filter(name='ムーンショット目標2データベース（未病DB）のメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        # No files - empty lists
        files = []
        file_metadatas = []

        # Project metadata with minimal required fields for MEBYO schema
        project_metadata = {
            'title-of-dataset': {
                'value': 'テストデータセット',
            },
            'title-of-dataset-en': {
                'value': 'Test Dataset',
            },
            'purpose-of-experiment': {
                'value': '実験目的の説明',
            },
            'purpose-of-experiment-en': {
                'value': 'Description of experiment purpose',
            },
            'data-creator': {
                'value': '国立情報学研究所',
            },
            'data-manager': {
                'value': 'テスト管理者',
            },
            'grdm-files': {
                'value': [],  # No files
            },
        }

        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            file_metadatas,
            [project_metadata],
            node_id
        )

        actual_json = json.loads(buf.getvalue())
        graph = {item['@id']: item for item in actual_json['@graph'] if '@id' in item}

        # Root dataset entity should exist
        assert_in('./', graph, 'Root dataset entity should exist')
        root = graph['./']
        assert_equal(root['@type'], ['Dataset', 'rdm:Dataset'])

        # ro-crate-metadata.json entity should exist
        assert_in('ro-crate-metadata.json', graph, 'RO-Crate metadata entity should exist')
        ro_crate_meta = graph['ro-crate-metadata.json']
        assert_equal(ro_crate_meta['about']['@id'], './')

        # Project metadata should be reflected
        assert_equal(root['name'], 'Test Dataset')
        assert_equal(root['description'], 'Description of experiment purpose')

    def test_write_ro_crate_json_mebyo_with_additional_metadata_files(self):
        """Test MEBYO schema with choose-additional-metadata containing files.

        Regression test for TypeError in _flatten_json_ld_root when hasPart
        contains File objects with 'name' as a string (filename) rather than
        a list of dicts (as with Person objects).
        """
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '2000'
        index.title = 'MEBYO Test Index'
        node_id = 'mebyotest'

        target_schema = RegistrationSchema.objects \
            .filter(name='ムーンショット目標2データベース（未病DB）のメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        # Files from choose-additional-metadata
        files = [[('text1.csv', 'text/csv')]]
        file_metadatas = []  # MEBYO uses allow_empty_files

        # Project metadata based on real production data
        project_metadata = {
            'title-of-dataset': {
                'value': '未病DBメタデータテスト',
            },
            'title-of-dataset-en': {
                'value': 'Mebyo DB Metadata Test',
            },
            'purpose-of-experiment': {
                'value': 'test',
            },
            'purpose-of-experiment-en': {
                'value': 'test purpose',
            },
            'data-creator': {
                'value': '[{"name":"test","name-en":"test"}]',
            },
            'data-manager': {
                'value': '[{"name":"test"}]',
            },
            'choose-additional-metadata': {
                'value': '[{"path":"osfstorage/text1.csv","urlpath":"","metadata":{}}]',
            },
            'date-registered-in-metadata': {
                'value': '2026-02-05',
            },
            'date-updated-in-metadata': {
                'value': '2026-02-05',
            },
            'access-rights': {
                'value': '公開|open access',
            },
            'dataset-research-field': {
                'value': '自然科学一般|Natural Science',
            },
            'project-name': {
                'value': 'MS2合原PJ|MS2 Aihara PJ',
            },
            'keywords': {
                'value': '[{"filename":"test"}]',
            },
            'grdm-files': {
                'value': '',
            },
        }

        # This should NOT raise TypeError: string indices must be integers
        schema.write_ro_crate_json(
            self.user,
            buf,
            index,
            files,
            target_schema._id,
            file_metadatas,
            [project_metadata],
            node_id
        )

        actual_json = json.loads(buf.getvalue())
        graph = {item['@id']: item for item in actual_json['@graph'] if '@id' in item}

        # Root dataset entity should exist
        assert_in('./', graph, 'Root dataset entity should exist')
        root = graph['./']
        assert_equal(root['@type'], ['Dataset', 'rdm:Dataset'])

        # ro-crate-metadata.json entity should exist
        assert_in('ro-crate-metadata.json', graph, 'RO-Crate metadata entity should exist')
        ro_crate_meta = graph['ro-crate-metadata.json']
        assert_equal(ro_crate_meta['about']['@id'], './')

        # Project metadata should be reflected
        assert_equal(root['name'], 'Mebyo DB Metadata Test')
        assert_equal(root['description'], 'test purpose')

        # hasPart should contain File reference
        assert_in('hasPart', root)
        has_part = root['hasPart']
        assert_true(isinstance(has_part, list))

        # hasPart should not contain duplicates
        has_part_ids = [part['@id'] for part in has_part]
        assert_equal(
            len(has_part_ids),
            len(set(has_part_ids)),
            f'hasPart contains duplicate entries: {has_part_ids}'
        )

        # File entity should exist with name as string (not list)
        file_entities = [
            item for item in actual_json['@graph']
            if item.get('@type') == 'File'
        ]
        assert_true(len(file_entities) > 0, 'File entity should exist')
        file_entity = file_entities[0]
        assert_equal(file_entity['name'], 'text1.csv')
        assert_true(isinstance(file_entity['name'], str), 'File name should be a string')

    def test_write_ro_crate_json_erad_requires_files(self):
        """Test that e-Rad schema (公的資金) requires files and raises error when empty.

        The e-Rad schema should NOT allow empty files, as file metadata is required
        for public funding data submissions.
        """
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'Test Index'
        node_id = 'testnode'

        target_schema = RegistrationSchema.objects \
            .filter(name='公的資金による研究データのメタデータ登録') \
            .order_by('-schema_version') \
            .first()

        # No files - empty lists
        files = []
        file_metadatas = []
        project_metadata = {
            'funder': {'value': 'JST'},
            'japan-grant-number': {'value': 'JP123456'},
        }

        # Should raise ValueError because e-Rad schema requires files
        with assert_raises(ValueError) as context:
            schema.write_ro_crate_json(
                self.user,
                buf,
                index,
                files,
                target_schema._id,
                file_metadatas,
                [project_metadata],
                node_id
            )

        assert_in(
            'No file metadata available',
            str(context.exception),
            'Error message should indicate missing file metadata'
        )
