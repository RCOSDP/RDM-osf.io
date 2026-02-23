# API specifications for JaLC (Japan Link Center) integration

https://api.japanlinkcenter.org/api-docs/index.html#/%2Fv2%2Fdois/3

```
{
  "apiType": "string",
  "apiVersion": "string",
  "data": {
    "access_rights": {
      "access_rights": "string",
      "access_rights_date": "string"
    },
    "advance_date": "string",
    "alternate_identifier_list": [
      {
        "alternate_identifier": "string",
        "type": "string"
      }
    ],
    "article_number": "string",
    "article_type": "string",
    "book_classification": "string",
    "citation_list": [
      {
        "content_language": "string",
        "creator_list": [
          {
            "affiliation_list": [
              {
                "affiliation_identifier_list": [
                  {
                    "affiliation_identifier": "string",
                    "scheme_uri": "string",
                    "type": "string"
                  }
                ],
                "affiliation_name_list": [
                  {
                    "affiliation_name": "string",
                    "lang": "string"
                  }
                ],
                "sequence": "string"
              }
            ],
            "names": [
              {
                "first_name": "string",
                "lang": "string",
                "last_name": "string",
                "prefix": "string",
                "suffix": "string"
              }
            ],
            "researcher_id_list": [
              {
                "id_code": "string",
                "type": "string"
              }
            ],
            "sequence": "string",
            "type": "string"
          }
        ],
        "doi": "string",
        "edition": {
          "format": "string",
          "variation": "string",
          "version": "string"
        },
        "first_page": "string",
        "issue": "string",
        "journal_title_name_list": [
          {
            "journal_title_name": "string",
            "lang": "string",
            "type": "string"
          }
        ],
        "last_page": "string",
        "original_text": "string",
        "publication_date": {
          "publication_day": "string",
          "publication_month": "string",
          "publication_year": "string"
        },
        "sequence": "string",
        "special_issue": "string",
        "special_issue_lang": "string",
        "title_list": [
          {
            "lang": "string",
            "subtitle": "string",
            "title": "string"
          }
        ],
        "volume": "string"
      }
    ],
    "content_language": "string",
    "content_type": "string",
    "contract_number": "string",
    "contributor_list": [
      {
        "affiliation_list": [
          {
            "affiliation_identifier_list": [
              {
                "affiliation_identifier": "string",
                "scheme_uri": "string",
                "type": "string"
              }
            ],
            "affiliation_name_list": [
              {
                "affiliation_name": "string",
                "lang": "string"
              }
            ],
            "sequence": "string"
          }
        ],
        "contributor_type": "string",
        "names": [
          {
            "first_name": "string",
            "lang": "string",
            "last_name": "string",
            "prefix": "string",
            "suffix": "string"
          }
        ],
        "researcher_id_list": [
          {
            "id_code": "string",
            "type": "string"
          }
        ],
        "sequence": "string",
        "type": "string"
      }
    ],
    "creator_list": [
      {
        "affiliation_list": [
          {
            "affiliation_identifier_list": [
              {
                "affiliation_identifier": "string",
                "scheme_uri": "string",
                "type": "string"
              }
            ],
            "affiliation_name_list": [
              {
                "affiliation_name": "string",
                "lang": "string"
              }
            ],
            "sequence": "string"
          }
        ],
        "names": [
          {
            "first_name": "string",
            "lang": "string",
            "last_name": "string",
            "prefix": "string",
            "suffix": "string"
          }
        ],
        "researcher_id_list": [
          {
            "id_code": "string",
            "type": "string"
          }
        ],
        "sequence": "string",
        "type": "string"
      }
    ],
    "date": "string",
    "date_list": [
      {
        "date": "string",
        "type": "string"
      }
    ],
    "description_list": [
      {
        "description": "string",
        "lang": "string",
        "type": "string"
      }
    ],
    "doi": "string",
    "edition": {
      "format": "string",
      "variation": "string",
      "version": "string"
    },
    "first_page": "string",
    "format_list": [
      "string"
    ],
    "fund_list": [
      {
        "award_number_group_list": [
          {
            "award_number_list": [
              {
                "award_number": "string",
                "type": "string"
              }
            ],
            "program_id": "string",
            "program_name": "string",
            "project_name": "string"
          }
        ],
        "funder_identifier_list": [
          {
            "funder_identifier": "string",
            "type": "string"
          }
        ],
        "funder_name": [
          {
            "funder_name": "string",
            "lang": "string"
          }
        ]
      }
    ],
    "geolocation_list": [
      {
        "geolocation_box": "string",
        "geolocation_place": "string",
        "geolocation_point": "string"
      }
    ],
    "institution_list": [
      {
        "institution_acronym": "string",
        "institution_department": "string",
        "institution_name": "string",
        "institution_place": "string"
      }
    ],
    "isbn": "string",
    "isbn_type": "string",
    "issue": "string",
    "journal_classification": "string",
    "journal_id_list": [
      {
        "issn_type": "string",
        "journal_id": "string",
        "type": "string"
      }
    ],
    "journal_title_name_list": [
      {
        "journal_title_name": "string",
        "lang": "string",
        "type": "string"
      }
    ],
    "journal_txt_lang": "string",
    "keyword_list": [
      {
        "keyword": "string",
        "lang": "string",
        "sequence": "string"
      }
    ],
    "last_page": "string",
    "learning_resource_type": "string",
    "meeting_list": [
      {
        "count": "string",
        "lang": "string",
        "meeting_name": "string",
        "place": "string"
      }
    ],
    "prefix": "string",
    "publication_date": {
      "publication_day": "string",
      "publication_month": "string",
      "publication_year": "string"
    },
    "publisher_list": [
      {
        "identifier": "string",
        "identifier_scheme": "string",
        "identifier_scheme_uri": "string",
        "lang": "string",
        "location": "string",
        "publisher_name": "string"
      }
    ],
    "ra": "string",
    "recorded_issue": "string",
    "recorded_volume": "string",
    "recorded_year": "string",
    "relation_list": [
      {
        "content": "string",
        "relation": "string",
        "type": "string"
      }
    ],
    "repository_list": [
      {
        "lang": "string",
        "repository_name": "string"
      }
    ],
    "resource_kind": "string",
    "resource_type": "string",
    "rights_list": [
      {
        "rights": "string",
        "uri": "string"
      }
    ],
    "signature": "string",
    "siteId": "string",
    "site_name": "string",
    "size_list": [
      "string"
    ],
    "special_issue": "string",
    "special_issue_lang": "string",
    "subject_list": [
      {
        "lang": "string",
        "scheme_uri": "string",
        "subject": "string",
        "subject_scheme": "string"
      }
    ],
    "title_list": [
      {
        "lang": "string",
        "subtitle": "string",
        "title": "string"
      }
    ],
    "updated_date": "string",
    "url": "string",
    "volume": "string"
  },
  "message": {
    "errors": {
      "message": "string",
      "statusCode": "string"
    },
    "page": 0,
    "rows": 0,
    "total": 0,
    "totalPages": 0
  },
  "status": "string"
}
```
