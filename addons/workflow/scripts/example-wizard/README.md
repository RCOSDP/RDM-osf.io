# Example: RDM Form Extensions

A minimal workflow demonstrating all RDM special placeholders and wizard features.

## Process flow

```
startEvent           → wizardTask          → buildSummary (script) → resultTask          → endEvent
(example-start-form)   (example-wizard-form)                         (example-result-form)
```

## What this covers

### Start form (`example-start-form`)

| Feature | Field ID |
|---------|----------|
| `_PROJECT_METADATA(schema)` | `project_metadata` |
| `_PROJECT_METADATA(schema, MULTISELECT)` | `project_metadata_multi` |
| `_FILE_METADATA(schema)` | `file_metadata` |
| `_FILE_METADATA(schema, filter=<expr>)` | `file_metadata_non_manuscript` |
| `_FILE_SELECTOR()` | `selected_files` |

### Wizard form (`example-wizard-form`)

| Feature | Field ID | Page |
|---------|----------|------|
| `_EXPORT_TARGET()` | `export_target` | Export Settings |
| `_FILE_UPLOADER(path, ext)` | `uploaded_files` | File Upload |
| `_FILE_UPLOADER(path)` readOnly | `conf_uploaded_files` | Confirmation |
| `_ARRAY_INPUT(fields)` | `members` | Details |
| Visibility expression | `include_details` | Details (conditionally shown) |
| Alias (read-only reference) | `conf_note` → `note` | Confirmation |
| Alias (read-only reference) | `conf_export_target` → `export_target` | Confirmation |
| Field hints (width) | `members.name`, `members.role` | Details |

### Wizard structure

```
Export Settings          _EXPORT_TARGET, boolean toggle
File Upload              _FILE_UPLOADER (with .pdf,.docx filter)
Details                  _ARRAY_INPUT, text  (visible: include_details)
Confirmation             alias fields (readOnly), _FILE_UPLOADER (readOnly)
```

## How to deploy

1. Upload `example-wizard-v0.zip` to Flowable via the RDM workflow template registration
2. Start the process from the RDM workflow dashboard
3. The start form shows metadata/file selection placeholders
4. After starting, the wizard task shows export/array/alias features
5. After completing the wizard, a result task displays all submitted data as JSON

Or upload individual files:
- `bpmn-models/rdm-main-example-wizard.bpmn` as a process definition
- `form-models/example-start-form.json`, `form-models/example-wizard-form.json`, and `form-models/example-result-form.json` as form definitions

To regenerate the zip: `bash create_zip.sh`

## Specification

See `addons/workflow/RDM-FORM.md` for the full specification.
