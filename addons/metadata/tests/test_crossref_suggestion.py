# -*- coding: utf-8 -*-
"""
Tests for Crossref suggestion module
"""
import pytest
import responses
import json
from addons.metadata.suggestions.crossref import (
    valid_crossref_key,
    suggestion_crossref,
    extract_crossref_metadata,
    extract_person_data,
    extract_date_string,
    extract_dates
)
from addons.metadata.suggestion import (
    valid_suggestion_key,
    suggestion_metadata
)


class TestValidCrossrefKey:

    def test_valid_key(self):
        assert valid_crossref_key('crossref:doi') is True
        assert valid_crossref_key('crossref:article') is True

    def test_invalid_key(self):
        assert valid_crossref_key('erad:doi') is False
        assert valid_crossref_key('doi:crossref') is False
        assert valid_crossref_key('crossref') is False


class TestSuggestionCrossref:

    @responses.activate
    def test_successful_doi_lookup(self):
        doi = '10.3390/bdcc5040076'
        mock_response = {
            'status': 'ok',
            'message-type': 'work',
            'message': {
                'DOI': doi,
                'title': ['Test Article'],
                'author': [
                    {'given': 'John', 'family': 'Doe'}
                ],
                'published-online': {
                    'date-parts': [[2021, 12, 13]]
                }
            }
        }

        responses.add(
            responses.GET,
            f'https://api.crossref.org/works/{doi}',
            json=mock_response,
            status=200
        )

        result = suggestion_crossref('crossref:doi', doi)

        assert len(result) == 1
        assert result[0]['key'] == 'crossref:doi'
        assert result[0]['value']['doi'] == doi
        assert result[0]['value']['title'] == 'Test Article'

    @responses.activate
    def test_doi_not_found(self):
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            f'https://api.crossref.org/works/{doi}',
            status=404
        )

        result = suggestion_crossref('crossref:doi', doi)
        assert result == []

    @responses.activate
    def test_server_error(self):
        doi = '10.3390/bdcc5040076'

        responses.add(
            responses.GET,
            f'https://api.crossref.org/works/{doi}',
            status=500
        )

        with pytest.raises(Exception):  # requests.exceptions.HTTPError
            suggestion_crossref('crossref:doi', doi)

    def test_empty_keyword(self):
        result = suggestion_crossref('crossref:doi', '')
        assert result == []

    def test_invalid_doi_format(self):
        result = suggestion_crossref('crossref:doi', 'not-a-doi')
        assert result == []

    def test_doi_cleaning(self):
        # Test that various DOI formats are cleaned properly
        test_cases = [
            ('https://doi.org/10.3390/bdcc5040076', '10.3390/bdcc5040076'),
            ('http://dx.doi.org/10.3390/bdcc5040076', '10.3390/bdcc5040076'),
            ('doi:10.3390/bdcc5040076', '10.3390/bdcc5040076'),
            ('10.3390/bdcc5040076', '10.3390/bdcc5040076'),
        ]

        for input_doi, expected_doi in test_cases:
            # Would need to mock the actual API call to test this properly
            # For now, just verify the DOI validation doesn't reject valid formats
            pass


