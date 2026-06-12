# RDM Metadata Addon

## Feature

The RDM Metadata Addon provides a way to edit metadata for projects or files. Users can enable the addon for their project and edit metadata for the project or files.

The detailed features of the RDM Metadata Addon are as follows:

- Edit metadata for projects or files
- View metadata for projects or files
- Export metadata for projects to various formats/destinations
- Export and import projects in RO-Crate format
- Import datasets from external sources

## Enabling the feature

### Export and import projects in RO-Crate format

To enable the feature, you should add the following settings to the configuration file `addons/metadata/settings/local.py`:

```python
USE_EXPORTING = True
```

The "Export" tab is displayed in a project dashboard if `USE_EXPORTING` is true and users can export the project in RO-Crate format.

### Import datasets from external sources

To enable the feature, you should add the following settings to the configuration file `addons/metadata/settings/local.py`:

```python
USE_DATASET_IMPORTING = True
```

The "Import Dataset" button is displayed in a toolbar of a file browser if `USE_DATASET_IMPORTING` is true and users can import datasets from external sources.

## Schema UI Hints (`ui` property)

Metadata schemas (e.g. `e-rad-metadata-1.json`) define both data structure and form rendering. To keep rendering concerns separate from data structure, each question may carry an optional `ui` property — a single JSON object that holds all UI-specific hints.

### Design rationale

Schema properties flow through two distinct paths:

1. **File metadata path** — The schema JSON is stored in `RegistrationSchema.schema` (a JSONField) and served as-is to the browser. The frontend JS (`metadata-fields.js`) reads `question.ui.*` directly. Any new key added to `ui` is automatically available without backend changes.

2. **Project metadata path** — The migration `map_schemas_to_schemablocks` decomposes each question into `RegistrationSchemaBlock` rows. Each column on that model requires a DB migration, a serializer update, and a corresponding Ember model attribute. Adding a single column touches Python models, migrations, API serializers, and Ember types.

By consolidating all UI hints into a single `ui` JSONField column on `RegistrationSchemaBlock`, the project metadata path gains the same extensibility as the file metadata path: new hints can be added to the `ui` object without further migrations or model changes.

### Structure

Simple ja/en pair:

```json
{ "qid": "grdm-file:title-ja",
  "ui": {
    "group": { "id": "title", "title": "データの名称|Title", "tags": ["共通|Common", "リポジトリ|Repository"],
               "help": "...", "info": "管理対象データの特徴を示す名称を入力。|..." },
    "sub_label": "（日本語）|(Japanese)",
    "item": { "placeholder": "研究データ管理に関する意識調査" }
  } }

{ "qid": "grdm-file:title-en",
  "ui": { "group": "title", "sub_label": "（English）|(English)" } }
```

Nested group (ja/en pair inside a category):

```json
{ "qid": "grdm-file:data-policy-free",
  "ui": { "group": { "id": "data-policy", "title": "管理対象データの利活用・提供方針|...", "bar": true,
                      "tags": ["共通|Common"], "info": "ライセンス情報を記載。|..." } } }

{ "qid": "grdm-file:data-policy-license",
  "ui": { "group": "data-policy" } }

{ "qid": "grdm-file:data-policy-cite-ja",
  "ui": {
    "group": { "id": "data-policy-cite", "parent": "data-policy", "title": "引用方法等|..." },
    "sub_label": "（日本語）|(Japanese)"
  } }

{ "qid": "grdm-file:data-policy-cite-en",
  "ui": { "group": "data-policy-cite", "sub_label": "（English）|(English)" } }
```

The `ui` object has three scopes:

**Page scope** (`page.ui`) — page-level decoration:

- **`header`** — Introductory HTML text displayed above all questions on the page (e.g. format notes, tag legend).

**Group scope** (`ui.group`) — section heading and grouping:

- **`id`** — Group identifier. The first question in a group carries the full definition (object); subsequent questions reference the group by `id` string only (e.g. `"group": "title"`).
- **`parent`** — Parent group reference. A string ID when the parent is already defined by an earlier question. An object (`{ "id": "...", "title": "...", ... }`) to simultaneously define the parent group — useful when no earlier question belongs directly to the parent.
- **`title`** — Section heading text.
- **`help`** — Help text (supports HTML) displayed under the section heading.
- **`bar`** — If `true`, draw a continuous vertical bar on the left side of group members (for semantic category groups).
- **`tags`** — Badge labels for the section (e.g. `["共通|Common"]`, `["共通|Common", "リポジトリ|Repository"]`). Pipe-delimited for localization.
- **`info`** — Detailed explanation shown in a popover when the ⓘ mark next to the group heading is clicked.

**Item scope** (`ui.item`) — individual input field:

