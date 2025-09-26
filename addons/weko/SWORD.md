# WEKO SWORD Protocol Specification

## Overview

The WEKO addon implements the SWORD (Simple Web-service Offering Repository Deposit) protocol for depositing metadata and files from OSF to WEKO repositories. It supports two metadata formats (CSV and RO-Crate) packaged using the BagIt standard.

## SWORD Protocol Implementation

### Service Endpoint
- **Endpoint**: `sword/service-document`
- **Method**: POST
- **Authentication**: OAuth2 Bearer token or Basic authentication

### Package Formats
- **SimpleZip**: `http://purl.org/net/sword/3.0/package/SimpleZip`
- **SWORDBagIt**: `http://purl.org/net/sword/3.0/package/SWORDBagIt`

## Metadata Format Support

### CSV Format
- **Mapping File**: `addons/weko/mappings/e-rad-metadata-mappings-csv.json`
- **Output**: `index.csv` (WEKO item type 30002 format)
- Maps OSF metadata to WEKO's tabular format

### RO-Crate Format
- **Mapping File**: `addons/weko/mappings/e-rad-metadata-mappings-ro-crate.json`
- **Output**: `ro-crate-metadata.json` (JSON-LD, JPCOAR 2.0 compliant)
- Supports rich semantic metadata with conditional field mapping

## RO-Crate: Manuscript/Dataset Conditional Mapping

The RO-Crate mapping uses `grdm-file:file-type` to output different metadata fields for manuscripts vs. datasets.

### Conditional Syntax
```json
"@createIf": "{% if grdm_file_file_type_value == \"manuscript\" %}{{value}}{% endif %}"  // Manuscript-only
"@createIf": "{% if grdm_file_file_type_value != \"manuscript\" %}{{value}}{% endif %}" // Dataset-only
```

### Manuscript-Only Fields (JPCOAR 2.0)

When `grdm-file:file-type` = `"manuscript"`:

| Source Field | JPCOAR Output | Description |
|--------------|---------------|-------------|
| `grdm-file:doi` | `jpcoar:relation[]` (relationType: `isVersionOf`) | Published article DOI |
| `grdm-file:manuscript-type` | `dc:type` | Manuscript type |
| `grdm-file:authors` | `jpcoar:creator[]` (with familyName/givenName) | Author details (split name fields) |
| `grdm-file:journal-name-ja/en` | `jpcoar:sourceTitle[]` | Journal name (bilingual) |
| `grdm-file:date-published` | `datacite:date[ISSUED]` | Publication date |
| `grdm-file:volume` | `jpcoar:volume` (PropertyValue) | Volume number |
| `grdm-file:issue` | `jpcoar:issue` (PropertyValue) | Issue number |
| `grdm-file:page-start/end` | `jpcoar:pageStart/pageEnd` (PropertyValue) | Page range |
| `grdm-file:version`, `grdm-file:reviewed` | `oaire:version` (PropertyValue) | Manuscript version (AM/VoR/AO) with COAR URI and peer review status |
| `grdm-file:dataset-link` | `jpcoar:relation[]` (relationType: `isSupplementedBy`) | Related dataset DOI |

**Note**: Volume, issue, and page fields use PropertyValue format to comply with WEKO's item schema validation.

### Dataset-Only Fields

When `grdm-file:file-type` ≠ `"manuscript"`:

- `grdm-file:data-number`, `data-description-ja/en`, `data-research-field`, `data-type`
- `grdm-file:access-rights`, `data-policy-*`, `available-date`
- `grdm-file:creators` (simple format), `hosting-inst-*`, `data-man-*`
- `grdm-file:publication-link` (`jpcoar:relation[]`, relationType: `isSupplementTo`)

### Common Fields

Both manuscript and dataset include:
- `grdm-file:title-ja/en` → `dc:title`
- Project funding information → `jpcoar:fundingReference`
- User feedback → `wk:feedbackMail`

## RO-Crate: Item Relationships (wk:itemLinks)

When multiple items with different `grdm-file:file-type` values are present, the system automatically generates bidirectional relationship links between manuscripts and datasets.

### Link Generation

