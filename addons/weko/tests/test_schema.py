# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import mock
from mock import call
from nose.tools import *  # noqa

from osf.models.metaschema import RegistrationSchema
from tests.base import OsfTestCase

from addons.weko import schema


logger = logging.getLogger(__name__)


def _transpose(lines):
    assert len(set([len(l) for l in lines])) == 1, set([len(l) for l in lines])
    return [[row[i] for row in lines] for i in range(len(lines[0]))]


class TestWEKOSchema(OsfTestCase):

    def test_write_csv_minimal(self):
        buf = io.StringIO()
        index = mock.MagicMock()
        index.identifier = '1000'
        index.title = 'TITLE'
        files = [
            ('test.jpg', 'image/jpeg'),
        ]
        target_schema = RegistrationSchema.objects.get(name='公的資金による研究データのメタデータ登録')
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
            buf,
            index,
            files,
            target_schema._id,
            file_metadata,
            None,
        )

        logger.info(f'CSV: {buf.getvalue()}')
        buf.seek(0)
        reader = csv.reader(buf)
        lines = list(reader)
        assert_equal(len(lines), 6)
        assert_equal(lines[0], [
            '#ItemType',
            'デフォルトアイテムタイプ（フル）(15)',
            'https://localhost:8443/items/jsonschema/15',
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
            ['.file_path[0]', '.ファイルパス[0]', '', 'Allow Multiple', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617605131499[0].filename', 'File[0].表示名', '', 'Allow Multiple', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617605131499[0].format', 'File[0].フォーマット', '', 'Allow Multiple', 'image/jpeg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[0].subitem_1551255647225', '', '', '', 'ENGLISH TITLE'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[0].subitem_1551255648112', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description_type', '', '', '', 'Other'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description', '', '', '', '日本語説明'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617258105262.resourcetype', '', '', '', 'dataset'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.pubdate', '', '', '', '2023-10-13'],
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
            ['.feedback_mail[0]', '.FEEDBACK_MAIL[0]', '', 'Allow Multiple', ''],
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
            ('test.jpg', 'image/jpeg'),
        ]
        target_schema = RegistrationSchema.objects.get(name='公的資金による研究データのメタデータ登録')
        file_metadata = {
            'items': [
                {
                    'schema': target_schema._id,                   
                    'data': dict([(k, {
                        'value': v,
                    })for k, v in {
                        "grdm-file:data-number": "00001",
                        "grdm-file:title-en": "TEST DATA",
                        "grdm-file:title-ja": "テストデータ",
                        "grdm-file:date-issued-updated": "2023-09-15",
                        "grdm-file:data-description-ja": "テスト説明",
                        "grdm-file:data-description-en": "TEST DESCRIPTION",
                        "grdm-file:data-research-field": "189",
                        "grdm-file:data-type": "experimental data",
                        "grdm-file:file-size": "29.9KB",
                        "grdm-file:data-policy-free": "free",
                        "grdm-file:data-policy-license": "CC0",
                        "grdm-file:data-policy-cite-ja": "ライセンスのテスト",
                        "grdm-file:data-policy-cite-en": "Test for license",
                        "grdm-file:access-rights": "restricted access",
                        "grdm-file:available-date": "",
                        "grdm-file:repo-information-ja": "テストリポジトリ",
                        "grdm-file:repo-information-en": "Test Repository",
                        "grdm-file:repo-url-doi-link": "http://localhost:5000/q3gnm/files/osfstorage/650e68f8c00e45055fc9e0ac",
                        "grdm-file:creators": "[{\"number\":\"22222\",\"name_ja\":\"情報太郎\",\"name_en\":\"Taro Joho\"}]",
                        "grdm-file:hosting-inst-ja": "国立情報学研究所",
                        "grdm-file:hosting-inst-en": "National Institute of Informatics",
                        "grdm-file:hosting-inst-id": "https://ror.org/04ksd4g47",
                        "grdm-file:data-man-number": "11111",
                        "grdm-file:data-man-name-ja": "情報花子",
                        "grdm-file:data-man-name-en": "Hanako Joho",
                        "grdm-file:data-man-org-ja": "国立情報学研究所",
                        "grdm-file:data-man-org-en": "National Institute of Informatics",
                        "grdm-file:data-man-address-ja": "一ツ橋",
                        "grdm-file:data-man-address-en": "Hitotsubashi",
                        "grdm-file:data-man-tel": "XX-XXXX-XXXX",
                        "grdm-file:data-man-email": "dummy@test.rcos.nii.ac.jp",
                        "grdm-file:remarks-ja": "コメント",
                        "grdm-file:remarks-en": "Comment",
                        "grdm-file:metadata-access-rights": "closed access",
                    }.items()]),
                },
            ],
        }

        schema.write_csv(
            buf,
            index,
            files,
            target_schema._id,
            file_metadata,
            None,
        )

        logger.info(f'CSV: {buf.getvalue()}')
        buf.seek(0)
        reader = csv.reader(buf)
        lines = list(reader)
        assert_equal(len(lines), 6)
        logger.info(repr(lines))
        assert_equal(lines[0], [
            '#ItemType',
            'デフォルトアイテムタイプ（フル）(15)',
            'https://localhost:8443/items/jsonschema/15',
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
            ['.file_path[0]', '.ファイルパス[0]', '', 'Allow Multiple', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617605131499[0].filename', 'File[0].表示名', '', 'Allow Multiple', 'test.jpg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617605131499[0].format', 'File[0].フォーマット', '', 'Allow Multiple', 'image/jpeg'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617353299429[0].subitem_1522306207484', '', '', '', 'isIdenticalTo'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617353299429[0].subitem_1522306287251.subitem_1522306382014', '', '', '', 'Local'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617353299429[0].subitem_1522306287251.subitem_1522306436033', '', '', '', '00001'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[0].subitem_1551255647225', '', '', '', 'テストデータ'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[0].subitem_1551255648112', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[1].subitem_1551255647225', '', '', '', 'TEST DATA'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186331708[1].subitem_1551255648112', '', '', '', 'en'],
        )

        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description_type', '', '', '', 'Other'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description', '', '', '', 'テスト説明'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[0].subitem_description_language', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[1].subitem_description_type', '', '', '', 'Other'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[1].subitem_description', '', '', '', 'TEST DESCRIPTION'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186626617[1].subitem_description_language', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[0].subitem_1522300014469', '', '', '', 'Other'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[0].subitem_1523261968819', '', '', '', 'ライフサイエンス'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[0].subitem_1522299896455', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[1].subitem_1522300014469', '', '', '', 'Other'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[1].subitem_1523261968819', '', '', '', 'Life Science'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186609386[1].subitem_1522299896455', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617258105262.resourcetype', '', '', '', 'experimental data'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186499011[0].subitem_1522651041219', '', '', '', 'CC0 1.0 Universal (ライセンスのテスト) (無償)'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186499011[0].subitem_1522650717957', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186499011[1].subitem_1522651041219', '', '', '', 'CC0 1.0 Universal (Test for license) (free)'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186499011[1].subitem_1522650717957', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186476635.subitem_1522299639480', '', '', '', 'restricted access'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186783814[0].subitem_identifier_uri', '', '', '', 'http://localhost:5000/q3gnm/files/osfstorage/650e68f8c00e45055fc9e0ac'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186783814[0].subitem_identifier_type', '', '', '', 'URI'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].nameIdentifiers[0].nameIdentifierURI', '', '', '', '22222'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'e-Rad_Researcher'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].creatorNames[0].creatorName', '', '', '', '情報太郎'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].creatorNames[0].creatorNameLang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].creatorNames[1].creatorName', '', '', '', 'Taro Joho'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617186419668[0].creatorNames[1].creatorNameLang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].contributorType', '', '', '', 'HostingInstitution'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].contributorNames[0].contributorName', '', '', '', '国立情報学研究所'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].contributorNames[0].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].contributorNames[1].contributorName', '', '', '', 'National Institute of Informatics'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].contributorNames[1].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].nameIdentifiers[0].nameIdentifierURI', '', '', '', 'https://ror.org/04ksd4g47'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[0].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'ROR'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].contributorType', '', '', '', 'DataManager'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].nameIdentifiers[0].nameIdentifierURI', '', '', '', '11111'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].nameIdentifiers[0].nameIdentifierScheme', '', '', '', 'e-Rad_Researcher'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].contributorNames[0].contributorName', '', '', '', '情報花子'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].contributorNames[0].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].contributorNames[1].contributorName', '', '', '', 'Hanako Joho'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[1].contributorNames[1].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[2].contributorType', '', '', '', 'ContactPerson'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[2].contributorNames[0].contributorName', '', '', '', '国立情報学研究所 一ツ橋 XX-XXXX-XXXX dummy@test.rcos.nii.ac.jp'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[2].contributorNames[0].lang', '', '', '', 'ja'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[2].contributorNames[1].contributorName', '', '', '', 'National Institute of Informatics Hitotsubashi'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.item_1617349709064[2].contributorNames[1].lang', '', '', '', 'en'],
        )
        assert_equal(
            props.pop(),
            ['.metadata.pubdate', '', '', '', '2023-10-13'],
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
            ['.feedback_mail[0]', '.FEEDBACK_MAIL[0]', '', 'Allow Multiple', ''],
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
