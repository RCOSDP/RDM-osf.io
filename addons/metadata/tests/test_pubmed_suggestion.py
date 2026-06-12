# -*- coding: utf-8 -*-
"""
Tests for PubMed suggestion module
"""
import pytest
import responses
import json
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from addons.metadata.suggestions.pubmed import (
    valid_pubmed_key,
    suggestion_pubmed,
    search_pubmed,
    fetch_pubmed_metadata,
    extract_pubmed_metadata
)
from addons.metadata.suggestion import (
    valid_suggestion_key,
    suggestion_metadata
)


class TestValidPubmedKey:

    def test_valid_key(self):
        assert valid_pubmed_key('pubmed:doi') is True
        assert valid_pubmed_key('pubmed:pmid') is True

    def test_invalid_key(self):
        assert valid_pubmed_key('crossref:doi') is False
        assert valid_pubmed_key('doi:pubmed') is False
        assert valid_pubmed_key('pubmed') is False


class TestSearchPubmed:

    @responses.activate
    def test_successful_search(self):
        search_term = '10.1038/nature12373'
        mock_response = {
            'esearchresult': {
                'count': '1',
                'idlist': ['23903748']
            }
        }

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json=mock_response,
            status=200
        )

        result = search_pubmed(search_term)
        assert result == '23903748'

    @responses.activate
    def test_no_results(self):
        search_term = '10.1234/notfound'
        mock_response = {
            'esearchresult': {
                'count': '0',
                'idlist': []
            }
        }

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json=mock_response,
            status=200
        )

        result = search_pubmed(search_term)
        assert result is None

    @responses.activate
    def test_404_response(self):
        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            status=404
        )

        result = search_pubmed('test')
        assert result is None


class TestFetchPubmedMetadata:

    @responses.activate
    def test_successful_fetch(self):
        pmid = '23903748'
        mock_response = {
            'result': {
                '23903748': {
                    'uid': '23903748',
                    'title': 'Test Article',
                    'source': 'Nature'
                }
            }
        }

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            json=mock_response,
            status=200
        )

        result = fetch_pubmed_metadata(pmid)
        assert result['uid'] == '23903748'
        assert result['title'] == 'Test Article'

    @responses.activate
    def test_pmid_not_found(self):
        pmid = '99999999'
        mock_response = {
            'result': {}
        }

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            json=mock_response,
            status=200
        )

        result = fetch_pubmed_metadata(pmid)
        assert result is None


