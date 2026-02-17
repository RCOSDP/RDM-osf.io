# -*- coding: utf-8 -*-
"""
JaLC (Japan Link Center) suggestion module for fetching publication metadata from DOI
"""
import logging
import re
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

JALC_API_URL = 'https://api.japanlinkcenter.org/v2/dois/'
JALC_TIMEOUT = 10  # seconds


def valid_jalc_key(key):
    """Check if the key is valid for JaLC suggestions"""
    return key.startswith('jalc:')


def suggestion_jalc(key, keyword):
    """
    Fetch publication metadata from JaLC API using DOI

    Args:
        key: The suggestion key (e.g., 'jalc:doi')
        keyword: The DOI to look up

    Returns:
        List of suggestion results with publication metadata
    """
    if not keyword:
        return []

    # Clean the DOI (remove common prefixes if present)
    doi = keyword.strip()
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:', '', doi)

    # Basic DOI format validation
    if not re.match(r'^10\.\d{4,}/[-._;()/:a-zA-Z0-9]+$', doi):
        return []

    # URL encode the DOI for the API request
    encoded_doi = quote(doi, safe='')

    # Call JaLC API
    response = requests.get(
        f'{JALC_API_URL}{encoded_doi}',
        headers={'User-Agent': 'GakuNin-RDM/1.0'},
        timeout=JALC_TIMEOUT
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    data = response.json()

    # Check API status
    if data.get('status') != 'OK':
        return []

    jalc_data = data.get('data', {})

    # Extract metadata
    result = extract_jalc_metadata(jalc_data)
    result['doi'] = doi

    return [{
        'key': key,
        'value': result
    }]


def extract_jalc_metadata(jalc_data):
    """
    Extract relevant metadata from JaLC API response

    Args:
        jalc_data: The 'data' field from JaLC API response

    Returns:
        Dictionary with extracted metadata
    """
    result = {}

    # DOI
    if 'doi' in jalc_data:
        result['doi'] = jalc_data['doi']

    # Title (multiple languages)
    titles = jalc_data.get('title_list', [])
    for title_obj in titles:
        lang = title_obj.get('lang', '')
        title = title_obj.get('title', '')
        subtitle = title_obj.get('subtitle', '')

        if lang == 'ja':
            result['title_ja'] = title
            if subtitle:
                result['subtitle_ja'] = subtitle
        elif lang == 'en':
            result['title'] = title
            result['title_en'] = title
            if subtitle:
                result['subtitle'] = subtitle
                result['subtitle_en'] = subtitle
        elif not result.get('title'):  # Fallback to any language
            result['title'] = title
            if subtitle:
                result['subtitle'] = subtitle

    # Authors/Creators
    authors = []
    for creator in jalc_data.get('creator_list', []):
        author_data = extract_person_data(creator)
        if author_data:
            authors.append(author_data)
    result['authors'] = authors

    # Authors in common metadata format for direct autofill
    result['authors_common_metadata_format'] = []
    for author in authors:
        formatted_author = {}

        # Name fields as objects with first, middle, last
        # For Japanese name
        if 'name_ja' in author:
            formatted_author['name-ja'] = author['name_ja']

        # For English name
        if 'name_en' in author:
            formatted_author['name-en'] = author['name_en']

        # Add affiliation if available
        if 'affiliations' in author and author['affiliations']:
            # Take the first affiliation
            first_affiliation = author['affiliations'][0]
            formatted_author['affiliation-name-ja'] = first_affiliation.get('name_ja', '')
            formatted_author['affiliation-name-en'] = first_affiliation.get('name_en', first_affiliation.get('name', ''))

        result['authors_common_metadata_format'].append(formatted_author)

    # Contributors
    contributors = []
    for contributor in jalc_data.get('contributor_list', []):
        contributor_data = extract_person_data(contributor)
        if contributor_data:
            contributors.append(contributor_data)
    if contributors:
        result['contributors'] = contributors

    # Publication dates
    extract_dates(jalc_data, result)

    # Journal information
    journal_titles = jalc_data.get('journal_title_name_list', [])
    for journal in journal_titles:
        lang = journal.get('lang', '')
        title = journal.get('journal_title_name', '')

        if lang == 'ja':
            result['journal_title_ja'] = title
        elif lang == 'en':
            result['journal_title'] = title
            result['journal_title_en'] = title
        elif not result.get('journal_title'):
            result['journal_title'] = title

    # Volume, Issue, Page
    if 'volume' in jalc_data:
        result['volume'] = jalc_data['volume']

    if 'issue' in jalc_data:
        result['issue'] = jalc_data['issue']

    # Page information
    if 'first_page' in jalc_data:
        result['page_start'] = jalc_data['first_page']
    if 'last_page' in jalc_data:
        result['page_end'] = jalc_data['last_page']

    # Construct page range if both exist
    if 'first_page' in jalc_data and 'last_page' in jalc_data:
        result['page'] = f"{jalc_data['first_page']}-{jalc_data['last_page']}"
    elif 'first_page' in jalc_data:
        result['page'] = jalc_data['first_page']

    # Publisher information
    publishers = jalc_data.get('publisher_list', [])
    for publisher in publishers:
        lang = publisher.get('lang', '')
        name = publisher.get('publisher_name', '')

        if lang == 'ja':
            result['publisher_ja'] = name
        elif lang == 'en':
            result['publisher'] = name
            result['publisher_en'] = name
        elif not result.get('publisher'):
            result['publisher'] = name

    # ISSN/ISBN
    journal_ids = jalc_data.get('journal_id_list', [])
    issn_list = []
    for journal_id in journal_ids:
        if journal_id.get('type') == 'ISSN':
            issn_list.append(journal_id.get('journal_id'))
    if issn_list:
        result['issn'] = issn_list

    if 'isbn' in jalc_data:
        result['isbn'] = jalc_data['isbn']

    # Abstract/Description
    descriptions = jalc_data.get('description_list', [])
    for desc in descriptions:
        lang = desc.get('lang', '')
        text = desc.get('description', '')
        desc_type = desc.get('type', '')

        if desc_type == 'Abstract':
            if lang == 'ja':
                result['abstract_ja'] = text
            elif lang == 'en':
                result['abstract'] = text
                result['abstract_en'] = text
            elif not result.get('abstract'):
                result['abstract'] = text

    # Keywords
    keywords = jalc_data.get('keyword_list', [])
    if keywords:
        result['keywords'] = [kw.get('keyword', '') for kw in keywords]

    # Resource type
    if 'content_type' in jalc_data:
        result['content_type'] = jalc_data['content_type']
        # Map JaLC content type to common metadata format manuscript type
        # Based on observed values and JaLC documentation
        # TODO: Research and add more type mappings from JaLC API documentation
        # Target manuscript types defined in grdm-file:manuscript-type:
        # - conference paper
        # - data paper
        # - departmental bulletin paper
        # - editorial
        # - journal article (confirmed: JA)
        # - review article
        # - software paper
        # - article
        # Observed JaLC content_type values:
        # - JA = Journal Article (confirmed)
        # - GD = General Data (observed, mapping unclear)
        type_mapping = {
            'JA': 'journal article',  # Journal Article (confirmed)
        }
        manuscript_type = type_mapping.get(jalc_data['content_type'])
        if manuscript_type:
            result['manuscript_type_common_metadata_format'] = manuscript_type
    if 'resource_type' in jalc_data:
        result['resource_type'] = jalc_data['resource_type']

    # URL
    if 'url' in jalc_data:
        result['url'] = jalc_data['url']

    # Funding information
    funds = jalc_data.get('fund_list', [])
    if funds:
        result['funders'] = []
        for fund in funds:
            funder_data = {}

            # Funder name
            funder_names = fund.get('funder_name', [])
            for fname in funder_names:
                if fname.get('lang') == 'ja':
                    funder_data['name_ja'] = fname.get('funder_name', '')
                elif fname.get('lang') == 'en':
                    funder_data['name'] = fname.get('funder_name', '')
                    funder_data['name_en'] = fname.get('funder_name', '')

            # Award numbers
            award_groups = fund.get('award_number_group_list', [])
            if award_groups:
                awards = []
                for group in award_groups:
                    for award in group.get('award_number_list', []):
                        awards.append(award.get('award_number', ''))
                if awards:
                    funder_data['award'] = awards

            if funder_data:
                result['funders'].append(funder_data)

    return result


def extract_person_data(person):
    """Extract person data (creator, contributor)"""
    if not person:
        return None

    person_data = {}

    # Extract names in different languages
    names = person.get('names', [])
    for name_obj in names:
        lang = name_obj.get('lang', '')
        first = name_obj.get('first_name', '')
        last = name_obj.get('last_name', '')

        if lang == 'ja':
            person_data['name_ja'] = {
                'last': last,
                'middle': '',
                'first': first
            }
            # Also store as string for compatibility
            if last and first:
                person_data['name_ja_str'] = f'{last} {first}'
            elif last:
                person_data['name_ja_str'] = last
            elif first:
                person_data['name_ja_str'] = first

        elif lang == 'en':
            person_data['name_en'] = {
                'last': last,
                'middle': '',
                'first': first
            }
            # Also store as string for compatibility
            if first and last:
                person_data['name_en_str'] = f'{first} {last}'
            elif last:
                person_data['name_en_str'] = last
            elif first:
                person_data['name_en_str'] = first

    # Type (person, institution, etc.)
    if 'type' in person:
        person_data['type'] = person['type']

    # Sequence
    if 'sequence' in person:
        person_data['sequence'] = person['sequence']

    # Researcher IDs
    researcher_ids = person.get('researcher_id_list', [])
    for rid in researcher_ids:
        if rid.get('type') == 'ORCID':
            person_data['orcid'] = rid.get('id_code', '')
        elif rid.get('type') == 'e-Rad':
            person_data['erad'] = rid.get('id_code', '')

    # Affiliations
    affiliations = person.get('affiliation_list', [])
    if affiliations:
        person_data['affiliations'] = []
        for aff in affiliations:
            aff_data = {}

            # Affiliation names
            aff_names = aff.get('affiliation_name_list', [])
            for aff_name in aff_names:
                if isinstance(aff_name, dict):
                    lang = aff_name.get('lang', '')
                    name = aff_name.get('affiliation_name', '')
                    if lang == 'ja':
                        aff_data['name_ja'] = name
                    elif lang == 'en':
                        aff_data['name'] = name
                        aff_data['name_en'] = name
                elif isinstance(aff_name, str):
                    # Sometimes it's just a string
                    aff_data['name'] = aff_name

            if aff_data:
                person_data['affiliations'].append(aff_data)

    return person_data if person_data else None


def extract_dates(jalc_data, result):
    """Extract various date fields from JaLC data"""

    # Main publication date
    pub_date = jalc_data.get('publication_date', {})
    if pub_date:
        year = pub_date.get('publication_year', '')
        month = pub_date.get('publication_month', '')
        day = pub_date.get('publication_day', '')

        # Construct date string
        if year:
            date_str = year
            if month:
                # Ensure month is two digits
                month = str(month).zfill(2)
                date_str = f'{year}-{month}'
                result['publication_year_month'] = date_str
                if day:
                    # Ensure day is two digits
                    day = str(day).zfill(2)
                    date_str = f'{year}-{month}-{day}'
            else:
                result['publication_year_month'] = year

            result['publication_date'] = date_str
            result['publication_year'] = year

    # Other dates
    date_list = jalc_data.get('date_list', [])
    for date_obj in date_list:
        date_type = date_obj.get('type', '')
        date_value = date_obj.get('date', '')

        if date_type == 'Issued' and date_value:
            result['issued'] = date_value
        elif date_type == 'Created' and date_value:
            result['created'] = date_value
        elif date_type == 'Updated' and date_value:
            result['updated'] = date_value
        elif date_type == 'Available' and date_value:
            result['available'] = date_value

    # Advance date (for preprints)
    if 'advance_date' in jalc_data:
        result['advance_date'] = jalc_data['advance_date']

    # Updated date
    if 'updated_date' in jalc_data:
        result['updated_date'] = jalc_data['updated_date']
