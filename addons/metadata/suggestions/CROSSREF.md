# API specifications for CrossRef integration

https://api.crossref.org/swagger-ui/index.html#/Works/get_works__doi_

```
{
  "status": "string",
  "message-type": "work",
  "message-version": "string",
  "message": {
    "institution": [
      {
        "name": "string",
        "place": [
          "string"
        ],
        "department": [
          "string"
        ],
        "acronym": [
          "string"
        ],
        "id": [
          {
            "id": "string",
            "id-type": "string",
            "asserted-by": "string"
          }
        ]
      }
    ],
    "indexed": {
      "date-parts": [
        [
          0
        ]
      ],
      "version": "string"
    },
    "description": "string",
    "posted": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "publisher-location": "string",
    "update-to": [
      {
        "label": "string",
        "DOI": "string",
        "type": "string",
        "source": "string",
        "updated": {
          "date-parts": [
            [
              0
            ]
          ],
          "date-time": "2025-08-13T08:55:59.317Z",
          "timestamp": 0
        },
        "record-id": "string"
      }
    ],
    "standards-body": {
      "name": "string",
      "acronym": "string"
    },
    "edition-number": "string",
    "group-title": "string",
    "reference-count": 0,
    "publisher": "string",
    "issue": "string",
    "isbn-type": [
      {
        "type": "string",
        "value": "string"
      }
    ],
    "license": [
      {
        "URL": "string",
        "start": {
          "date-parts": [
            [
              0
            ]
          ],
          "date-time": "2025-08-13T08:55:59.317Z",
          "timestamp": 0
        },
        "delay-in-days": 0,
        "content-version": "string"
      }
    ],
    "funder": [
      {
        "name": "string",
        "DOI": "string",
        "doi-asserted-by": "string",
        "award": [
          "string"
        ],
        "id": [
          {
            "id": "string",
            "id-type": "string",
            "asserted-by": "string"
          }
        ]
      }
    ],
    "content-domain": {
      "domain": [
        "string"
      ],
      "crossmark-restriction": true
    },
    "chair": [
      {
        "ORCID": "string",
        "suffix": "string",
        "given": "string",
        "family": "string",
        "affiliation": [
          {
            "name": "string",
            "place": [
              "string"
            ],
            "department": [
              "string"
            ],
            "acronym": [
              "string"
            ],
            "id": [
              {
                "id": "string",
                "id-type": "string",
                "asserted-by": "string"
              }
            ]
          }
        ],
        "name": "string",
        "authenticated-orcid": true,
        "prefix": "string",
        "sequence": "string"
      }
    ],
    "short-container-title": [
      "string"
    ],
    "accepted": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "special-numbering": "string",
    "content-updated": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "published-print": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "abstract": "string",
    "DOI": "string",
    "type": "string",
    "created": {
      "date-parts": [
        [
          0
        ]
      ],
      "date-time": "2025-08-13T08:55:59.317Z",
      "timestamp": 0
    },
    "approved": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "page": "string",
    "update-policy": "string",
    "source": "string",
    "is-referenced-by-count": 0,
    "title": [
      "string"
    ],
    "prefix": "string",
    "volume": "string",
    "clinical-trial-number": [
      {
        "clinical-trial-number": "string",
        "registry": "string",
        "type": "string"
      }
    ],
    "author": [
      {
        "ORCID": "string",
        "suffix": "string",
        "given": "string",
        "family": "string",
        "affiliation": [
          {
            "name": "string",
            "place": [
              "string"
            ],
            "department": [
              "string"
            ],
            "acronym": [
              "string"
            ],
            "id": [
              {
                "id": "string",
                "id-type": "string",
                "asserted-by": "string"
              }
            ]
          }
        ],
        "name": "string",
        "authenticated-orcid": true,
        "prefix": "string",
        "sequence": "string"
      }
    ],
    "member": "string",
    "content-created": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "published-online": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "reference": [
      {
        "issn": "string",
        "standards-body": "string",
        "issue": "string",
        "key": "string",
        "series-title": "string",
        "isbn-type": "string",
        "doi-asserted-by": "string",
        "first-page": "string",
        "DOI": "string",
        "type": "string",
        "isbn": "string",
        "component": "string",
        "article-title": "string",
        "volume-title": "string",
        "volume": "string",
        "author": "string",
        "standard-designator": "string",
        "year": "string",
        "unstructured": "string",
        "edition": "string",
        "journal-title": "string",
        "issn-type": "string"
      }
    ],
    "updated-by": [
      {
        "label": "string",
        "DOI": "string",
        "type": "string",
        "source": "string",
        "updated": {
          "date-parts": [
            [
              0
            ]
          ],
          "date-time": "2025-08-13T08:55:59.317Z",
          "timestamp": 0
        },
        "record-id": "string"
      }
    ],
    "event": {
      "name": "string",
      "location": "string",
      "start": {
        "date-parts": [
          [
            "string"
          ]
        ]
      },
      "end": {
        "date-parts": [
          [
            "string"
          ]
        ]
      }
    },
    "container-title": [
      "string"
    ],
    "review": {
      "type": "string",
      "running-number": "string",
      "revision-round": "string",
      "stage": "string",
      "competing-interest-statement": "string",
      "recommendation": "string",
      "language": "string"
    },
    "project": [
      {
        "award-end": [
          {
            "date-parts": [
              [
                "string"
              ]
            ]
          }
        ],
        "award-planned-start": [
          {
            "date-parts": [
              [
                "string"
              ]
            ]
          }
        ],
        "award-start": [
          {
            "date-parts": [
              [
                "string"
              ]
            ]
          }
        ],
        "lead-investigator": [
          {
            "ORCID": "string",
            "suffix": "string",
            "given": "string",
            "family": "string",
            "affiliation": [
              {
                "id": [
                  {
                    "id": "string",
                    "id-type": "string",
                    "asserted-by": "string"
                  }
                ],
                "name": "string"
              }
            ],
            "name": "string",
            "role-start": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            },
            "authenticated-orcid": true,
            "prefix": "string",
            "alternate-name": "string",
            "sequence": "string",
            "role-end": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            }
          }
        ],
        "award-planned-end": [
          {
            "date-parts": [
              [
                "string"
              ]
            ]
          }
        ],
        "investigator": [
          {
            "ORCID": "string",
            "suffix": "string",
            "given": "string",
            "family": "string",
            "affiliation": [
              {
                "id": [
                  {
                    "id": "string",
                    "id-type": "string",
                    "asserted-by": "string"
                  }
                ],
                "name": "string"
              }
            ],
            "name": "string",
            "role-start": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            },
            "authenticated-orcid": true,
            "prefix": "string",
            "alternate-name": "string",
            "sequence": "string",
            "role-end": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            }
          }
        ],
        "funding": [
          {
            "type": "string",
            "scheme": "string",
            "award-amount": {
              "amount": 0,
              "currency": "string",
              "percentage": 0
            },
            "funder": {
              "name": "string",
              "DOI": "string",
              "doi-asserted-by": "string",
              "award": [
                "string"
              ],
              "id": [
                {
                  "id": "string",
                  "id-type": "string",
                  "asserted-by": "string"
                }
              ]
            }
          }
        ],
        "project-title": [
          {
            "title": "string",
            "language": "string"
          }
        ],
        "award-amount": {
          "amount": 0,
          "currency": "string",
          "percentage": 0
        },
        "co-lead-investigator": [
          {
            "ORCID": "string",
            "suffix": "string",
            "given": "string",
            "family": "string",
            "affiliation": [
              {
                "id": [
                  {
                    "id": "string",
                    "id-type": "string",
                    "asserted-by": "string"
                  }
                ],
                "name": "string"
              }
            ],
            "name": "string",
            "role-start": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            },
            "authenticated-orcid": true,
            "prefix": "string",
            "alternate-name": "string",
            "sequence": "string",
            "role-end": {
              "date-parts": [
                [
                  "string"
                ]
              ]
            }
          }
        ],
        "project-description": [
          {
            "description": "string",
            "language": "string"
          }
        ]
      }
    ],
    "original-title": [
      "string"
    ],
    "status": {
      "type": "string",
      "update": {
        "date-parts": [
          [
            "string"
          ]
        ]
      },
      "status-description": [
        {
          "language": "string",
          "description": "string"
        }
      ]
    },
    "language": "string",
    "link": [
      {
        "URL": "string",
        "content-type": "string",
        "content-version": "string",
        "intended-application": "string"
      }
    ],
    "deposited": {
      "date-parts": [
        [
          0
        ]
      ],
      "date-time": "2025-08-13T08:55:59.317Z",
      "timestamp": 0
    },
    "score": 0,
    "degree": [
      "string"
    ],
    "resource": {
      "primary": {
        "URL": "string"
      },
      "secondary": [
        {
          "URL": "string",
          "label": "string"
        }
      ]
    },
    "subtitle": [
      "string"
    ],
    "translator": [
      {
        "ORCID": "string",
        "suffix": "string",
        "given": "string",
        "family": "string",
        "affiliation": [
          {
            "name": "string",
            "place": [
              "string"
            ],
            "department": [
              "string"
            ],
            "acronym": [
              "string"
            ],
            "id": [
              {
                "id": "string",
                "id-type": "string",
                "asserted-by": "string"
              }
            ]
          }
        ],
        "name": "string",
        "authenticated-orcid": true,
        "prefix": "string",
        "sequence": "string"
      }
    ],
    "free-to-read": {
      "start-date": {
        "date-parts": [
          [
            "string"
          ]
        ]
      },
      "end-date": {
        "date-parts": [
          [
            "string"
          ]
        ]
      }
    },
    "editor": [
      {
        "ORCID": "string",
        "suffix": "string",
        "given": "string",
        "family": "string",
        "affiliation": [
          {
            "name": "string",
            "place": [
              "string"
            ],
            "department": [
              "string"
            ],
            "acronym": [
              "string"
            ],
            "id": [
              {
                "id": "string",
                "id-type": "string",
                "asserted-by": "string"
              }
            ]
          }
        ],
        "name": "string",
        "authenticated-orcid": true,
        "prefix": "string",
        "sequence": "string"
      }
    ],
    "proceedings-subject": "string",
    "component-number": "string",
    "short-title": [
      "string"
    ],
    "issued": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "ISBN": [
      "string"
    ],
    "references-count": 0,
    "part-number": "string",
    "aliases": [
      "string"
    ],
    "issue-title": [
      "string"
    ],
    "journal-issue": {
      "issue": "string",
      "published-online": {
        "date-parts": [
          [
            "string"
          ]
        ]
      },
      "published-print": {
        "date-parts": [
          [
            "string"
          ]
        ]
      }
    },
    "alternative-id": [
      "string"
    ],
    "version": {
      "version": "string",
      "language": "string",
      "version-description": [
        {
          "language": "string",
          "description": "string"
        }
      ]
    },
    "URL": "string",
    "archive": [
      "string"
    ],
    "relation": {
      "additionalProp1": [
        {
          "id-type": "string",
          "id": "string",
          "asserted-by": "string"
        }
      ],
      "additionalProp2": [
        {
          "id-type": "string",
          "id": "string",
          "asserted-by": "string"
        }
      ],
      "additionalProp3": [
        {
          "id-type": "string",
          "id": "string",
          "asserted-by": "string"
        }
      ]
    },
    "ISSN": [
      "string"
    ],
    "issn-type": [
      {
        "type": "string",
        "value": "string"
      }
    ],
    "subject": [
      "string"
    ],
    "published-other": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "published": {
      "date-parts": [
        [
          "string"
        ]
      ]
    },
    "assertion": [
      {
        "group": {
          "name": "string",
          "label": "string"
        },
        "explanation": {
          "URL": "string"
        },
        "name": "string",
        "value": "string",
        "URL": "string",
        "order": 0,
        "label": "string"
      }
    ],
    "subtype": "string",
    "article-number": "string"
  }
}
```
