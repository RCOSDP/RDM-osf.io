# API specifications for PubMed integration

## API Endpoints

### 1. ESearch - Search for PubMed IDs
```
GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
```

Parameters:
- `db=pubmed`
- `term=<DOI or PMID>`
- `retmode=json`
- `api_key=<key>` (optional, from settings.PUBMED_API_KEY)

Response:
```json
{
  "esearchresult": {
    "idlist": ["23903748"]
  }
}
```

### 2. ESummary - Get article metadata
```
GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi
```

Parameters:
- `db=pubmed`
- `id=<PMID>`
- `retmode=json`
- `api_key=<key>` (optional, from settings.PUBMED_API_KEY)

Response:
```json
{
  "result": {
    "23903748": {
      "uid": "23903748",
      "title": "Nanometre-scale thermometry in a living cell.",
      "source": "Nature",
      "authors": [
        {"name": "Kucsko G"},
        {"name": "Maurer PC"}
      ],
      "pubdate": "2013 Aug 1",
      "volume": "500",
      "issue": "7460",
      "pages": "54-8",
      "articleids": [
        {"idtype": "doi", "value": "10.1038/nature12373"},
        {"idtype": "pmc", "value": "PMC4221854"}
      ]
    }
  }
}
```

## Configuration
- API key: Set `PUBMED_API_KEY` in settings
- Rate limits:
  - Without API key: 3 requests/second
  - With API key: 10 requests/second

## Caching
- Cache DOI → metadata mappings to reduce API calls
- Cache duration: 24 hours (configurable)
- Use same caching mechanism as CrossRef/JaLC implementations