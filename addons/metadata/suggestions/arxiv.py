# -*- coding: utf-8 -*-
"""
arXiv suggestion module for fetching publication metadata from arXiv ID or DOI
"""
import logging
import re
import requests
import xml.etree.ElementTree as ET
from django.core.cache import cache

logger = logging.getLogger(__name__)

ARXIV_API_URL = 'https://export.arxiv.org/api/query'
ARXIV_TIMEOUT = 10  # seconds
CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds


def valid_arxiv_key(key):
    """Check if the key is valid for arXiv suggestions"""
    return key.startswith('arxiv:')


def suggestion_arxiv(key, keyword):
    """
    Fetch publication metadata from arXiv API using arXiv ID or DOI

    Args:
        key: The suggestion key (e.g., 'arxiv:id', 'arxiv:doi')
        keyword: The arXiv ID or DOI to look up

    Returns:
        List of suggestion results with publication metadata
    """
    if not keyword:
        return []

    cache_key = f'arxiv:{keyword}'
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Clean and extract arXiv ID
    keyword = keyword.strip()
    arxiv_id = None
    doi = None
    
    # Check if it's an arXiv DOI
    if '10.48550/arXiv.' in keyword or '10.48550/arxiv.' in keyword.lower():
        # Extract arXiv ID from DOI
        match = re.search(r'10\.48550/arXiv\.(\S+)', keyword, re.IGNORECASE)
        if match:
            arxiv_id = match.group(1)
            doi = f'10.48550/arXiv.{arxiv_id}'
    else:
        # Assume it's an arXiv ID
        arxiv_id = keyword
        
        # Remove common URL prefixes if present
        arxiv_id = re.sub(r'^https?://arxiv\.org/(abs|pdf)/', '', arxiv_id)
        arxiv_id = re.sub(r'\.pdf$', '', arxiv_id)
        
        # Basic arXiv ID format validation (new format: YYMM.NNNNN or old format: category/YYNNNNN)
        if not re.match(r'^(\d{4}\.\d{4,5}(v\d+)?|[a-z\-]+(\.[A-Z]{2})?/\d{7}(v\d+)?)$', arxiv_id):
            return []
        
        # Construct DOI from arXiv ID
        doi = f'10.48550/arXiv.{arxiv_id}'

    if not arxiv_id:
        return []

    params = {
        'id_list': arxiv_id,
        'max_results': 1
    }
    
    response = requests.get(
        ARXIV_API_URL,
        params=params,
        headers={'User-Agent': 'GakuNin-RDM/1.0'},
        timeout=ARXIV_TIMEOUT
    )
    
    if response.status_code == 404:
        return []
    
    response.raise_for_status()
    
    # Parse XML response
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        logger.error(f'Failed to parse arXiv XML response for ID: {arxiv_id}')
        return []
    
    # Define namespaces
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    # Find entry
    entry = root.find('atom:entry', ns)
    if entry is None:
        return []
    
    # Extract metadata
    result = extract_arxiv_metadata(entry, ns, arxiv_id, doi)
    
    response = [{
        'key': key,
        'value': result
    }]
    
    cache.set(cache_key, response, CACHE_DURATION)
    
    return response