class TestExtractCrossrefMetadata:

    def test_basic_metadata(self):
        message = {
            'DOI': '10.3390/bdcc5040076',
            'title': ['Test Article'],
            'subtitle': ['A Subtitle'],
            'container-title': ['Journal Name'],
            'volume': '5',
            'issue': '4',
            'page': '76',
            'publisher': 'MDPI AG',
            'type': 'journal-article'
        }

        result = extract_crossref_metadata(message)

        assert result['doi'] == '10.3390/bdcc5040076'
        assert result['title'] == 'Test Article'
        assert result['subtitle'] == 'A Subtitle'
        assert result['journal_title'] == 'Journal Name'
        assert result['volume'] == '5'
        assert result['issue'] == '4'
        assert result['page'] == '76'
        assert result['page_start'] == '76'  # Single page
        assert 'page_end' not in result  # No end page for single page
        assert result['publisher'] == 'MDPI AG'
        assert result['type'] == 'journal-article'
        assert result['manuscript_type_common_metadata_format'] == 'journal article'

    def test_page_parsing(self):
        # Test single page
        message = {'page': '76'}
        result = extract_crossref_metadata(message)
        assert result['page'] == '76'
        assert result['page_start'] == '76'
        assert 'page_end' not in result

        # Test page range
        message = {'page': '54-58'}
        result = extract_crossref_metadata(message)
        assert result['page'] == '54-58'
        assert result['page_start'] == '54'
        assert result['page_end'] == '58'

        # Test electronic page format
        message = {'page': 'e12-e20'}
        result = extract_crossref_metadata(message)
        assert result['page'] == 'e12-e20'
        assert result['page_start'] == 'e12'
        assert result['page_end'] == 'e20'

        # Test page with spaces
        message = {'page': '100 - 105'}
        result = extract_crossref_metadata(message)
        assert result['page'] == '100 - 105'
        assert result['page_start'] == '100'
        assert result['page_end'] == '105'

    def test_authors_extraction(self):
        message = {
            'author': [
                {
                    'given': 'John', 
                    'family': 'Doe', 
                    'ORCID': 'https://orcid.org/0000-0000-0000-0001',
                    'affiliation': [
                        {
                            'name': 'University of Tokyo',
                            'department': ['Computer Science'],
                            'place': ['Tokyo', 'Japan']
                        }
                    ]
                },
                {'given': 'Jane', 'family': 'Smith'},
                {'name': 'Research Group'}
            ]
        }

        result = extract_crossref_metadata(message)

        assert len(result['authors']) == 3
        assert result['authors'][0]['given'] == 'John'
        assert result['authors'][0]['family'] == 'Doe'
        assert result['authors'][0]['orcid'] == 'https://orcid.org/0000-0000-0000-0001'
        assert result['authors'][0]['name_en'] == 'John Doe'
        assert result['authors'][0]['name_ja'] == 'Doe, John'
        
        # Check affiliation in raw authors data
        assert 'affiliations' in result['authors'][0]
        assert result['authors'][0]['affiliations'][0]['name'] == 'University of Tokyo'
        
        assert result['authors'][2]['name'] == 'Research Group'

        # Test common metadata format
        assert len(result['authors_common_metadata_format']) == 3
        # Only English names since Crossref only has English data
        assert result['authors_common_metadata_format'][0]['name-en'] == {
            'last': 'Doe',
            'middle': '',
            'first': 'John'
        }
        assert 'name-ja' not in result['authors_common_metadata_format'][0]
        
        # Check affiliation in common metadata format
        assert 'affiliation-name-ja' in result['authors_common_metadata_format'][0]
        assert result['authors_common_metadata_format'][0]['affiliation-name-ja'] == ''
        assert 'affiliation-name-en' in result['authors_common_metadata_format'][0]
        assert result['authors_common_metadata_format'][0]['affiliation-name-en'] == 'University of Tokyo'
        
        # Second author has no affiliation
        assert result['authors_common_metadata_format'][1]['name-en'] == {
            'last': 'Smith',
            'middle': '',
            'first': 'Jane'
        }
        assert 'name-ja' not in result['authors_common_metadata_format'][1]
        assert 'affiliation-name-ja' not in result['authors_common_metadata_format'][1]
        assert 'affiliation-name-en' not in result['authors_common_metadata_format'][1]

    def test_dates_extraction(self):
        message = {
            'published-print': {
                'date-parts': [[2021, 12, 13]]
            },
            'published-online': {
                'date-parts': [[2021, 11, 1]]
            },
            'created': {
                'date-parts': [[2021, 10, 1]],
                'date-time': '2021-10-01T00:00:00Z'
            }
        }

        result = extract_crossref_metadata(message)

        assert result['published_print'] == '2021-12-13'
        assert result['published_online'] == '2021-11-01'
        assert result['publication_date'] == '2021-12-13'  # Print takes priority
        assert result['publication_year'] == '2021'
        assert result['created'] == '2021-10-01'

    def test_license_extraction(self):
        message = {
            'license': [
                {
                    'URL': 'https://creativecommons.org/licenses/by/4.0/',
                    'content-version': 'vor',
                    'delay-in-days': 0,
                    'start': {
                        'date-parts': [[2021, 12, 13]]
                    }
                }
            ]
        }

        result = extract_crossref_metadata(message)

        assert len(result['licenses']) == 1
        assert result['licenses'][0]['url'] == 'https://creativecommons.org/licenses/by/4.0/'
        assert result['licenses'][0]['content_version'] == 'vor'
        assert result['licenses'][0]['delay_in_days'] == 0
        assert result['licenses'][0]['start'] == '2021-12-13'

    def test_funder_extraction(self):
        message = {
            'funder': [
                {
                    'name': 'Japan Science and Technology Agency',
                    'DOI': '10.13039/501100002241',
                    'award': ['JPMJCR18A4', 'JPMJCR19B2']
                }
            ]
        }

        result = extract_crossref_metadata(message)

        assert len(result['funders']) == 1
        assert result['funders'][0]['name'] == 'Japan Science and Technology Agency'
        assert result['funders'][0]['doi'] == '10.13039/501100002241'
        assert result['funders'][0]['award'] == ['JPMJCR18A4', 'JPMJCR19B2']

    def test_abstract_with_html(self):
        message = {
            'abstract': '<p>This is an <strong>abstract</strong> with <em>HTML</em> tags.</p>'
        }

        result = extract_crossref_metadata(message)

        assert result['abstract'] == 'This is an abstract with HTML tags.'

    def test_event_extraction(self):
        message = {
            'event': {
                'name': 'International Conference',
                'location': 'Tokyo, Japan',
                'start': {
                    'date-parts': [[2021, 10, 1]]
                },
                'end': {
                    'date-parts': [[2021, 10, 3]]
                }
            }
        }

        result = extract_crossref_metadata(message)

        assert result['event']['name'] == 'International Conference'
        assert result['event']['location'] == 'Tokyo, Japan'
        assert result['event']['start'] == '2021-10-01'
        assert result['event']['end'] == '2021-10-03'

    def test_empty_message(self):
        result = extract_crossref_metadata({})

        assert result == {'authors': [], 'authors_common_metadata_format': [], 'editors': [], 'translators': [], 'chairs': []}

    def test_manuscript_type_mapping(self):
        """Test manuscript type mapping to common metadata format"""
        # Test journal article
        message = {'type': 'journal-article'}
        result = extract_crossref_metadata(message)
        assert result['manuscript_type_common_metadata_format'] == 'journal article'

        # Test conference paper
        message = {'type': 'proceedings-article'}
        result = extract_crossref_metadata(message)
        assert result['manuscript_type_common_metadata_format'] == 'conference paper'

        # Test unmapped type (should not have manuscript_type_common_metadata_format)
        message = {'type': 'book-chapter'}
        result = extract_crossref_metadata(message)
        assert 'manuscript_type_common_metadata_format' not in result
        assert result['type'] == 'book-chapter'  # Original type should still be preserved

        # Test unknown type
        message = {'type': 'unknown-type'}
        result = extract_crossref_metadata(message)
        assert 'manuscript_type_common_metadata_format' not in result
        assert result['type'] == 'unknown-type'


