# -*- coding: utf-8 -*-
"""
Tests for JaLC suggestion module
"""
import pytest
import responses
import json
from addons.metadata.suggestions.jalc import (
    valid_jalc_key,
    suggestion_jalc,
    extract_jalc_metadata,
    extract_person_data,
    extract_dates
)
from addons.metadata.suggestion import (
    valid_suggestion_key,
    suggestion_metadata
)


class TestValidJalcKey:

    def test_valid_key(self):
        assert valid_jalc_key('jalc:doi') is True
        assert valid_jalc_key('jalc:article') is True

    def test_invalid_key(self):
        assert valid_jalc_key('crossref:doi') is False
        assert valid_jalc_key('doi:jalc') is False
        assert valid_jalc_key('jalc') is False


class TestSuggestionJalc:

    @responses.activate
    def test_successful_doi_lookup(self):
        doi = '10.24602/sjpr.67.1_109'
        mock_response = {
            'status': 'OK',
            'apiType': 'doi',
            'apiVersion': 'v1',
            'message': {
                'total': 1,
                'rows': 1,
                'totalPages': 1,
                'page': 1
            },
            'data': {
                'doi': doi,
                'title_list': [
                    {'lang': 'ja', 'title': 'テスト記事'},
                    {'lang': 'en', 'title': 'Test Article'}
                ],
                'creator_list': [
                    {
                        'sequence': '1',
                        'type': 'person',
                        'names': [
                            {'lang': 'ja', 'last_name': '山田', 'first_name': '太郎'},
                            {'lang': 'en', 'last_name': 'Yamada', 'first_name': 'Taro'}
                        ]
                    }
                ],
                'publication_date': {
                    'publication_year': '2024',
                    'publication_month': '3'
                }
            }
        }

        responses.add(
            responses.GET,
            'https://api.japanlinkcenter.org/v2/dois/10.24602%2Fsjpr.67.1_109',
            json=mock_response,
            status=200
        )

        result = suggestion_jalc('jalc:doi', doi)

        assert len(result) == 1
        assert result[0]['key'] == 'jalc:doi'
        assert result[0]['value']['doi'] == doi
        assert result[0]['value']['title'] == 'Test Article'
        assert result[0]['value']['title_ja'] == 'テスト記事'

    @responses.activate
    def test_doi_not_found(self):
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            'https://api.japanlinkcenter.org/v2/dois/10.1234%2Fnotfound',
            status=404
        )

        result = suggestion_jalc('jalc:doi', doi)
        assert result == []

    @responses.activate
    def test_api_error_status(self):
        doi = '10.24602/error'
        mock_response = {
            'status': 'ERROR',
            'message': {
                'errors': {
                    'message': 'Error occurred',
                    'statusCode': '500'
                }
            }
        }

        responses.add(
            responses.GET,
            'https://api.japanlinkcenter.org/v2/dois/10.24602%2Ferror',
            json=mock_response,
            status=200
        )

        result = suggestion_jalc('jalc:doi', doi)
        assert result == []

    def test_empty_keyword(self):
        result = suggestion_jalc('jalc:doi', '')
        assert result == []

    def test_invalid_doi_format(self):
        result = suggestion_jalc('jalc:doi', 'not-a-doi')
        assert result == []

    def test_doi_cleaning(self):
        # Test that various DOI formats are cleaned properly
        test_cases = [
            ('https://doi.org/10.24602/sjpr.67.1_109', '10.24602/sjpr.67.1_109'),
            ('http://dx.doi.org/10.24602/sjpr.67.1_109', '10.24602/sjpr.67.1_109'),
            ('doi:10.24602/sjpr.67.1_109', '10.24602/sjpr.67.1_109'),
            ('10.24602/sjpr.67.1_109', '10.24602/sjpr.67.1_109'),
        ]

        for input_doi, expected_doi in test_cases:
            # Would need to mock the actual API call to test this properly
            pass