def extract_arxiv_metadata(entry, ns, arxiv_id, doi):
    """Extract relevant metadata from arXiv API response"""
    result = {}
    
    # arXiv ID and DOI
    result['arxiv_id'] = arxiv_id
    result['doi'] = doi
    
    # Extract ID URL and version
    id_elem = entry.find('atom:id', ns)
    if id_elem is not None:
        result['arxiv_url'] = id_elem.text
        # Extract version from URL if present
        match = re.search(r'v(\d+)$', id_elem.text)
        if match:
            result['version'] = match.group(1)
    
    # Title
    title_elem = entry.find('atom:title', ns)
    if title_elem is not None:
        # Clean up title (remove newlines and extra spaces)
        title = ' '.join(title_elem.text.split())
        result['title'] = title
    
    # Abstract/Summary
    summary_elem = entry.find('atom:summary', ns)
    if summary_elem is not None:
        # Clean up abstract
        abstract = ' '.join(summary_elem.text.split())
        result['abstract'] = abstract
    
    # Authors
    authors = []
    for author_elem in entry.findall('atom:author', ns):
        name_elem = author_elem.find('atom:name', ns)
        if name_elem is not None:
            name = name_elem.text
            # Try to split into first and last name
            parts = name.rsplit(' ', 1)
            if len(parts) == 2:
                given, family = parts
            else:
                given = ''
                family = name
            
            authors.append({
                'name': name,
                'given': given,
                'family': family
            })
    result['authors'] = authors
    
    # Authors in common metadata format
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
    
    # Published date
    published_elem = entry.find('atom:published', ns)
    if published_elem is not None:
        published = published_elem.text
        result['published'] = published
        # Extract year and year-month
        if published:
            result['publication_year'] = published[:4]
            result['publication_year_month'] = published[:7]
    
    # Updated date
    updated_elem = entry.find('atom:updated', ns)
    if updated_elem is not None:
        result['updated'] = updated_elem.text
    
    # Categories
    categories = []
    primary_category = entry.find('arxiv:primary_category', ns)
    if primary_category is not None:
        primary_cat = primary_category.get('term')
        if primary_cat:
            result['primary_category'] = primary_cat
            categories.append(primary_cat)
    
    for cat_elem in entry.findall('atom:category', ns):
        cat = cat_elem.get('term')
        if cat and cat not in categories:
            categories.append(cat)
    
    if categories:
        result['categories'] = categories
    
    # Links (PDF, HTML)
    for link_elem in entry.findall('atom:link', ns):
        rel = link_elem.get('rel')
        href = link_elem.get('href')
        link_type = link_elem.get('type')
        
        if rel == 'alternate' and link_type == 'text/html':
            result['html_url'] = href
        elif rel == 'related' and link_type == 'application/pdf':
            result['pdf_url'] = href
    
    # Journal reference (if published)
    journal_ref_elem = entry.find('arxiv:journal_ref', ns)
    if journal_ref_elem is not None:
        result['journal_ref'] = journal_ref_elem.text
        # Try to parse journal reference
        parse_journal_ref(journal_ref_elem.text, result)
    
    # External DOI (if the paper was published elsewhere)
    external_doi_elem = entry.find('arxiv:doi', ns)
    if external_doi_elem is not None:
        result['external_doi'] = external_doi_elem.text
    
    # Map to common metadata format manuscript type
    if 'primary_category' in result:
        # Most arXiv papers are preprints/articles
        result['manuscript_type_common_metadata_format'] = 'article'
    
    return result


def parse_journal_ref(journal_ref, result):
    """Parse journal reference string to extract structured information"""
    if not journal_ref:
        return
    
    # Common patterns in journal references
    # Example: "Phys. Rev. Lett. 120, 120501 (2018)"
    # Example: "Nature 500, 54-58 (2013)"
    
    # Try to extract year
    year_match = re.search(r'\((\d{4})\)', journal_ref)
    if year_match:
        result['journal_year'] = year_match.group(1)
    
    # Try to extract volume and pages
    # Pattern: "volume, pages"
    vol_page_match = re.search(r'(\d+),\s*([\d\-]+)', journal_ref)
    if vol_page_match:
        result['volume'] = vol_page_match.group(1)
        pages = vol_page_match.group(2)
        if '-' in pages:
            page_parts = pages.split('-')
            result['page_start'] = page_parts[0]
            result['page_end'] = page_parts[1]
        else:
            result['page_start'] = pages
    
    # Extract journal name (everything before the volume/year)
    if vol_page_match:
        journal_name = journal_ref[:vol_page_match.start()].strip()
        result['journal_title'] = journal_name