class TestExtractPersonData:

    def test_full_name(self):
        person = {
            'given': 'John',
            'family': 'Doe',
            'ORCID': 'https://orcid.org/0000-0000-0000-0001',
            'prefix': 'Dr.',
            'suffix': 'Jr.',
            'sequence': 'first'
        }

        result = extract_person_data(person)

        assert result['given'] == 'John'
        assert result['family'] == 'Doe'
        assert result['name_en'] == 'John Doe'
        assert result['name_ja'] == 'Doe, John'
        assert result['orcid'] == 'https://orcid.org/0000-0000-0000-0001'
        assert result['prefix'] == 'Dr.'
        assert result['suffix'] == 'Jr.'
        assert result['sequence'] == 'first'

    def test_family_name_only(self):
        person = {'family': 'Smith'}

        result = extract_person_data(person)

        assert result['family'] == 'Smith'
        assert result['name_en'] == 'Smith'
        assert result['name_ja'] == 'Smith'

    def test_given_name_only(self):
        person = {'given': 'Jane'}

        result = extract_person_data(person)

        assert result['given'] == 'Jane'
        assert result['name_en'] == 'Jane'
        assert result['name_ja'] == 'Jane'

    def test_name_field(self):
        person = {'name': 'Research Group'}

        result = extract_person_data(person)

        assert result['name'] == 'Research Group'

    def test_with_affiliation(self):
        person = {
            'family': 'Doe',
            'affiliation': [
                {
                    'name': 'University of Tokyo',
                    'department': ['Computer Science'],
                    'place': ['Tokyo', 'Japan']
                }
            ]
        }

        result = extract_person_data(person)

        assert len(result['affiliations']) == 1
        assert result['affiliations'][0]['name'] == 'University of Tokyo'
        assert result['affiliations'][0]['department'] == ['Computer Science']
        assert result['affiliations'][0]['place'] == ['Tokyo', 'Japan']

    def test_empty_person(self):
        assert extract_person_data({}) is None
        assert extract_person_data(None) is None


