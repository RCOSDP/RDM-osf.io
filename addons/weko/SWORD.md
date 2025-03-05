# WEKO SWORD プロトコル デポジット仕様書

## 概要

WEKOアドオンは、OSFからWEKOリポジトリへのメタデータとファイルのデポジットのためにSWORD（Simple Web-service Offering Repository Deposit）プロトコルを実装しています。この仕様では、CSVとRO-Crateの2つのメタデータ形式をサポートし、BagIt標準を使用してパッケージ化されます。

## SWORD プロトコル実装

### サービスエンドポイント
- **エンドポイント**: `sword/service-document`
- **メソッド**: POST
- **認証**: OAuth2 Bearerトークンまたは基本認証

### パッケージ形式
- **SimpleZip**: `http://purl.org/net/sword/3.0/package/SimpleZip`
- **SWORDBagIt**: `http://purl.org/net/sword/3.0/package/SWORDBagIt`

## メタデータマッピング管理オブジェクト

### 1. 基本構造

マッピング設定ファイルは以下の3つのセクションで構成されます：

```json
{
  "@metadata": {
    "itemtype": {
      "name": "デフォルトアイテムタイプ（フル）(30002)",
      "schema": "https://localhost:8443/items/jsonschema/30002"
    },
    "filename": "index.csv"
  },
  "@files": { ... },
  "@projects": { ... }
}
```

### 2. @metadataセクション

WEKOアイテムタイプとスキーマの定義を管理します。

#### 構造
```json
"@metadata": {
  "itemtype": {
    "name": "デフォルトアイテムタイプ（フル）(30002)",
    "schema": "https://localhost:8443/items/jsonschema/30002"
  },
  "filename": "index.csv"  // CSV形式の場合のみ
}
```

#### 技術詳細
- **itemtype.name**: WEKOのアイテムタイプ名称
- **itemtype.schema**: JSONスキーマのURL
- **filename**: CSVエクスポート時のファイル名（オプション）

### 3. @filesセクション

ファイル固有のメタデータマッピングを管理します。

#### 主要機能
- **動的アクセス権限マッピング**: `object_grdm_file_access_rights`に基づく
- **条件付き日付埋め込み**: エンバーゴ付きコンテンツ用
- **テンプレート変数**: `{{object_filename}}`、`{{object_format}}`
- **アクセスロールマッピング**: `open_access`、`open_login`、`open_date`、`open_no`

#### 例：アクセス権限マッピング
```json
"metadata.item_30002_file_access_right7[]": {
  "@type": "string",
  "@value": "{% if object_grdm_file_access_rights == \"open access\" %}open_access{% elif object_grdm_file_access_rights == \"restricted access\" %}open_login{% elif object_grdm_file_access_rights == \"embargoed access\" %}open_date{% else %}open_no{% endif %}"
}
```

### 4. @projectsセクション

OSFプロジェクトの資金情報をWEKOの資金参照フィールドにマッピングします。

#### 主要マッピング
- **e-Rad資金機関識別子と名称**（二言語対応）
- **Japan Grant Numbers (JGN)**
- **資金ストリーム情報**
- **助成タイトルと番号**
- **プロジェクト名**（日本語・英語）

#### 例：資金機関マッピング
```json
"metadata.item_30002_fundref_funder_identifier12[FUNDER_IDENTIFIER]": {
  "@type": "string",
  "@value": "{{japan_grant_number_funder_identifier_value}}"
},
"metadata.item_30002_fundref_funder_name_ja13[FUNDER_NAME_JA]": {
  "@type": "string",
  "@value": "{{japan_grant_number_funder_name_ja_value}}"
}
```

### 5. フィールドマッピングメカニズム

#### テンプレートシステム
- **Jinja2テンプレート**: カスタムフィルター付き
- **変数補間**: `{{value}}`、`{{grdm_file_data_research_field_value}}`
- **条件レンダリング**: `{% if condition %}...{% endif %}`
- **カスタムフィルター**: `has_license_def_for_jpcoar2`、`to_normalized_ja_license_name_for_jpcoar2`

