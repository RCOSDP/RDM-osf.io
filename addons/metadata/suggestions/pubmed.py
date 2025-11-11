# -*- coding: utf-8 -*-
"""
PubMed suggestion module for fetching publication metadata from DOI
"""
import logging
import re
import requests
from django.core.cache import cache
from addons.metadata import settings

logger = logging.getLogger(__name__)

PUBMED_ESEARCH_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
PUBMED_ESUMMARY_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi'
PUBMED_TIMEOUT = 10  # seconds
CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds


def valid_pubmed_key(key):
    """Check if the key is valid for PubMed suggestions"""
    return key.startswith('pubmed:')


def suggestion_pubmed(key, keyword):
    """
    Fetch publication metadata from PubMed API using DOI

    Args:
        key: The suggestion key (e.g., 'pubmed:doi')
        keyword: The DOI to look up

    Returns:
        List of suggestion results with publication metadata
    """
    if not keyword:
        return []

    cache_key = f'pubmed:{keyword}'
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Clean the DOI
    doi = keyword.strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:', '', doi)

    # Basic DOI format validation
    if not re.match(r'^10\.\d{4,}/[-._;()/:a-zA-Z0-9]+$', doi):
        return []

    pmid = search_pubmed(doi)
    if not pmid:
        return []

    metadata = fetch_pubmed_metadata(pmid)
    if not metadata:
        return []

    result = extract_pubmed_metadata(metadata, doi)

    response = [{
        'key': key,
        'value': result
    }]

    cache.set(cache_key, response, CACHE_DURATION)

    return response


def search_pubmed(doi):
    """Search PubMed for a PMID using DOI"""
    params = {
        'db': 'pubmed',
        'term': doi,
        'retmode': 'json',
        'retmax': 1
    }

    api_key = settings.PUBMED_API_KEY
    if api_key:
        params['api_key'] = api_key

    response = requests.get(
        PUBMED_ESEARCH_URL,
        params=params,
        headers={'User-Agent': 'GakuNin-RDM/1.0'},
        timeout=PUBMED_TIMEOUT
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    data = response.json()
    id_list = data.get('esearchresult', {}).get('idlist', [])

    return id_list[0] if id_list else None


def fetch_pubmed_metadata(pmid):
    """Fetch metadata for a PMID using ESummary API"""
    params = {
        'db': 'pubmed',
        'id': pmid,
        'retmode': 'json'
    }

    api_key = settings.PUBMED_API_KEY
    if api_key:
        params['api_key'] = api_key

    response = requests.get(
        PUBMED_ESUMMARY_URL,
        params=params,
        headers={'User-Agent': 'GakuNin-RDM/1.0'},
        timeout=PUBMED_TIMEOUT
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    data = response.json()
    result = data.get('result', {})

    return result.get(str(pmid))


def extract_pubmed_metadata(pubmed_data, doi):
    """Extract relevant metadata from PubMed ESummary response"""
    result = {}

    result['doi'] = doi

    if 'uid' in pubmed_data:
        result['pmid'] = pubmed_data['uid']

    if 'title' in pubmed_data:
        title = pubmed_data['title'].rstrip('.')
        result['title'] = title

    authors = []
    for author in pubmed_data.get('authors', []):
        author_name = author.get('name', '')
        if author_name:
            parts = author_name.split(' ', 1)
            if len(parts) == 2:
                family = parts[0]
                given = parts[1]
            else:
                family = author_name
                given = ''

            authors.append({
                'family': family,
                'given': given,
                'name': author_name
            })
    result['authors'] = authors

    result['authors_common_metadata_format'] = []
    for author in authors:
        formatted_author = {
            'name-en': {
                'last': author.get('family', ''),
                'middle': '',
                'first': author.get('given', '')
            }
        }
        result['authors_common_metadata_format'].append(formatted_author)

    if 'source' in pubmed_data:
        result['journal_title'] = pubmed_data['source']

    if 'fulljournalname' in pubmed_data:
        result['journal_title_full'] = pubmed_data['fulljournalname']

    if 'volume' in pubmed_data:
        result['volume'] = pubmed_data['volume']

    if 'issue' in pubmed_data:
        result['issue'] = pubmed_data['issue']

    if 'pages' in pubmed_data:
        pages = pubmed_data['pages']
        result['page'] = pages

        if '-' in pages:
            parts = pages.split('-', 1)
            result['page_start'] = parts[0].strip()
            if len(parts) > 1:
                end_page = parts[1].strip()
                if end_page and not end_page[0].isalpha() and len(end_page) < len(parts[0]):
                    start_page = parts[0].strip()
                    result['page_end'] = start_page[:-len(end_page)] + end_page
                else:
                    result['page_end'] = end_page
        else:
            result['page_start'] = pages.strip()

    if 'pubdate' in pubmed_data:
        pubdate = pubmed_data['pubdate']
        result['publication_date'] = pubdate

        year_match = re.search(r'(\d{4})', pubdate)
        if year_match:
            result['publication_year'] = year_match.group(1)

        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }

        for month_name, month_num in month_map.items():
            if month_name in pubdate:
                if year_match:
                    result['publication_year_month'] = f"{year_match.group(1)}-{month_num}"
                break
        else:
            if year_match:
                result['publication_year_month'] = year_match.group(1)

    if 'epubdate' in pubmed_data and pubmed_data['epubdate']:
        result['epubdate'] = pubmed_data['epubdate']

    article_ids = pubmed_data.get('articleids', [])
    for aid in article_ids:
        id_type = aid.get('idtype', '')
        value = aid.get('value', '')

        if id_type == 'pmc':
            result['pmc_id'] = value
        elif id_type == 'mid':
            result['manuscript_id'] = value

    if 'issn' in pubmed_data:
        result['issn'] = pubmed_data['issn']

    if 'essn' in pubmed_data:
        result['essn'] = pubmed_data['essn']

    lang_list = pubmed_data.get('lang', [])
    if lang_list:
        result['language'] = lang_list[0] if len(lang_list) == 1 else lang_list

    pubtype_list = pubmed_data.get('pubtype', [])
    if pubtype_list:
        result['publication_type'] = pubtype_list

        type_mapping = {
            'Journal Article': 'journal article',
            'Review': 'review article',
            'Editorial': 'editorial',
            'Dataset': 'data paper',
        }

        for pubtype in pubtype_list:
            manuscript_type = type_mapping.get(pubtype)
            if manuscript_type:
                result['manuscript_type_common_metadata_format'] = manuscript_type
                break

    if 'recordstatus' in pubmed_data:
        result['record_status'] = pubmed_data['recordstatus']

    attributes = pubmed_data.get('attributes', [])
    if attributes:
        result['attributes'] = attributes
        result['has_abstract'] = 'Has Abstract' in attributes

    history = pubmed_data.get('history', [])
    for hist_entry in history:
        status = hist_entry.get('pubstatus', '')
        date = hist_entry.get('date', '')
        if status == 'received':
            result['received_date'] = date
        elif status == 'accepted':
            result['accepted_date'] = date
        elif status == 'revised':
            result['revised_date'] = date

    if 'pmcrefcount' in pubmed_data:
        result['pmc_citation_count'] = pubmed_data['pmcrefcount']

    return result