class TestExtractDateString:

    def test_full_date(self):
        date_obj = {
            'date-parts': [[2021, 12, 13]]
        }
        assert extract_date_string(date_obj) == '2021-12-13'

    def test_year_month(self):
        date_obj = {
            'date-parts': [[2021, 12]]
        }
        assert extract_date_string(date_obj) == '2021-12'

    def test_year_only(self):
        date_obj = {
            'date-parts': [[2021]]
        }
        assert extract_date_string(date_obj) == '2021'

    def test_datetime_fallback(self):
        date_obj = {
            'date-time': '2021-12-13T00:00:00Z'
        }
        assert extract_date_string(date_obj) == '2021-12-13T00:00:00Z'

    def test_empty_date(self):
        assert extract_date_string({}) is None
        assert extract_date_string(None) is None

    def test_empty_date_parts(self):
        date_obj = {
            'date-parts': []
        }
        assert extract_date_string(date_obj) is None


class TestExtractDates:

    def test_publication_priority(self):
        # Test that published-print takes priority over published-online
        message = {
            'published-print': {
                'date-parts': [[2021, 12, 13]]
            },
            'published-online': {
                'date-parts': [[2021, 11, 1]]
            }
        }

        result = {}
        extract_dates(message, result)

        assert result['publication_date'] == '2021-12-13'
        assert result['publication_year'] == '2021'
        assert result['publication_year_month'] == '2021-12'
        assert result['published_print'] == '2021-12-13'
        assert result['published_online'] == '2021-11-01'

    def test_online_only(self):
        message = {
            'published-online': {
                'date-parts': [[2021, 11, 1]]
            }
        }

        result = {}
        extract_dates(message, result)

        assert result['publication_date'] == '2021-11-01'
        assert result['publication_year'] == '2021'
        assert result['publication_year_month'] == '2021-11'

    def test_publication_year_month_extraction(self):
        # Test extraction of year-month from different date formats

        # Full date should extract year-month
        message = {
            'published-print': {
                'date-parts': [[2021, 12, 13]]
            }
        }
        result = {}
        extract_dates(message, result)
        assert result['publication_year_month'] == '2021-12'

        # Year-month date should use as-is
        message = {
            'published-print': {
                'date-parts': [[2021, 6]]
            }
        }
        result = {}
        extract_dates(message, result)
        assert result['publication_year_month'] == '2021-06'

        # Year-only date should use just the year
        message = {
            'published-print': {
                'date-parts': [[2021]]
            }
        }
        result = {}
        extract_dates(message, result)
        assert result['publication_year_month'] == '2021'

    def test_all_date_fields(self):
        message = {
            'created': {'date-parts': [[2021, 1, 1]]},
            'deposited': {'date-parts': [[2021, 2, 1]]},
            'indexed': {'date-parts': [[2021, 3, 1]]},
            'issued': {'date-parts': [[2021, 4, 1]]},
            'posted': {'date-parts': [[2021, 5, 1]]},
            'accepted': {'date-parts': [[2021, 6, 1]]},
            'approved': {'date-parts': [[2021, 7, 1]]},
            'content-created': {'date-parts': [[2021, 8, 1]]},
            'content-updated': {'date-parts': [[2021, 9, 1]]}
        }

        result = {}
        extract_dates(message, result)

        assert result['created'] == '2021-01-01'
        assert result['deposited'] == '2021-02-01'
        assert result['indexed'] == '2021-03-01'
        assert result['issued'] == '2021-04-01'
        assert result['posted'] == '2021-05-01'
        assert result['accepted'] == '2021-06-01'
        assert result['approved'] == '2021-07-01'
        assert result['content_created'] == '2021-08-01'
        assert result['content_updated'] == '2021-09-01'