#### 条件付き作成
```json
"@createIf": "{% if object_grdm_file_access_rights == \"embargoed access\" %}{{object_grdm_file_available_date}}{% endif %}"
```

#### 配列インデックスシステム
- **動的配列インデックス**: `[RESEARCH_FIELD_JA]`、`[FUNDER_NAME_EN]`
- **番号付きインデックス**: `[0]`、`[1]`
- **名前付きインデックス**: `[CREATOR_NAME]`、`[DESCRIPTION_JA]`

### 6. 利用可能なマッピング設定

#### 1. E-Rad標準マッピング (`e-rad-metadata-mappings.json`)
```json
{
  "@metadata": {
    "itemtype": {
      "name": "デフォルトアイテムタイプ（フル）(30002)",
      "schema": "https://localhost:8443/items/jsonschema/30002"
    }
  }
}
```

#### 2. E-Rad CSVマッピング (`e-rad-metadata-mappings-csv.json`)
```json
{
  "@metadata": {
    "filename": "index.csv",
    "itemtype": {
      "name": "デフォルトアイテムタイプ（フル）(30002)",
      "schema": "https://localhost:8443/items/jsonschema/30002"
    }
  }
}
```

#### 3. E-Rad RO-Crateマッピング (`e-rad-metadata-mappings-ro-crate.json`)
```json
{
  "@metadata": {
    "filename": "ro-crate-metadata.json",
    "itemtype": {
      "name": "RO-Crate Metadata",
      "schema": "https://w3id.org/ro/crate/1.1"
    }
  }
}
```

#### 4. MIBYODB RO-Crateマッピング (`ms2-mibyodb-metadata-mappings-ro-crate.json`)
```json
{
  "@metadata": {
    "filename": "ro-crate-metadata.json",
    "itemtype": {
      "name": "Medical/Biomedical RO-Crate",
      "schema": "https://w3id.org/ro/crate/1.1"
    }
  }
}
```

### 7. データ型システム

#### 基本データ型
```json
"@type": "string"    // 文字列
"@type": "array"     // 配列
"@type": "object"    // オブジェクト
```

#### 複合構造
```json
"metadata.item_30002_creator2[]": {
  "@type": "object",
  "creator_name": {
    "@type": "string",
    "@value": "{{creator_name_value}}"
  },
  "creator_name_ja": {
    "@type": "string", 
    "@value": "{{creator_name_ja_value}}"
  }
}
```

### 8. 変数解決システム

#### 基本変数
- `{{value}}`: 基本値
- `{{nowdate}}`: 現在日時
- `{{object_filename}}`: ファイル名
- `{{object_format}}`: ファイル形式

#### スキーマ固有変数
- `{{grdm_file_*_value}}`: GRDMファイルメタデータ
- `{{japan_grant_number_value}}`: 科研費番号
- `{{research_field_*_value}}`: 研究分野情報

### 9. WEKOスキーマ統合

#### フィールド命名規則
```
metadata.item_{type_id}_{field_name}{field_id}[]
```

#### 例
```json
"metadata.item_30002_title0[]": "タイトル",
"metadata.item_30002_creator2[]": "作成者",
"metadata.item_30002_description3[]": "説明"
```

#### 特殊マッピングキー
- `_`: 静的メタデータ（公開日など）
- `@agent`: ユーザー固有情報（フィードバックメール）
- `null`: 未使用フィールド

### 10. 多言語サポート

#### 言語コード管理
- **日本語**: `ja`
- **英語**: `en`
- **言語固有フィールド作成**
- **条件付き言語選択ロジック**

#### ライセンス管理
- **定義済みライセンス**: `utils.py`内
- **Creative Commons、MIT、Apache、GPL等の標準ライセンス**
- **二言語ライセンス名とURL**
- **カスタムライセンス処理**

この高度なマッピングシステムにより、OSFの研究データ管理システムとWEKOのリポジトリ構造間での洗練された変換レイヤーが提供され、適切なメタデータ保存と発見可能性が確保されます。