**Manuscripts** (`file-type: manuscript`):
- Creates `wk:itemLinks` with `isSupplementedBy` relation to each dataset item
- Links reference internal RO-Crate item IDs (e.g., `#dataset-2`)

**Datasets** (`file-type: dataset` or other):
- Creates `wk:itemLinks` with `isSupplementTo` relation to each manuscript item
- Links reference internal RO-Crate item IDs (e.g., `#dataset-1`)

### Structure

Each link is represented as a PropertyValue entity:
```json
{
  "@id": "_:itemLink1",
  "@type": "PropertyValue",
  "value": "isSupplementedBy",
  "identifier": "#dataset-2"
}
```

Items reference these links via `wk:itemLinks`:
```json
"wk:itemLinks": [
  {"@id": "_:itemLink1"}
]
```

**Note**: These links represent internal RO-Crate relationships, distinct from external DOI-based `jpcoar:relation` references. Link generation only occurs when multiple items are split into separate entities (`wk:isSplited: true`).

## Updating Mappings

**Important**: After modifying mapping files (`addons/weko/mappings/*.json`), you must register them to the database:

```bash
docker compose run --rm web \
  python3 -m scripts.register_metadata_mapping \
  "公的資金による研究データのメタデータ登録" \
  addons/weko/mappings/e-rad-metadata-mappings-ro-crate.json
```

Without this step, updates will not be reflected in generated payloads. After registration, generate a test payload using the script below to verify the output.

## Testing Utilities

### Payload Generation Script

Test metadata mappings locally using `addons/weko/scripts/export_sword_payload.py`:

```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    /code/path/to/config.json \
    /code/path/to/output/payload.zip
```

**Options**:
- `--format {zip|ro-crate|csv}`: Output format (default: `zip`)
- `--skip-flatten`: Keep RO-Crate JSON nested (debug mode, use with `--format=ro-crate`)
- `--skip-csv`: Skip CSV generation (recommended for manuscript testing to avoid field conflicts)

**Manuscript Testing Example**:
```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    addons/weko/scripts/example-manuscript-metadata.json \
    /code/manuscript-payload.zip \
    --format zip \
    --skip-csv
```

### Database Export Mode

Export SWORD payload directly from the database using the `--project` option:

```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    /code/output.zip \
    --project <node_id> \
    --file-metadata <provider>/<path> \
    --file-metadata <provider>/<path> \
    --project-metadata draft-registration/<draft_id> \
    --format zip \
    --skip-csv
```

**Required Parameters**:
- `--project`: OSF project/node ID
- `--file-metadata`: File path(s) in `<provider>/<path>` format (can be specified multiple times)
- `--project-metadata`: Draft registration ID in `draft-registration/<id>` or `registration/<id>` format

**Example**:
```bash
docker compose run --rm web python3 -m addons.weko.scripts.export_sword_payload \
    /code/test-export.zip \
    --project rekxj \
    --file-metadata osfstorage/dataset.zip \
    --file-metadata osfstorage/journal_paper.pdf \
    --project-metadata draft-registration/68f16b2eb9d46d002db720d8 \
    --format zip \
    --skip-csv
```

**Important Notes**:
- Files are downloaded from WaterButler before payload generation
- Use `--skip-csv` when exporting manuscripts + datasets together (CSV format cannot merge different file types)
- File metadata is loaded from the database using the specified file paths

### Configuration Format (JSON Mode)

See sample files for structure details:
- `addons/weko/scripts/example-metadata.json` (dataset template)
- `addons/weko/scripts/example-manuscript-metadata.json` (manuscript + dataset template)

Configuration requires:
- `user`: username, fullname, institution
- `schema_name`: "公的資金による研究データのメタデータ登録"
- `node_id`, `index`, `files`, `file_metadatas`, `project_metadatas`

The `file_metadatas[].items[].schema` field must match the latest `RegistrationSchema` `_id` for the specified `schema_name`.

## Sample Files

- **`example-metadata.json`**: Dataset template
- **`example-manuscript-metadata.json`**: Manuscript template (1 manuscript + 2 datasets)
- **`example-data.txt`, `sample-manuscript.pdf`, `sample-supporting-data*.csv`**: Test data files

Generated artifacts use the same transformation process as actual SWORD deposits.