class TestExtractJalcMetadata:

    def test_basic_metadata(self):
        jalc_data = {
            'doi': '10.24602/sjpr.67.1_109',
            'title_list': [
                {'lang': 'ja', 'title': 'テスト記事', 'subtitle': 'サブタイトル'},
                {'lang': 'en', 'title': 'Test Article', 'subtitle': 'A Subtitle'}
            ],
            'journal_title_name_list': [
                {'lang': 'ja', 'journal_title_name': '心理学評論'},
                {'lang': 'en', 'journal_title_name': 'Japanese Psychological Review'}
            ],
            'volume': '67',
            'issue': '1',
            'first_page': '109',
            'last_page': '124',
            'publisher_list': [
                {'lang': 'ja', 'publisher_name': '心理学評論刊行会'},
                {'lang': 'en', 'publisher_name': 'Japanese Psychological Review'}
            ],
            'content_type': 'JA'
        }

        result = extract_jalc_metadata(jalc_data)

        assert result['doi'] == '10.24602/sjpr.67.1_109'
        assert result['title'] == 'Test Article'
        assert result['title_ja'] == 'テスト記事'
        assert result['subtitle'] == 'A Subtitle'
        assert result['subtitle_ja'] == 'サブタイトル'
        assert result['journal_title'] == 'Japanese Psychological Review'
        assert result['journal_title_ja'] == '心理学評論'
        assert result['volume'] == '67'
        assert result['issue'] == '1'
        assert result['page'] == '109-124'
        assert result['page_start'] == '109'
        assert result['page_end'] == '124'
        assert result['publisher'] == 'Japanese Psychological Review'
        assert result['publisher_ja'] == '心理学評論刊行会'
        assert result['content_type'] == 'JA'
        assert result['manuscript_type_common_metadata_format'] == 'journal article'

    def test_authors_extraction(self):
        jalc_data = {
            'creator_list': [
                {
                    'sequence': '1',
                    'type': 'person',
                    'names': [
                        {'lang': 'ja', 'last_name': '山田', 'first_name': '太郎'},
                        {'lang': 'en', 'last_name': 'Yamada', 'first_name': 'Taro'}
                    ],
                    'researcher_id_list': [
                        {'type': 'ORCID', 'id_code': '0000-0000-0000-0001'},
                        {'type': 'e-Rad', 'id_code': '12345678'}
                    ],
                    'affiliation_list': [
                        {
                            'affiliation_name_list': [
                                {'lang': 'ja', 'affiliation_name': '東京大学'},
                                {'lang': 'en', 'affiliation_name': 'The University of Tokyo'}
                            ]
                        }
                    ]
                },
                {
                    'sequence': '2',
                    'type': 'person',
                    'names': [
                        {'lang': 'ja', 'last_name': '佐藤', 'first_name': '花子'},
                        {'lang': 'en', 'last_name': 'Sato', 'first_name': 'Hanako'}
                    ]
                }
            ]
        }

        result = extract_jalc_metadata(jalc_data)

        assert len(result['authors']) == 2

        # First author
        assert result['authors'][0]['name_ja'] == {
            'last': '山田',
            'middle': '',
            'first': '太郎'
        }
        assert result['authors'][0]['name_en'] == {
            'last': 'Yamada',
            'middle': '',
            'first': 'Taro'
        }
        assert result['authors'][0]['orcid'] == '0000-0000-0000-0001'
        assert result['authors'][0]['erad'] == '12345678'
        assert result['authors'][0]['affiliations'][0]['name'] == 'The University of Tokyo'
        assert result['authors'][0]['affiliations'][0]['name_ja'] == '東京大学'

        # Common metadata format
        assert len(result['authors_common_metadata_format']) == 2
        assert result['authors_common_metadata_format'][0]['name-ja'] == {
            'last': '山田',
            'middle': '',
            'first': '太郎'
        }
        assert result['authors_common_metadata_format'][0]['name-en'] == {
            'last': 'Yamada',
            'middle': '',
            'first': 'Taro'
        }
        # Check affiliation in common metadata format
        assert 'affiliation-name-ja' in result['authors_common_metadata_format'][0]
        assert result['authors_common_metadata_format'][0]['affiliation-name-ja'] == '東京大学'
        assert 'affiliation-name-en' in result['authors_common_metadata_format'][0]
        assert result['authors_common_metadata_format'][0]['affiliation-name-en'] == 'The University of Tokyo'

    def test_dates_extraction(self):
        jalc_data = {
            'publication_date': {
                'publication_year': '2024',
                'publication_month': '3',
                'publication_day': '15'
            },
            'date_list': [
                {'type': 'Issued', 'date': '2024-03-15'},
                {'type': 'Created', 'date': '2024-01-10'},
                {'type': 'Updated', 'date': '2024-03-01'}
            ],
            'advance_date': '2024-02-01'
        }

        result = extract_jalc_metadata(jalc_data)

        assert result['publication_date'] == '2024-03-15'
        assert result['publication_year'] == '2024'
        assert result['publication_year_month'] == '2024-03'
        assert result['issued'] == '2024-03-15'
        assert result['created'] == '2024-01-10'
        assert result['updated'] == '2024-03-01'
        assert result['advance_date'] == '2024-02-01'

    def test_funding_extraction(self):
        jalc_data = {
            'fund_list': [
                {
                    'funder_name': [
                        {'lang': 'ja', 'funder_name': '日本学術振興会'},
                        {'lang': 'en', 'funder_name': 'Japan Society for the Promotion of Science'}
                    ],
                    'award_number_group_list': [
                        {
                            'award_number_list': [
                                {'award_number': '21K12345'},
                                {'award_number': '22K67890'}
                            ]
                        }
                    ]
                }
            ]
        }

        result = extract_jalc_metadata(jalc_data)

        assert len(result['funders']) == 1
        assert result['funders'][0]['name'] == 'Japan Society for the Promotion of Science'
        assert result['funders'][0]['name_ja'] == '日本学術振興会'
        assert result['funders'][0]['award'] == ['21K12345', '22K67890']

    def test_keywords_extraction(self):
        jalc_data = {
            'keyword_list': [
                {'keyword': '心理学', 'lang': 'ja'},
                {'keyword': 'Psychology', 'lang': 'en'},
                {'keyword': '実験', 'lang': 'ja'}
            ]
        }

        result = extract_jalc_metadata(jalc_data)

        assert 'keywords' in result
        assert len(result['keywords']) == 3
        assert '心理学' in result['keywords']
        assert 'Psychology' in result['keywords']
        assert '実験' in result['keywords']

    def test_empty_jalc_data(self):
        result = extract_jalc_metadata({})

        assert result == {'authors': [], 'authors_common_metadata_format': []}

    def test_manuscript_type_mapping(self):
        """Test manuscript type mapping to common metadata format"""
        # Test journal article
        jalc_data = {'content_type': 'JA'}
        result = extract_jalc_metadata(jalc_data)
        assert result['manuscript_type_common_metadata_format'] == 'journal article'
        assert result['content_type'] == 'JA'

        # Test unmapped type (GD = General Data)
        jalc_data = {'content_type': 'GD'}
        result = extract_jalc_metadata(jalc_data)
        assert 'manuscript_type_common_metadata_format' not in result
        assert result['content_type'] == 'GD'  # Original type should still be preserved

        # Test unknown type
        jalc_data = {'content_type': 'XX'}
        result = extract_jalc_metadata(jalc_data)
        assert 'manuscript_type_common_metadata_format' not in result
        assert result['content_type'] == 'XX'

        # Test missing content_type
        jalc_data = {}
        result = extract_jalc_metadata(jalc_data)
        assert 'manuscript_type_common_metadata_format' not in result
        assert 'content_type' not in result