- **`placeholder`** — Placeholder text for the input field.
- **`width`** — Abstract width category (e.g. `"narrow"`, `"half"`).
- **`widget`** — Override the default widget (e.g. `"radio"` instead of pulldown for `singleselect`).
- **`enabled_if`** — Conditional disabled display. An object with a `disabled` key whose value is either `true` (unconditionally disabled) or a condition object (e.g. `{ "disabled": { "grdm-file:file-type": "dataset" } }`). When the question's `enabled_if` is false and the `disabled` condition is met, the field is shown greyed out instead of hidden.
- **`info`** — Detailed explanation shown in a popover when the ⓘ mark next to the field label is clicked. For grouped fields, prefer `ui.group.info` over `ui.item.info`.
- **`tags`** — Badge labels for standalone fields (fields not belonging to a group). Pipe-delimited for localization.

**Top-level** (`ui.*`):

- **`sub_label`** — Label within a group (e.g. "（日本語）|(Japanese)" / "（English）|(English)" for ja/en pairs).

This list is not exhaustive; new keys can be added as needed without schema migration.

## Suggestion Policies (ERAD/KAKEN)

This addon provides researcher/project suggestions sourced from ERAD and KAKEN. Ordering and deduplication follow simple, explicit policies so results are predictable and easy to reason about.

### Sorting

- Owner: current user first, then other contributors in `node.contributors` order.
- Year: within each owner, sort by fiscal year (`nendo`) descending.
- Key priority: then apply `key_list` priority (place `contributor:*` earlier if you want it prioritized).
- Researcher/Project ordering flow (e.g. for KAKEN suggestions):
  1. Seed with the current user's e-Rad researcher number, query Elasticsearch for matching projects, sort the projects by fiscal year (descending), and enumerate collaborators (`work:project.member`) exactly as stored. For collaborators with an e-Rad number but no English name, fetch the English name from Elasticsearch keyed by that number.
  2. For each remaining project member, follow their contributor order, query Elasticsearch for their projects, and reuse the collaborator enumeration from step 1. Ensure the project member themselves appears immediately after the current user in the combined results.
  3. Deduplicate the consolidated list. A researcher entry is considered a duplicate when the e-Rad number, Japanese/English names, and Japanese/English affiliation names all match; keep the first occurrence. A project entry is considered a duplicate if the project number matches; keep the first occurrence.

### Deduplication

Unified approach for all modes: first apply the sorting above (owner → year desc → key priority), then keep the first occurrence per identity.

- person identity: [ERAD researcher number (`erad` or `kenkyusha_no`), normalized name (MSFullName), normalized institution name ja (`kenkyukikan_mei_ja`)]
- project identity: `kadai_id` (or if absent, `japan_grant_number`)

### Policy Selection (by full key)

Policy is inferred by the full key `<prefix>:<field>` with explicit mappings to avoid ambiguities:

- person keys:
  - `contributor:erad`, `contributor:name`, `contributor:affiliated-institution-name`
  - `erad:kenkyusha_no`, `erad:kenkyusha_shimei`
  - `kaken:erad`, `kaken:kenkyusha_shimei` (and `_ja`, `_en` variants)
- project keys:
  - ERAD: `erad:kadai_id`, `erad:japan_grant_number`, `erad:nendo`, `erad:kadai_mei`, `erad:program_name_*`, `erad:haibunkikan_*`, `erad:bunya_*`
  - KAKEN: `kaken:kadai_id`, `kaken:japan_grant_number`, `kaken:nendo`, `kaken:kadai_mei`, `kaken:program_name_*`, `kaken:haibunkikan_*`, `kaken:bunya_*`

There is no prefix‑based fallback for single‑key requests; classification is always determined by the field suffix.

Mixed requests (person + project keys together):

- No cross‑key merge/dedup is applied. Suggestions are returned in the concatenated order (i.e., `key_list` order, with each key’s internal order preserved).

### Endpoint Behavior

- `suggestion_erad` (keys starting with `erad:`): applies person mode.
- `suggest_kaken` (keys starting with `kaken:`): applies project mode.
- `metadata_file_metadata_suggestions`:
  - If all keys are person or all project: sort (owner → year desc → key priority) and keep first occurrence per identity.
  - If person and project keys are mixed: no cross‑key merge/dedup; suggestions are concatenated in request `key_list` order (each key’s internal order preserved).
- `metadata_get_erad_candidates`: orders by owner → year desc; deduplicates by project identity keeping the first appearance.

Notes:

- Sorting is a stable sort; when tie‑breaking cannot decide, original order is preserved.
- Identifiers used for deduplication are chosen conservatively to avoid false merges (e.g., prefer explicit IDs over normalized names).
