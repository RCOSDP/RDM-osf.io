REPOSITORIES = {}
REPOSITORY_IDS = list(sorted(REPOSITORIES.keys()))
REFRESH_TIME = 5 * 60  # 5 minutes

DEFAULT_REGISTRATION_SCHEMA_NAME = '公的資金による研究データのメタデータ登録'

# TODO 外部ファイルで定義し、DBに保存するようにする
MAPPINGS = {
    # Mapping GakuNin RDM metadata -> WEKO3 item mapping
    # The mapping defines the information of the conversion destination item using the qid of the GakuNin RDM metadata as the key.
    '公的資金による研究データのメタデータ登録': {
        'funder': {
            '@type': 'string',
            # @createIf: 値を指定すると、その値が長さ1以上の文字列だった場合に要素が表示される
            '@createIf': '{{value}}',
            # 変換先アイテムの識別子を列挙する
            # Funding Reference https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.1
            # マッピング先アイテム末尾に[識別名]を指定すると、識別名で参照可能なアイテムとして新規にアイテムが追加される
            # すでに識別名で指定されたアイテムが存在する場合は新規にアイテムは追加されない
            'item_1617186901218[FUNDING]': {
                # Funder Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.1
                'subitem_1522399143519': {
                    # - funderIdentifierType
                    # TODO JPCOAR 2.0未対応
                    #'subitem_1522399281603': 'e-Rad_funder',
                    'subitem_1522399281603': 'Other',
                    # - funderIdentifierTypeURI
                    'subitem_1522399333375': '{{value}}',
                },
            },
        },
        'funding-stream-code': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # TODO JPCOAR 2.0未対応: https://schema.irdb.nii.ac.jp/ja/schema/2.0/23-.3
        },
        'program-name-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # TODO JPCOAR 2.0未対応: https://schema.irdb.nii.ac.jp/ja/schema/2.0/23-.4
        },
        'program-name-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # TODO JPCOAR 2.0未対応: https://schema.irdb.nii.ac.jp/ja/schema/2.0/23-.4
        },
        'japan-grant-number': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Funding Reference https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.1
            'item_1617186901218[FUNDING]': {
                # Award Number https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.5
                'subitem_1522399571623': {
                    # TODO JPCOAR 2.0未対応: - awardNumberType
                    # - awardNumber
                    'subitem_1522399628911': '{{value}}'
                },
            },
        },
        'project-name-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Funding Reference https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.1
            'item_1617186901218[FUNDING]': {
                # Award Title https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.6
                # マッピング先アイテム末尾に[]を指定すると、新規にアイテムを追加する
                'subitem_1522399651758[]': {
                    # - lang
                    'subitem_1522721910626': 'ja',
                    # - awardTitle
                    'subitem_1522721929892': '{{value}}',
                },
            },
        },
        'project-name-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Funding Reference https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.1
            'item_1617186901218[FUNDING]': {
                # Award Title https://schema.irdb.nii.ac.jp/en/schema/2.0/23-.6
                'subitem_1522399651758[]': {
                    # - lang
                    'subitem_1522721910626': 'en',
                    # - awardTitle
                    'subitem_1522721929892': '{{value}}',
                },
            },
        },
        # project-research-fieldの値はgrdm-file:data-research-fieldで利用するのでSkip
        'project-research-field': None,
        # grdm-filesはProject Metadataに紐づいたファイルメタデータを保持する。これはWEKOに送信不要。Skip
        'grdm-files': None,
        'grdm-file:data-number': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Relation https://schema.irdb.nii.ac.jp/en/schema/2.0/20
            'item_1617353299429[]': {
                #  - relationType: isIdenticalTo
                'subitem_1522306207484': 'isIdenticalTo',
                #  - relatedIdentifier
                'subitem_1522306287251': {
                    'subitem_1522306382014': 'Local',
                    #    - identifierType: Local
                    'subitem_1522306436033': '{{value}}',
                    #    - identifier: {value}
                },
            },
        },
        'grdm-file:title-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Title: https://schema.irdb.nii.ac.jp/en/schema/2.0/1
            'item_1617186331708[]': {
                'subitem_1551255647225': '{{value}}',
                'subitem_1551255648112': 'ja',
            },
        },
        'grdm-file:title-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Title: https://schema.irdb.nii.ac.jp/en/schema/2.0/1
            'item_1617186331708[]': {
                'subitem_1551255647225': '{{value}}',
                'subitem_1551255648112': 'en',
            },
        },
        # "掲載日と掲載更新日の区別がないため、受入システム側（IRDB or CiR）で判断する必要がある。
        # → OAI-PMH、ResourceSyncで同期するシステムでは、タイムスタンプを利用可能。"
        'grdm-file:date-issued-updated': None,
        'grdm-file:data-description-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Description https://schema.irdb.nii.ac.jp/en/schema/2.0/9
            'item_1617186626617[]': {
                # TODO 要決定 空文字列 or 固定値
                'subitem_description_type': 'Other',
                'subitem_description': '{{value}}',
                'subitem_description_language': 'ja',
            }
        },
        'grdm-file:data-description-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Description https://schema.irdb.nii.ac.jp/en/schema/2.0/9
            'item_1617186626617[]': {
                # TODO 要決定 空文字列 or 固定値
                'subitem_description_type': 'Other',
                'subitem_description': '{{value}}',
                'subitem_description_language': 'en',
            },
        },
        'grdm-file:data-research-field': {
            '@type': 'string',
            '@createIf': '{{grdm_file_data_research_field_value}}{{project_research_field_value}}',
            # Subject https://schema.irdb.nii.ac.jp/en/schema/2.0/8
            'item_1617186609386[RESEARCH_FIELD_JA]': {
                # TODO 'subitem_1522300014469': 'e-Rad_field',
                'subitem_1522300014469': 'Other',
                'subitem_1523261968819': '{% if grdm_file_data_research_field_value != "project" %}{{grdm_file_data_research_field_tooltip_0}}{% else %}{{project_research_field_tooltip_0}}{% endif %}',
                'subitem_1522299896455': 'ja',
            },
            'item_1617186609386[RESEARCH_FIELD_EN]': {
                # TODO 'subitem_1522300014469': 'e-Rad_field',
                'subitem_1522300014469': 'Other',
                'subitem_1523261968819': '{% if grdm_file_data_research_field_value != "project" %}{{grdm_file_data_research_field_tooltip_1}}{% else %}{{project_research_field_tooltip_1}}{% endif %}',
                'subitem_1522299896455': 'en',
            },
        },
        'grdm-file:data-type': {
            '@type': 'string',
            '@createIf': '{% if context == "file" %}{{value}}{% endif %}',
            'item_1617258105262': {
                'resourcetype': '{{value}}',
            },
        },
        'grdm-file:file-size': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # TBD 複数ファイルの場合の考慮
            # In the metadata description of the digitised material, both the size of the source material and the size of the individual files may be present. The size of the individual files should be entered in Size (jpcoar:extent).
            # WEKO(開発環境)未対応
            # 'item_1617605131499[0]': {
            # },
        },
        # grdm-file:data-policy-license に包含
        'grdm-file:data-policy-free': None,
        'grdm-file:data-policy-license': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # TBD 無償/有償と引用の仕方等
            'item_1617186499011[]': [
                {
                    'subitem_1522651041219': '{{tooltip_0}} ({{grdm_file_data_policy_cite_ja_value}}) ({{grdm_file_data_policy_free_tooltip_0}})',
                    'subitem_1522650717957': 'ja',
                },
                {
                    'subitem_1522651041219': '{{tooltip_1}} ({{grdm_file_data_policy_cite_en_value}}) ({{grdm_file_data_policy_free_tooltip_1}})',
                    'subitem_1522650717957': 'en',
                },
            ],
        },
        # grdm-file:data-policy-license に包含
        'grdm-file:data-policy-cite-ja': None,
        'grdm-file:data-policy-cite-en': None,
        'grdm-file:access-rights': {
            # TBD check
            '@type': 'string',
            '@createIf': '{{value}}',
            # Access Rights https://schema.irdb.nii.ac.jp/en/schema/2.0/5
            'item_1617186476635': {
                'subitem_1522299639480': '{{value}}'
            },
        },
        'grdm-file:available-date': {
            # TBD check
            '@type': 'string',
            '@createIf': '{{value}}',
            # Date https://schema.irdb.nii.ac.jp/en/schema/2.0/12
            'item_1617186660861[]': {
                'subitem_1522300695726': 'Available',
                'subitem_1522300722591': '{{value}}',
            },
        },
        # JPCOAR 1.0.2にはCatalogなし TBD
        'grdm-file:repo-information-ja': None,
        'grdm-file:repo-information-en': None,
        'grdm-file:repo-url-doi-link': {
            # TBD check
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617186783814[]': {
                'subitem_identifier_uri': '{{value}}',
                # TBD GakuNin RDMの段階でDOIが指定されることはない(だろう)...
                'subitem_identifier_type': 'URI',
            },
        },
        # TBD JSON arrayのマッピング
        'grdm-file:creators': {
            # TBD check
            # @type: jsonarrayを指定すると、メタデータ値をJSON文字列として評価する
            # arrayの要素ごとにマッピングが行われ、その値は value.要素名 で参照することができる
            '@type': 'jsonarray',
            'item_1617186419668[]': {
                'nameIdentifiers[]': {
                    '@createIf': '{{object_number}}',
                    'nameIdentifierURI': '{{object_number}}',
                    'nameIdentifierScheme': 'e-Rad_Researcher',
                },
                'creatorNames[]': [
                    {
                        '@createIf': '{{object_name_ja}}',
                        'creatorName': '{{object_name_ja}}',
                        'creatorNameLang': 'ja',
                    },
                    {
                        '@createIf': '{{object_name_en}}',
                        'creatorName': '{{object_name_en}}',
                        'creatorNameLang': 'en',
                    },
                ],
            },
        },
        'grdm-file:hosting-inst-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            # Contributor Name https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.2
            'item_1617349709064[HOSTING_INSTITUTION]': {
                'contributorType': 'HostingInstitution',
                # TODO nameType?
                'contributorNames[]': {
                    'contributorName': '{{value}}',
                    'lang': 'ja',
                },
            },
        },
        'grdm-file:hosting-inst-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[HOSTING_INSTITUTION]': {
                'contributorType': 'HostingInstitution',
                # Contributor Name https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.2
                # TODO nameType?
                'contributorNames[]': {
                    'contributorName': '{{value}}',
                    'lang': 'en',
                },
            },
        },
        'grdm-file:hosting-inst-id': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[HOSTING_INSTITUTION]': {
                'contributorType': 'HostingInstitution',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                'nameIdentifiers[]': {
                    'nameIdentifierURI': '{{value}}',
                    'nameIdentifierScheme': 'ROR',
                },
            },
        },
        'grdm-file:data-man-number': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[DATA_MANAGER]': {
                'contributorType': 'DataManager',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                'nameIdentifiers[]': {
                    'nameIdentifierURI': '{{value}}',
                    'nameIdentifierScheme': 'e-Rad_Researcher',
                },
            },
        },
        'grdm-file:data-man-name-ja': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[DATA_MANAGER]': {
                'contributorType': 'DataManager',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                'contributorNames[]': {
                    'contributorName': '{{value}}',
                    'lang': 'ja',
                },
            },
        },
        'grdm-file:data-man-name-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[DATA_MANAGER]': {
                'contributorType': 'DataManager',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                'contributorNames[]': {
                    'contributorName': '{{value}}',
                    'lang': 'en',
                },
            },
        },
        # 空白で区切ることで複数のキーに対する共通ルールを定義できる
        'grdm-file:data-man-org-ja grdm-file:data-man-address-ja grdm-file:data-man-tel grdm-file:data-man-email': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[CONTACT_PERSON]': {
                'contributorType': 'ContactPerson',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                # TODO nameType?
                'contributorNames[CONTACT_PERSON_JA]': {
                    'contributorName': '{{grdm_file_data_man_org_ja_value}} {{grdm_file_data_man_address_ja_value}} {{grdm_file_data_man_tel_value}} {{grdm_file_data_man_email_value}}',
                    'lang': 'ja',
                },
            },
        },
        'grdm-file:data-man-org-en grdm-file:data-man-address-en': {
            '@type': 'string',
            '@createIf': '{{value}}',
            'item_1617349709064[CONTACT_PERSON]': {
                'contributorType': 'ContactPerson',
                # Contributor Name Identifier https://schema.irdb.nii.ac.jp/en/schema/2.0/4-.1
                # TODO nameType?
                'contributorNames[CONTACT_PERSON_EN]': {
                    'contributorName': '{{grdm_file_data_man_org_en_value}} {{grdm_file_data_man_address_en_value}}',
                    'lang': 'en',
                },
            },
        },
        'grdm-file:remarks-ja': None,
        'grdm-file:remarks-en': None,
        'grdm-file:metadata-access-rights': None,
        '_': {
            # 対応するGakuNin RDM metadataがない場合はkeyを '_' とする。
            # 値にはPython Format stringが記述できる。nowdateは今日の日付(YYYY-MM-DD)
            # TBD pubdateは必須だが共通メタデータにないフィールドなので、今日の日付を入れる
            'pubdate': '{{nowdate}}',
        },
    },
}