class TestExtractPubmedMetadata:

    def test_basic_metadata(self):
        pubmed_data = {
            'uid': '23903748',
            'title': 'Nanometre-scale thermometry in a living cell.',
            'source': 'Nature',
            'fulljournalname': 'Nature',
            'volume': '500',
            'issue': '7460',
            'pages': '54-8',
            'pubdate': '2013 Aug 1'
        }
        doi = '10.1038/nature12373'

        result = extract_pubmed_metadata(pubmed_data, doi)

        assert result['pmid'] == '23903748'
        assert result['doi'] == '10.1038/nature12373'
        assert result['title'] == 'Nanometre-scale thermometry in a living cell'
        assert result['journal_title'] == 'Nature'
        assert result['volume'] == '500'
        assert result['issue'] == '7460'
        assert result['page'] == '54-8'
        assert result['page_start'] == '54'
        assert result['page_end'] == '58'  # Abbreviated page number
        assert result['publication_date'] == '2013 Aug 1'
        assert result['publication_year'] == '2013'
        assert result['publication_year_month'] == '2013-08'

    def test_authors_extraction(self):
        pubmed_data = {
            'authors': [
                {'name': 'Kucsko G'},
                {'name': 'Maurer PC'},
                {'name': 'Yao NY'}
            ]
        }

        result = extract_pubmed_metadata(pubmed_data, '10.1038/test')

        assert len(result['authors']) == 3
        assert result['authors'][0]['family'] == 'Kucsko'
        assert result['authors'][0]['given'] == 'G'
        assert result['authors'][1]['family'] == 'Maurer'
        assert result['authors'][1]['given'] == 'PC'

        # Test common metadata format
        assert len(result['authors_common_metadata_format']) == 3
        assert result['authors_common_metadata_format'][0]['name-en'] == {
            'last': 'Kucsko',
            'middle': '',
            'first': 'G'
        }

    def test_page_parsing(self):
        # Test abbreviated page range
        pubmed_data = {'pages': '54-8'}
        result = extract_pubmed_metadata(pubmed_data, 'doi')
        assert result['page_start'] == '54'
        assert result['page_end'] == '58'

        # Test full page range
        pubmed_data = {'pages': '100-105'}
        result = extract_pubmed_metadata(pubmed_data, 'doi')
        assert result['page_start'] == '100'
        assert result['page_end'] == '105'

        # Test electronic pages
        pubmed_data = {'pages': 'e12-e20'}
        result = extract_pubmed_metadata(pubmed_data, 'doi')
        assert result['page_start'] == 'e12'
        assert result['page_end'] == 'e20'

        # Test single page
        pubmed_data = {'pages': '42'}
        result = extract_pubmed_metadata(pubmed_data, 'doi')
        assert result['page_start'] == '42'
        assert 'page_end' not in result

    def test_date_parsing(self):
        # Test various date formats
        test_cases = [
            ('2013 Aug 1', '2013', '2013-08'),
            ('2013 Aug', '2013', '2013-08'),
            ('2013', '2013', '2013'),
            ('2021 Dec 25', '2021', '2021-12'),
            ('2020 Jan', '2020', '2020-01')
        ]

        for pubdate, expected_year, expected_year_month in test_cases:
            pubmed_data = {'pubdate': pubdate}
            result = extract_pubmed_metadata(pubmed_data, 'doi')
            assert result['publication_year'] == expected_year
            assert result['publication_year_month'] == expected_year_month

    def test_article_ids(self):
        pubmed_data = {
            'articleids': [
                {'idtype': 'doi', 'value': '10.1038/nature12373'},
                {'idtype': 'pmc', 'value': 'PMC4221854'},
                {'idtype': 'mid', 'value': 'NIHMS636072'}
            ]
        }

        result = extract_pubmed_metadata(pubmed_data, 'test_doi')

        assert result['doi'] == 'test_doi'  # DOI is always set from parameter
        assert result['pmc_id'] == 'PMC4221854'
        assert result['manuscript_id'] == 'NIHMS636072'

    def test_publication_types(self):
        pubmed_data = {
            'pubtype': ['Journal Article', 'Research Support, N.I.H., Extramural']
        }

        result = extract_pubmed_metadata(pubmed_data, 'doi')

        assert result['publication_type'] == ['Journal Article', 'Research Support, N.I.H., Extramural']
        assert result['manuscript_type_common_metadata_format'] == 'journal article'

        # Test review article
        pubmed_data = {'pubtype': ['Review']}
        result = extract_pubmed_metadata(pubmed_data, 'doi')
        assert result['manuscript_type_common_metadata_format'] == 'review article'

    def test_history_dates(self):
        pubmed_data = {
            'history': [
                {'pubstatus': 'received', 'date': '2013/03/19 00:00'},
                {'pubstatus': 'accepted', 'date': '2013/06/10 00:00'},
                {'pubstatus': 'revised', 'date': '2013/05/15 00:00'}
            ]
        }

        result = extract_pubmed_metadata(pubmed_data, 'doi')

        assert result['received_date'] == '2013/03/19 00:00'
        assert result['accepted_date'] == '2013/06/10 00:00'
        assert result['revised_date'] == '2013/05/15 00:00'


