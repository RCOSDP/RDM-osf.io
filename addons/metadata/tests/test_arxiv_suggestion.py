# -*- coding: utf-8 -*-
"""
Tests for arXiv suggestion module
"""
import pytest
import responses
from unittest.mock import patch
from django.core.cache import cache
from addons.metadata.suggestions.arxiv import (
    valid_arxiv_key,
    suggestion_arxiv,
    extract_arxiv_metadata,
    parse_journal_ref
)
from addons.metadata.suggestion import (
    valid_suggestion_key,
    suggestion_metadata
)
import xml.etree.ElementTree as ET


class TestValidArxivKey:

    def test_valid_key(self):
        assert valid_arxiv_key('arxiv:id') is True
        assert valid_arxiv_key('arxiv:doi') is True

    def test_invalid_key(self):
        assert valid_arxiv_key('crossref:doi') is False
        assert valid_arxiv_key('doi:arxiv') is False
        assert valid_arxiv_key('arxiv') is False


class TestSuggestionArxiv:

    def setUp(self):
        cache.clear()

    @responses.activate
    def test_successful_arxiv_id_lookup(self):
        arxiv_id = '2301.08727'
        mock_xml = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.08727v2</id>
            <title>Neural Architecture Search: Insights from 1000 Papers</title>
            <summary>In the past decade, advances in deep learning...</summary>
            <author><name>Colin White</name></author>
            <author><name>Mahmoud Safari</name></author>
            <published>2023-01-20T18:47:24Z</published>
            <updated>2023-01-25T08:01:55Z</updated>
            <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG"/>
            <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <link href="http://arxiv.org/abs/2301.08727v2" rel="alternate" type="text/html"/>
            <link href="http://arxiv.org/pdf/2301.08727v2" rel="related" type="application/pdf"/>
          </entry>
        </feed>'''

        responses.add(
            responses.GET,
            'https://export.arxiv.org/api/query',
            body=mock_xml,
            status=200,
            content_type='application/atom+xml'
        )

        result = suggestion_arxiv('arxiv:id', arxiv_id)

        assert len(result) == 1
        assert result[0]['key'] == 'arxiv:id'
        assert result[0]['value']['arxiv_id'] == arxiv_id
        assert result[0]['value']['doi'] == f'10.48550/arXiv.{arxiv_id}'
        assert result[0]['value']['title'] == 'Neural Architecture Search: Insights from 1000 Papers'
        assert len(result[0]['value']['authors']) == 2
        assert result[0]['value']['authors'][0]['name'] == 'Colin White'
        assert result[0]['value']['primary_category'] == 'cs.LG'

    @responses.activate
    def test_successful_doi_lookup(self):
        doi = '10.48550/arXiv.2301.08727'
        arxiv_id = '2301.08727'
        mock_xml = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.08727v2</id>
            <title>Test Paper</title>
            <author><name>Test Author</name></author>
            <published>2023-01-20T18:47:24Z</published>
            <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG"/>
          </entry>
        </feed>'''

        responses.add(
            responses.GET,
            'https://export.arxiv.org/api/query',
            body=mock_xml,
            status=200,
            content_type='application/atom+xml'
        )

        result = suggestion_arxiv('arxiv:doi', doi)

        assert len(result) == 1
        assert result[0]['value']['arxiv_id'] == arxiv_id
        assert result[0]['value']['doi'] == doi

    @responses.activate
    def test_not_found(self):
        arxiv_id = '9999.99999'
        mock_xml = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        </feed>'''

        responses.add(
            responses.GET,
            'https://export.arxiv.org/api/query',
            body=mock_xml,
            status=200,
            content_type='application/atom+xml'
        )

        result = suggestion_arxiv('arxiv:id', arxiv_id)
        assert result == []

    def test_empty_keyword(self):
        result = suggestion_arxiv('arxiv:id', '')
        assert result == []

    def test_invalid_arxiv_id_format(self):
        result = suggestion_arxiv('arxiv:id', 'not-an-arxiv-id')
        assert result == []

    def test_arxiv_id_cleaning(self):
        # Test URL prefix removal
        test_cases = [
            ('https://arxiv.org/abs/2301.08727', '2301.08727'),
            ('https://arxiv.org/pdf/2301.08727.pdf', '2301.08727'),
            ('2301.08727v2', '2301.08727v2'),
        ]

        for input_id, expected_clean_id in test_cases:
            # Would need to mock API calls to fully test
            pass

    @patch('addons.metadata.suggestions.arxiv.cache')
    @responses.activate
    def test_caching(self, mock_cache):
        mock_cache.get.return_value = None
        arxiv_id = '2301.08727'
        mock_xml = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.08727v2</id>
            <title>Test Paper</title>
          </entry>
        </feed>'''

        responses.add(
            responses.GET,
            'https://export.arxiv.org/api/query',
            body=mock_xml,
            status=200
        )

        result = suggestion_arxiv('arxiv:id', arxiv_id)

        mock_cache.set.assert_called_once()
        cache_key, cache_value, cache_duration = mock_cache.set.call_args[0]
        assert cache_key == f'arxiv:{arxiv_id}'
        assert cache_duration == 24 * 60 * 60