class TestExtractPersonData:

    def test_full_person_data(self):
        person = {
            'sequence': '1',
            'type': 'person',
            'names': [
                {'lang': 'ja', 'last_name': '山田', 'first_name': '太郎'},
                {'lang': 'en', 'last_name': 'Yamada', 'first_name': 'Taro'}
            ],
            'researcher_id_list': [
                {'type': 'ORCID', 'id_code': '0000-0000-0000-0001'},
                {'type': 'e-Rad', 'id_code': '12345678'}
            ],
            'affiliation_list': [
                {
                    'affiliation_name_list': [
                        {'lang': 'ja', 'affiliation_name': '東京大学'},
                        {'lang': 'en', 'affiliation_name': 'The University of Tokyo'}
                    ]
                }
            ]
        }

        result = extract_person_data(person)

        assert result['type'] == 'person'
        assert result['sequence'] == '1'
        assert result['name_ja'] == {
            'last': '山田',
            'middle': '',
            'first': '太郎'
        }
        assert result['name_en'] == {
            'last': 'Yamada',
            'middle': '',
            'first': 'Taro'
        }
        assert result['name_ja_str'] == '山田 太郎'
        assert result['name_en_str'] == 'Taro Yamada'
        assert result['orcid'] == '0000-0000-0000-0001'
        assert result['erad'] == '12345678'
        assert len(result['affiliations']) == 1
        assert result['affiliations'][0]['name'] == 'The University of Tokyo'
        assert result['affiliations'][0]['name_ja'] == '東京大学'

    def test_person_with_single_name(self):
        person = {
            'names': [
                {'lang': 'ja', 'last_name': '山田'},
                {'lang': 'en', 'last_name': 'Yamada'}
            ]
        }

        result = extract_person_data(person)

        assert result['name_ja'] == {
            'last': '山田',
            'middle': '',
            'first': ''
        }
        assert result['name_ja_str'] == '山田'
        assert result['name_en_str'] == 'Yamada'

    def test_empty_person(self):
        assert extract_person_data({}) is None
        assert extract_person_data(None) is None