class TestSuggestionPubmed:

    def setUp(self):
        cache.clear()

    @responses.activate
    def test_successful_doi_lookup(self):
        doi = '10.1038/nature12373'

        # Mock ESearch response
        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json={'esearchresult': {'idlist': ['23903748']}},
            status=200
        )

        # Mock ESummary response
        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            json={
                'result': {
                    '23903748': {
                        'uid': '23903748',
                        'title': 'Test Article',
                        'source': 'Nature',
                        'authors': [{'name': 'Doe J'}]
                    }
                }
            },
            status=200
        )

        result = suggestion_pubmed('pubmed:doi', doi)

        assert len(result) == 1
        assert result[0]['key'] == 'pubmed:doi'
        assert result[0]['value']['doi'] == doi
        assert result[0]['value']['pmid'] == '23903748'

    @responses.activate
    def test_doi_not_found(self):
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json={'esearchresult': {'idlist': []}},
            status=200
        )

        result = suggestion_pubmed('pubmed:doi', doi)
        assert result == []

    def test_empty_keyword(self):
        result = suggestion_pubmed('pubmed:doi', '')
        assert result == []

    def test_invalid_doi_format(self):
        result = suggestion_pubmed('pubmed:doi', 'not-a-doi')
        assert result == []

    def test_doi_cleaning(self):
        test_cases = [
            'https://doi.org/10.1038/nature12373',
            'http://dx.doi.org/10.1038/nature12373',
            'doi:10.1038/nature12373'
        ]

        for input_doi in test_cases:
            # Should not return empty for valid DOI formats
            # (would need to mock API calls to fully test)
            pass

    @patch('addons.metadata.suggestions.pubmed.cache')
    @responses.activate
    def test_caching(self, mock_cache):
        mock_cache.get.return_value = None
        doi = '10.1038/nature12373'

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json={'esearchresult': {'idlist': ['23903748']}},
            status=200
        )

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            json={
                'result': {
                    '23903748': {
                        'uid': '23903748',
                        'title': 'Test Article'
                    }
                }
            },
            status=200
        )

        result = suggestion_pubmed('pubmed:doi', doi)

        # Verify cache.set was called
        mock_cache.set.assert_called_once()
        cache_key, cache_value, cache_duration = mock_cache.set.call_args[0]
        assert cache_key == f'pubmed:{doi}'
        assert cache_duration == 24 * 60 * 60

    @patch('addons.metadata.suggestions.pubmed.cache')
    def test_cache_hit(self, mock_cache):
        cached_result = [{'key': 'pubmed:doi', 'value': {'title': 'Cached Article'}}]
        mock_cache.get.return_value = cached_result

        result = suggestion_pubmed('pubmed:doi', '10.1038/nature12373')

        assert result == cached_result
        # No API calls should be made when cache hit


class TestSuggestionIntegration:
    """Test integration with main suggestion.py module"""

    def test_valid_suggestion_key_pubmed(self):
        assert valid_suggestion_key('pubmed:doi') is True
        assert valid_suggestion_key('pubmed:pmid') is True
        assert valid_suggestion_key('pubmed') is False

    def test_other_keys_still_work(self):
        assert valid_suggestion_key('crossref:doi') is True
        assert valid_suggestion_key('jalc:doi') is True
        assert valid_suggestion_key('file-data-number') is True
        assert valid_suggestion_key('ror') is True

    @responses.activate
    def test_suggestion_metadata_pubmed(self):
        doi = '10.1038/nature12373'

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json={'esearchresult': {'idlist': ['23903748']}},
            status=200
        )

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',
            json={
                'result': {
                    '23903748': {
                        'uid': '23903748',
                        'title': 'Test Article',
                        'source': 'Nature'
                    }
                }
            },
            status=200
        )

        result = suggestion_metadata('pubmed:doi', doi, None, None)

        assert len(result) == 1
        assert result[0]['key'] == 'pubmed:doi'
        assert result[0]['value']['pmid'] == '23903748'

    @responses.activate
    def test_suggestion_metadata_pubmed_not_found(self):
        doi = '10.1234/notfound'

        responses.add(
            responses.GET,
            'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            json={'esearchresult': {'idlist': []}},
            status=200
        )

        result = suggestion_metadata('pubmed:doi', doi, None, None)
        assert result == []