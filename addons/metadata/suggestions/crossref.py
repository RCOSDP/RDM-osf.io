# -*- coding: utf-8 -*-
"""
Crossref suggestion module for fetching publication metadata from DOI
"""
import logging
import re
import requests

logger = logging.getLogger(__name__)

CROSSREF_API_URL = 'https://api.crossref.org/works/'
CROSSREF_TIMEOUT = 10  # seconds


def valid_crossref_key(key):
    """Check if the key is valid for Crossref suggestions"""
    return key.startswith('crossref:')


def suggestion_crossref(key, keyword):
    """
    Fetch publication metadata from Crossref API using DOI

    Args:
        key: The suggestion key (e.g., 'crossref:doi')
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

    # Call Crossref API
    response = requests.get(
        f'{CROSSREF_API_URL}{doi}',
        headers={'User-Agent': 'GakuNin-RDM/1.0'},
        timeout=CROSSREF_TIMEOUT
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    data = response.json()
    message = data.get('message', {})

    # Extract metadata
    result = extract_crossref_metadata(message)
    result['doi'] = doi

    return [{
        'key': key,
        'value': result
    }]


def extract_crossref_metadata(message):
    """
    Extract relevant metadata from Crossref API response
    Based on the complete API specification

    Args:
        message: The 'message' field from Crossref API response

    Returns:
        Dictionary with extracted metadata
    """
    result = {}

    # DOI
    if 'DOI' in message:
        result['doi'] = message['DOI']

    # Title (main and subtitle)
    titles = message.get('title', [])
    if titles:
        result['title'] = titles[0]

    subtitles = message.get('subtitle', [])
    if subtitles:
        result['subtitle'] = subtitles[0]

    original_titles = message.get('original-title', [])
    if original_titles:
        result['original_title'] = original_titles[0]

    # Short title
    short_titles = message.get('short-title', [])
    if short_titles:
        result['short_title'] = short_titles[0]

    # Authors
    authors = []
    for author in message.get('author', []):
        author_data = extract_person_data(author)
        if author_data:
            authors.append(author_data)
    result['authors'] = authors

    # Authors in common metadata format for direct autofill
    result['authors_common_metadata_format'] = []
    for author in authors:
        formatted_author = {}

        # Only English name since Crossref only contains English data
        formatted_author['name-en'] = {
            'last': author.get('family', ''),
            'middle': '',
            'first': author.get('given', '')
        }

        # Add affiliation if available
        if 'affiliations' in author and author['affiliations']:
            # Take the first affiliation
            first_affiliation = author['affiliations'][0]
            formatted_author['affiliation-name-ja'] = ''  # Crossref doesn't have Japanese names
            formatted_author['affiliation-name-en'] = first_affiliation.get('name', '')

        result['authors_common_metadata_format'].append(formatted_author)

    # Editors
    editors = []
    for editor in message.get('editor', []):
        editor_data = extract_person_data(editor)
        if editor_data:
            editors.append(editor_data)
    result['editors'] = editors

    # Translators
    translators = []
    for translator in message.get('translator', []):
        translator_data = extract_person_data(translator)
        if translator_data:
            translators.append(translator_data)
    result['translators'] = translators

    # Chair
    chairs = []
    for chair in message.get('chair', []):
        chair_data = extract_person_data(chair)
        if chair_data:
            chairs.append(chair_data)
    result['chairs'] = chairs

    # Publication dates
    extract_dates(message, result)

    # Journal/Container information
    container_title = message.get('container-title', [])
    if container_title:
        result['journal_title'] = container_title[0]

    short_container_title = message.get('short-container-title', [])
    if short_container_title:
        result['journal_title_short'] = short_container_title[0]

    # Volume, Issue, Page
    if 'volume' in message:
        result['volume'] = message['volume']

    if 'issue' in message:
        result['issue'] = message['issue']

    if 'page' in message:
        page_value = message['page']
        result['page'] = page_value

        # Parse page range (e.g., "123-145" or "e1-e10") or single page
        if '-' in page_value:
            # Handle page range
            page_parts = page_value.split('-')
            if len(page_parts) >= 1:
                result['page_start'] = page_parts[0].strip()
            if len(page_parts) >= 2:
                result['page_end'] = page_parts[-1].strip()  # Use last part to handle ranges like "e1-e10"
        else:
            # Single page number
            result['page_start'] = page_value.strip()

    if 'article-number' in message:
        result['article_number'] = message['article-number']

    # Publisher information
    if 'publisher' in message:
        result['publisher'] = message['publisher']

    if 'publisher-location' in message:
        result['publisher_location'] = message['publisher-location']

    # Group title (for preprints)
    if 'group-title' in message:
        result['group_title'] = message['group-title']

    # ISSN and ISBN
    issn_list = message.get('ISSN', [])
    if issn_list:
        result['issn'] = issn_list

    issn_type = message.get('issn-type', [])
    if issn_type:
        result['issn_type'] = [{
            'type': item.get('type'),
            'value': item.get('value')
        } for item in issn_type]

    isbn_list = message.get('ISBN', [])
    if isbn_list:
        result['isbn'] = isbn_list

    isbn_type = message.get('isbn-type', [])
    if isbn_type:
        result['isbn_type'] = [{
            'type': item.get('type'),
            'value': item.get('value')
        } for item in isbn_type]

    # Abstract and description
    if 'abstract' in message:
        # Remove XML/HTML tags if present
        abstract = re.sub(r'<[^>]+>', '', message['abstract'])
        result['abstract'] = abstract

    if 'description' in message:
        result['description'] = message['description']

    # License information
    licenses = message.get('license', [])
    if licenses:
        result['licenses'] = []
        for lic in licenses:
            lic_data = {
                'url': lic.get('URL', ''),
                'content_version': lic.get('content-version', ''),
                'delay_in_days': lic.get('delay-in-days', 0)
            }
            if 'start' in lic:
                lic_data['start'] = extract_date_string(lic['start'])
            result['licenses'].append(lic_data)

    # Funder information
    funders = message.get('funder', [])
    if funders:
        result['funders'] = []
        for funder in funders:
            funder_data = {
                'name': funder.get('name', ''),
                'doi': funder.get('DOI', ''),
                'award': funder.get('award', [])
            }
            result['funders'].append(funder_data)

    # Type and subtype
    if 'type' in message:
        result['type'] = message['type']
        # Map Crossref type to common metadata format manuscript type
        # Only use confirmed mappings
        # TODO: Research and add more type mappings from Crossref documentation
        # Target manuscript types defined in grdm-file:manuscript-type:
        # - conference paper (confirmed: proceedings-article)
        # - data paper
        # - departmental bulletin paper
        # - editorial
        # - journal article (confirmed: journal-article)
        # - review article
        # - software paper
        # - article
        type_mapping = {
            'journal-article': 'journal article',  # Confirmed
            'proceedings-article': 'conference paper',  # Confirmed
        }
        manuscript_type = type_mapping.get(message['type'])
        if manuscript_type:
            result['manuscript_type_common_metadata_format'] = manuscript_type

    if 'subtype' in message:
        result['subtype'] = message['subtype']

    # Subjects
    subjects = message.get('subject', [])
    if subjects:
        result['subjects'] = subjects

    # Language
    if 'language' in message:
        result['language'] = message['language']

    # Edition
    if 'edition-number' in message:
        result['edition_number'] = message['edition-number']

    # Degree (for thesis)
    degrees = message.get('degree', [])
    if degrees:
        result['degrees'] = degrees

    # Event information (for conferences)
    if 'event' in message:
        event = message['event']
        result['event'] = {
            'name': event.get('name', ''),
            'location': event.get('location', '')
        }
        if 'start' in event:
            result['event']['start'] = extract_date_string(event['start'])
        if 'end' in event:
            result['event']['end'] = extract_date_string(event['end'])

    # Institution information
    institutions = message.get('institution', [])
    if institutions:
        result['institutions'] = []
        for inst in institutions:
            inst_data = {
                'name': inst.get('name', ''),
                'place': inst.get('place', []),
                'department': inst.get('department', []),
                'acronym': inst.get('acronym', [])
            }
            result['institutions'].append(inst_data)

    # Reference count
    if 'reference-count' in message:
        result['reference_count'] = message['reference-count']

    if 'references-count' in message:
        result['references_count'] = message['references-count']

    if 'is-referenced-by-count' in message:
        result['is_referenced_by_count'] = message['is-referenced-by-count']

    # URL
    if 'URL' in message:
        result['url'] = message['URL']

    # Clinical trial number
    clinical_trials = message.get('clinical-trial-number', [])
    if clinical_trials:
        result['clinical_trials'] = []
        for trial in clinical_trials:
            result['clinical_trials'].append({
                'number': trial.get('clinical-trial-number', ''),
                'registry': trial.get('registry', ''),
                'type': trial.get('type', '')
            })

    # Relations
    if 'relation' in message:
        result['relations'] = message['relation']

    # Update policy
    if 'update-policy' in message:
        result['update_policy'] = message['update-policy']

    # Archive
    archives = message.get('archive', [])
    if archives:
        result['archives'] = archives

    return result


def extract_person_data(person):
    """Extract person data (author, editor, translator, etc.)"""
    if not person:
        return None

    given = person.get('given', '')
    family = person.get('family', '')

    if not family and not given and not person.get('name'):
        return None

    person_data = {}

    # Names
    if family:
        person_data['family'] = family
    if given:
        person_data['given'] = given

    # Full name variations
    if person.get('name'):
        person_data['name'] = person['name']
    else:
        if family and given:
            person_data['name_ja'] = f"{family}, {given}"
            person_data['name_en'] = f"{given} {family}"
        elif family:
            person_data['name_ja'] = family
            person_data['name_en'] = family
        elif given:
            person_data['name_ja'] = given
            person_data['name_en'] = given

    # ORCID
    if 'ORCID' in person:
        person_data['orcid'] = person['ORCID']

    if 'authenticated-orcid' in person:
        person_data['authenticated_orcid'] = person['authenticated-orcid']

    # Name parts
    if 'prefix' in person:
        person_data['prefix'] = person['prefix']

    if 'suffix' in person:
        person_data['suffix'] = person['suffix']

    # Sequence
    if 'sequence' in person:
        person_data['sequence'] = person['sequence']

    # Affiliation
    affiliations = person.get('affiliation', [])
    if affiliations:
        person_data['affiliations'] = []
        for aff in affiliations:
            aff_data = {
                'name': aff.get('name', ''),
                'place': aff.get('place', []),
                'department': aff.get('department', []),
                'acronym': aff.get('acronym', [])
            }
            person_data['affiliations'].append(aff_data)

    return person_data


def extract_dates(message, result):
    """Extract various date fields from the message"""

    # Main publication date (prioritize print over online)
    main_date = None

    if 'published-print' in message:
        result['published_print'] = extract_date_string(message['published-print'])
        main_date = result['published_print']

    if 'published-online' in message:
        result['published_online'] = extract_date_string(message['published-online'])
        if not main_date:
            main_date = result['published_online']

    if 'published' in message:
        result['published'] = extract_date_string(message['published'])
        if not main_date:
            main_date = result['published']

    if 'published-other' in message:
        result['published_other'] = extract_date_string(message['published-other'])
        if not main_date:
            main_date = result['published_other']

    # Set publication_date and publication_year from the main date
    if main_date:
        result['publication_date'] = main_date
        # Extract year from the date string (YYYY or YYYY-MM or YYYY-MM-DD)
        year_match = re.match(r'^(\d{4})', main_date)
        if year_match:
            result['publication_year'] = year_match.group(1)
        # Extract year-month for date-published field (YYYY-MM format)
        year_month_match = re.match(r'^(\d{4}-\d{2})', main_date)
        if year_month_match:
            result['publication_year_month'] = year_month_match.group(1)
        elif year_match:
            # If only year is available, just use the year
            result['publication_year_month'] = year_match.group(1)

    # Other dates
    if 'created' in message:
        result['created'] = extract_date_string(message['created'])

    if 'deposited' in message:
        result['deposited'] = extract_date_string(message['deposited'])

    if 'indexed' in message:
        result['indexed'] = extract_date_string(message['indexed'])

    if 'issued' in message:
        result['issued'] = extract_date_string(message['issued'])

    if 'posted' in message:
        result['posted'] = extract_date_string(message['posted'])

    if 'accepted' in message:
        result['accepted'] = extract_date_string(message['accepted'])

    if 'approved' in message:
        result['approved'] = extract_date_string(message['approved'])

    if 'content-created' in message:
        result['content_created'] = extract_date_string(message['content-created'])

    if 'content-updated' in message:
        result['content_updated'] = extract_date_string(message['content-updated'])


def extract_date_string(date_obj):
    """Extract date string from date object"""
    if not date_obj:
        return None

    date_parts = date_obj.get('date-parts', [])
    if date_parts and date_parts[0]:
        parts = date_parts[0]
        if len(parts) >= 3:
            return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
        elif len(parts) == 2:
            return f"{parts[0]:04d}-{parts[1]:02d}"
        elif len(parts) == 1:
            return f"{parts[0]:04d}"

    # Fallback to date-time if available
    if 'date-time' in date_obj:
        return date_obj['date-time']

    return None