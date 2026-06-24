# API specifications for arXiv integration

## API Endpoint

### Query API - Search by arXiv ID or DOI
```
GET https://export.arxiv.org/api/query
```

Parameters:
- `id_list=<arxiv_id>` - arXiv ID (e.g., 2301.08727)
- `max_results=1` - Limit to single result

Response:
```xml
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.08727v2</id>
    <title>Neural Architecture Search: Insights from 1000 Papers</title>
    <summary>In the past decade, advances in deep learning...</summary>
    <author><name>Colin White</name></author>
    <published>2023-01-20T18:47:24Z</published>
    <updated>2023-01-25T08:01:55Z</updated>
    <arxiv:primary_category term="cs.LG"/>
    <link href="http://arxiv.org/pdf/2301.08727v2" type="application/pdf"/>
  </entry>
</feed>
```

## DOI Support
- arXiv automatically assigns DOIs to all papers
- DOI format: `10.48550/arXiv.{arxiv_id}`
- Example: `10.48550/arXiv.2301.08727`
- Convert DOI to arXiv ID by extracting the ID after `arXiv.`

## Configuration
- No API key required
- Rate limit: 3 seconds between requests (recommended)

## Caching
- Cache DOI/arXiv ID → metadata mappings to reduce API calls
- Cache duration: 24 hours (configurable)
- Use same caching mechanism as CrossRef/JaLC/PubMed implementations