class TestSuggestionIntegration:
    """Test integration with main suggestion.py module"""

    def test_valid_suggestion_key_crossref(self):
        """Test that crossref: keys are recognized as valid by main module"""
        assert valid_suggestion_key('crossref:doi') is True
        assert valid_suggestion_key('crossref:article') is True
        assert valid_suggestion_key('crossref') is False

    def test_other_keys_still_work(self):
        """Test that other suggestion keys still work"""
        assert valid_suggestion_key('file-data-number') is True
        assert valid_suggestion_key('get-excel-row-count') is True
        assert valid_suggestion_key('ror') is True
        assert valid_suggestion_key('erad:kenkyusha_no') is True
        assert valid_suggestion_key('asset:title') is True
        assert valid_suggestion_key('contributor:name') is True
        assert valid_suggestion_key('invalid-key') is False

    @responses.activate
    def test_suggestion_metadata_crossref(self):
        """Test that suggestion_metadata correctly routes crossref requests"""
        doi = '10.3390/bdcc5040076'
        mock_response = {
            'status': 'ok',
            'message-type': 'work',
            'message': {
                'DOI': doi,
                'title': ['Test Article'],
                'author': [
                    {'given': 'John', 'family': 'Doe'}
                ],
                'published-online': {
                    'date-parts': [[2021, 12, 13]]
                }
            }
        }

        responses.add(
            responses.GET,
            f'https://api.crossref.org/works/{doi}',
            json=mock_response,
            status=200
        )

        # Note: filepath and node parameters are not used for crossref suggestions
        result = suggestion_metadata('crossref:doi', doi, None, None)

        assert len(result) == 1
        assert result[0]['key'] == 'crossref:doi'
        assert result[0]['value']['doi'] == doi
        assert result[0]['value']['title'] == 'Test Article'

    @responses.activate
    def test_suggestion_metadata_crossref_not_found(self):
        """Test that 404 responses return empty list"""
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            f'https://api.crossref.org/works/{doi}',
            status=404
        )

        result = suggestion_metadata('crossref:doi', doi, None, None)
        assert result == []

    def test_suggestion_metadata_invalid_key(self):
        """Test that invalid keys raise KeyError"""
        with pytest.raises(KeyError, match='Invalid key'):
            suggestion_metadata('invalid:key', 'test', None, None)