class TestExtractDates:

    def test_full_publication_date(self):
        jalc_data = {
            'publication_date': {
                'publication_year': '2024',
                'publication_month': '3',
                'publication_day': '15'
            }
        }

        result = {}
        extract_dates(jalc_data, result)

        assert result['publication_date'] == '2024-03-15'
        assert result['publication_year'] == '2024'
        assert result['publication_year_month'] == '2024-03'

    def test_year_month_only(self):
        jalc_data = {
            'publication_date': {
                'publication_year': '2024',
                'publication_month': '12'
            }
        }

        result = {}
        extract_dates(jalc_data, result)

        assert result['publication_date'] == '2024-12'
        assert result['publication_year'] == '2024'
        assert result['publication_year_month'] == '2024-12'

    def test_year_only(self):
        jalc_data = {
            'publication_date': {
                'publication_year': '2024'
            }
        }

        result = {}
        extract_dates(jalc_data, result)

        assert result['publication_date'] == '2024'
        assert result['publication_year'] == '2024'
        assert result['publication_year_month'] == '2024'

    def test_single_digit_month_day(self):
        # Test that single digit months/days are zero-padded
        jalc_data = {
            'publication_date': {
                'publication_year': '2024',
                'publication_month': '3',
                'publication_day': '5'
            }
        }

        result = {}
        extract_dates(jalc_data, result)

        assert result['publication_date'] == '2024-03-05'
        assert result['publication_year_month'] == '2024-03'


class TestSuggestionIntegration:
    """Test integration with main suggestion.py module"""

    def test_valid_suggestion_key_jalc(self):
        """Test that jalc: keys are recognized as valid by main module"""
        assert valid_suggestion_key('jalc:doi') is True
        assert valid_suggestion_key('jalc:article') is True
        assert valid_suggestion_key('jalc') is False

    def test_other_keys_still_work(self):
        """Test that other suggestion keys still work"""
        assert valid_suggestion_key('file-data-number') is True
        assert valid_suggestion_key('get-excel-row-count') is True
        assert valid_suggestion_key('ror') is True
        assert valid_suggestion_key('erad:kenkyusha_no') is True
        assert valid_suggestion_key('asset:title') is True
        assert valid_suggestion_key('contributor:name') is True
        assert valid_suggestion_key('crossref:doi') is True
        assert valid_suggestion_key('invalid-key') is False

    @responses.activate
    def test_suggestion_metadata_jalc(self):
        """Test that suggestion_metadata correctly routes JaLC requests"""
        doi = '10.24602/sjpr.67.1_109'
        mock_response = {
            'status': 'OK',
            'apiType': 'doi',
            'apiVersion': 'v1',
            'message': {
                'total': 1,
                'rows': 1,
                'totalPages': 1,
                'page': 1
            },
            'data': {
                'doi': doi,
                'title_list': [
                    {'lang': 'ja', 'title': 'テスト記事'},
                    {'lang': 'en', 'title': 'Test Article'}
                ]
            }
        }

        responses.add(
            responses.GET,
            'https://api.japanlinkcenter.org/v2/dois/10.24602%2Fsjpr.67.1_109',
            json=mock_response,
            status=200
        )

        # Note: filepath and node parameters are not used for JaLC suggestions
        result = suggestion_metadata('jalc:doi', doi, None, None)

        assert len(result) == 1
        assert result[0]['key'] == 'jalc:doi'
        assert result[0]['value']['doi'] == doi
        assert result[0]['value']['title'] == 'Test Article'
        assert result[0]['value']['title_ja'] == 'テスト記事'

    @responses.activate
    def test_suggestion_metadata_jalc_not_found(self):
        """Test that 404 responses return empty list"""
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            'https://api.japanlinkcenter.org/v2/dois/10.1234%2Fnotfound',
            status=404
        )

        result = suggestion_metadata('jalc:doi', doi, None, None)
        assert result == []

    def test_suggestion_metadata_invalid_key(self):
        """Test that invalid keys raise KeyError"""
        with pytest.raises(KeyError, match='Invalid key'):
            suggestion_metadata('invalid:key', 'test', None, None)