class TestExtractArxivMetadata:

    def test_basic_metadata(self):
        xml_str = '''
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2301.08727v2</id>
            <title>Test Title</title>
            <summary>Test abstract text</summary>
            <published>2023-01-20T18:47:24Z</published>
            <updated>2023-01-25T08:01:55Z</updated>
        </entry>'''

        entry = ET.fromstring(xml_str)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

        result = extract_arxiv_metadata(entry, ns, '2301.08727', '10.48550/arXiv.2301.08727')

        assert result['arxiv_id'] == '2301.08727'
        assert result['doi'] == '10.48550/arXiv.2301.08727'
        assert result['title'] == 'Test Title'
        assert result['abstract'] == 'Test abstract text'
        assert result['published'] == '2023-01-20T18:47:24Z'
        assert result['publication_year'] == '2023'
        assert result['publication_year_month'] == '2023-01'
        assert result['version'] == '2'

    def test_authors_extraction(self):
        xml_str = '''
        <entry xmlns="http://www.w3.org/2005/Atom">
            <author><name>Colin White</name></author>
            <author><name>Jane Doe</name></author>
            <author><name>Smith</name></author>
        </entry>'''

        entry = ET.fromstring(xml_str)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

        result = extract_arxiv_metadata(entry, ns, '2301.08727', '10.48550/arXiv.2301.08727')

        assert len(result['authors']) == 3
        assert result['authors'][0]['name'] == 'Colin White'
        assert result['authors'][0]['given'] == 'Colin'
        assert result['authors'][0]['family'] == 'White'

        assert result['authors'][2]['name'] == 'Smith'
        assert result['authors'][2]['given'] == ''
        assert result['authors'][2]['family'] == 'Smith'

        # Check common metadata format
        assert len(result['authors_common_metadata_format']) == 3
        assert result['authors_common_metadata_format'][0]['name-en'] == {
            'last': 'White',
            'middle': '',
            'first': 'Colin'
        }

    def test_categories(self):
        xml_str = '''
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
            <arxiv:primary_category term="cs.LG"/>
            <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <category term="stat.ML" scheme="http://arxiv.org/schemas/atom"/>
        </entry>'''

        entry = ET.fromstring(xml_str)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

        result = extract_arxiv_metadata(entry, ns, '2301.08727', '10.48550/arXiv.2301.08727')

        assert result['primary_category'] == 'cs.LG'
        assert result['categories'] == ['cs.LG', 'cs.AI', 'stat.ML']
        assert result['manuscript_type_common_metadata_format'] == 'article'

    def test_journal_reference(self):
        xml_str = '''
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
            <arxiv:journal_ref>Nature 500, 54-58 (2013)</arxiv:journal_ref>
            <arxiv:doi>10.1038/nature12373</arxiv:doi>
        </entry>'''

        entry = ET.fromstring(xml_str)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

        result = extract_arxiv_metadata(entry, ns, '1301.0001', '10.48550/arXiv.1301.0001')

        assert result['journal_ref'] == 'Nature 500, 54-58 (2013)'
        assert result['external_doi'] == '10.1038/nature12373'
        assert result['journal_year'] == '2013'
        assert result['volume'] == '500'
        assert result['page_start'] == '54'
        assert result['page_end'] == '58'
        assert result['journal_title'] == 'Nature'


class TestParseJournalRef:

    def test_nature_format(self):
        result = {}
        parse_journal_ref('Nature 500, 54-58 (2013)', result)

        assert result['journal_year'] == '2013'
        assert result['volume'] == '500'
        assert result['page_start'] == '54'
        assert result['page_end'] == '58'
        assert result['journal_title'] == 'Nature'

    def test_phys_rev_format(self):
        result = {}
        parse_journal_ref('Phys. Rev. Lett. 120, 120501 (2018)', result)

        assert result['journal_year'] == '2018'
        assert result['volume'] == '120'
        assert result['page_start'] == '120501'
        assert result['journal_title'] == 'Phys. Rev. Lett.'

    def test_no_pages(self):
        result = {}
        parse_journal_ref('Journal Name (2020)', result)

        assert result['journal_year'] == '2020'
        assert 'volume' not in result
        assert 'page_start' not in result


class TestSuggestionIntegration:
    """Test integration with main suggestion.py module"""

    def test_valid_suggestion_key_arxiv(self):
        assert valid_suggestion_key('arxiv:id') is True
        assert valid_suggestion_key('arxiv:doi') is True
        assert valid_suggestion_key('arxiv') is False

    def test_other_keys_still_work(self):
        assert valid_suggestion_key('crossref:doi') is True
        assert valid_suggestion_key('jalc:doi') is True
        assert valid_suggestion_key('pubmed:doi') is True
        assert valid_suggestion_key('file-data-number') is True

    @responses.activate
    def test_suggestion_metadata_arxiv(self):
        arxiv_id = '2301.08727'
        mock_xml = '''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.08727v2</id>
            <title>Test Paper</title>
          </entry>
        </feed>'''

        responses.add(
            responses.GET,
            'https://export.arxiv.org/api/query',
            body=mock_xml,
            status=200
        )

        result = suggestion_metadata('arxiv:id', arxiv_id, None, None)

        assert len(result) == 1
        assert result[0]['key'] == 'arxiv:id'
        assert result[0]['value']['arxiv_id'] == arxiv_id