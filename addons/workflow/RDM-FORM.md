# RDM Form Extensions

Extensions to Flowable OSS `SimpleFormModel` for RDM workflow forms.
These are **RDM-specific** and independent of Flowable Enterprise features.

## Special Placeholders

`multi-line-text` fields with a placeholder matching `_KEYWORD(...)` are
rendered as custom UI components instead of a plain textarea.

### `_PROJECT_METADATA(schema_name[, MULTISELECT][, filter=<expr>])`

Renders a card-based selector for Draft Registrations / Registrations
created with the specified Registration Schema.

```json
{
  "fieldType": "FormField",
  "id": "metadata_record",
  "name": "Metadata",
  "type": "multi-line-text",
  "placeholder": "_PROJECT_METADATA(公的資金による研究データのメタデータ登録)",
  "required": true
}
```

Add `MULTISELECT` to allow selecting multiple records:

```json
"placeholder": "_PROJECT_METADATA(公的資金による研究データのメタデータ登録, MULTISELECT)"
```

Add `filter=<expr>` to narrow candidates by metadata values. See
[Filter expression](#filter-expression) below.

**Value**: JSON object (single) or JSON array (multi-select) containing the
selected record's GUID and metadata payload.

### `_FILE_METADATA(schema_name[, MULTISELECT][, filter=<expr>])`

Same as `_PROJECT_METADATA` but for file-level metadata records.

```json
"placeholder": "_FILE_METADATA(some-file-metadata-schema)"
```

### Filter expression

Restricts candidates to records whose metadata values satisfy the expression.

```
<expr>         = <clause> ( " and " <clause> )*
<clause>       = <key> <op> <quoted_value>
<op>           = "==" | "!="
<quoted_value> = '"' [^"]* '"'
```

- Comparison operators: `==` and `!=`. Any other token (`=`, `!=` without `=`,
  `<>`, `||`, `&&`, `or`, `!`) is a syntax error.
- Clauses are joined by the literal keyword `and` (surrounding spaces).
  Multiple `filter=` options in the same placeholder are a syntax error —
  write one `filter=` with `and`.
- Values **must** be double-quoted. A bare value like `filter=k==dataset`
  is a syntax error. Quoting forward-compatibly reserves room for future
  typed values (numbers, booleans) while keeping string boundaries explicit.
- A single `filter=` is allowed. Inside the placeholder argument list, commas
  inside quoted values are preserved (not treated as argument separators).

#### Matching semantics

For each clause, the selector reads `data[key].value` from a candidate
record's metadata and compares against the quoted value:

- `==`: strict equality. Unset/empty values (`undefined`, `null`, `""`) never
  equal a non-empty value, so they do not match.
- `!=`: strict inequality. Unset/empty values are treated as "not that value"
  and therefore match. This is useful when a field has a default value that
  is not always written back (e.g. `grdm-file:file-type` defaults to
  `dataset`; `filter=grdm-file:file-type!="manuscript"` covers explicit
  `dataset` **and** unset rows).

#### Example

```json
"placeholder": "_FILE_METADATA(公的資金による研究データのメタデータ登録, filter=grdm-file:file-type!=\"manuscript\")"
```

Combined with `MULTISELECT`:

```json
"placeholder": "_FILE_METADATA(公的資金による研究データのメタデータ登録, MULTISELECT, filter=grdm-file:file-type==\"dataset\" and status==\"ready\")"
```

### `_FILE_SELECTOR()`

Renders a file browser for selecting files from the project's storage providers.

```json
"placeholder": "_FILE_SELECTOR()"
```

**Value**:
```json
{
  "provider": "osfstorage",
  "files": [
    { "materialized": "/path/to/file.csv", "enable": true }
  ]
}
```

### `_FILE_UPLOADER(path[, extensions])`

Renders a file browser with upload capability targeting a specific folder in
osfstorage. The folder path is created recursively if it does not exist.

```json
{
  "fieldType": "FormField",
  "id": "manuscript_files",
  "name": "Manuscript Files",
  "type": "multi-line-text",
  "placeholder": "_FILE_UPLOADER(IQB-RIMS Temporary files/最終原稿・組図, .pdf,.docx)"
}
```

**Parameters**:
- `path` (required): osfstorage-relative folder path. `/`-separated segments are
  created from root if missing.
- `extensions` (optional): Comma-separated list of accepted file extensions
  (e.g. `.pdf,.xlsx`). Omit to allow all file types. Files with non-matching
  extensions trigger a warning and block form submission.

**Value** (`_FILE_SELECTOR` compatible):
```json
{
  "provider": "osfstorage",
  "files": [
    { "path": "/5f3e2a1b.../", "materialized": "/IQB-RIMS Temporary files/最終原稿・組図/paper.pdf", "enable": true }
  ]
}
```

All files in the target folder are included with `enable: true`.

**Multiple uploaders per form**: Supported. Each field gets a unique drop zone
based on the field ID.

**Read-only**: When `readOnly: true`, displays the file list without upload/delete controls.

### `_EXPORT_TARGET()`

Renders a dropdown of available storage providers for export destination.

```json
"placeholder": "_EXPORT_TARGET()"
```

**Value**: Provider name string (e.g. `"weko"`).

### `_ARRAY_INPUT(<fields JSON>)`

Renders a repeatable array input UI. `<fields JSON>` is a JSON array
using the same format as Flowable's `editorJson.fields`.

```json
"placeholder": "_ARRAY_INPUT([{\"fieldType\":\"FormField\",\"id\":\"name\",\"name\":\"Name\",\"type\":\"text\"},{\"fieldType\":\"OptionFormField\",\"id\":\"role\",\"name\":\"Role\",\"type\":\"dropdown\",\"hasEmptyValue\":true,\"options\":[{\"name\":\"PI\"},{\"name\":\"CoPI\"}]}])"
```

UI: each row is a card with the defined fields, plus Add/Remove buttons.

**Value**: JSON array. Each element is an object keyed by sub-field ID:
```json
[
  { "name": "Alice", "role": "PI" },
  { "name": "Bob", "role": "CoPI" }
]
```

Groovy scripts access this as a Jackson `ArrayNode` (not `java.util.List`).
Use `.has()` / `.get(field).asText()` to read values.

## Wizard (`_rdmWizard`)

A single user task can present a multi-page wizard form. The wizard
configuration is stored as an `ExpressionFormField` in the `fields` array:

```json
{
  "fieldType": "ExpressionFormField",
  "id": "_rdmWizard",
  "name": "_rdmWizard",
  "type": "expression",
  "expression": "<JSON string of wizard config>"
}
```

If `_rdmWizard` is absent, the form renders as a flat form (backward compatible).

**Why not a top-level property?** Flowable OSS form-data API only returns
known properties from `editorJson` top level. Custom properties are dropped.
`ExpressionFormField` in `fields` passes through including `expression`.

### Wizard Config Structure

```json
{
  "pages": [ ... ],
  "alias": { ... },
  "fieldHints": { ... },
  "navigation": { "allowBack": true, "allowHeaderNavigation": false },
  "progress": { "style": "sidebar" }
}
```

Field definitions stay flat in the form's `fields` array. Pages reference
field IDs only -- fields are not nested inside pages.

### Pages

```json
{
  "pages": [
    {
      "id": "data-management",
      "title": "Data Management Check",
      "fields": ["field-id-1", "field-id-2"]
    },
    {
      "id": "publication",
      "title": "Publication Check",
      "type": "group",
      "pages": [
        {
          "id": "pub-basic",
          "title": "Basic Check",
          "fields": ["field-id-3"]
        },
        {
          "id": "pub-ethics",
          "title": "Ethics",
          "visible": "!no_changes_from_plan",
          "fields": ["field-id-4"]
        }
      ]
    },
    {
      "id": "confirmation",
      "title": "Confirmation",
      "fields": ["confirmation_field_1"]
    }
  ]
}
```

#### Page Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | Yes | Unique identifier within the form |
| `title` | string | Yes | Displayed in progress sidebar and header |
| `type` | string | No | `"group"` only. Omit for regular input pages |
| `fields` | string[] | Regular pages | Field IDs to display on this page |
| `visible` | string \| boolean | No | Visibility expression. Default: `true` |
| `pages` | Page[] | Groups only | Child pages (groups and regular pages can mix) |

#### Groups

- Groups themselves are not navigable ("Next" skips them)
- Shown as headings in the progress sidebar with children indented
- `visible` on a group controls all children (hidden group = all children hidden)

#### Navigation Order

Depth-first traversal of the page tree, extracting only non-group pages:

```
Tree                              Navigation order
-----                             ----------------
Data Management Check             [0] Data Management Check
Publication Check (group)         [1] Basic Check
  Basic Check                     [2] Ethics (visible condition)
  Ethics                          [3] Confirmation
Confirmation
```

Pages with `visible = false` are skipped.

### Visibility Expressions

String in a page's `visible` property, evaluated client-side (not Flowable UEL).

#### Grammar

```
expression  = or_expr
or_expr     = and_expr ( "||" and_expr )*
and_expr    = not_expr ( "&&" not_expr )*
not_expr    = "!" not_expr | compare
compare     = primary ( ( "==" | "!=" ) primary )?
primary     = "(" expression ")" | "true" | "false" | string_literal | field_ref

string_literal = "'" [^']* "'"
field_ref      = [^&|!=()' \t]+
```

Operator precedence (high to low): `!` > `==` `!=` > `&&` > `||`

#### Resolution

Names resolve in order:
1. Form field ID (`fields[].id`) -- current value
2. Task variable (Flowable process variable)

Field ID takes precedence over a same-named task variable.

#### Truthiness

`false`, `null`, `undefined`, `""` are falsy. Everything else is truthy.

#### Example

Before (BPMN gateway + Groovy):
```groovy
def check = execution.getVariable("no_changes_from_plan")
execution.setVariable("require_ethics", !check)
// sequenceFlow: ${require_ethics == true}
```

After (wizard `visible`):
```json
{ "id": "ethics", "visible": "!no_changes_from_plan", "fields": [...] }
```

No intermediate variables, no Groovy scripts.

### Template Expressions

`ExpressionFormField` supports Jinja2-subset template directives alongside
Flowable UEL `${...}` variables. Templates are evaluated client-side and
produce Markdown text (rendered by `MarkdownToHtml`).

**Processing order**: `${...}` (Flowable UEL) is resolved first, then
`{{ }}` / `{% %}` directives are expanded. Both can coexist in the same
expression string. If no `{{ }}` or `{% %}` directives are present, the
template engine is not invoked (fast path).

#### Syntax

**Value interpolation**:
```
{{ variable }}
{{ item.property }}
{{ item['property-name'] }}
{{ value | default('N/A') }}
```

**Control structures**:
```
{% if condition %}...{% elif condition %}...{% else %}...{% endif %}
{% for item in array %}...{% endfor %}
```

**Whitespace trimming** (critical for Markdown output):
```
{%- tag %}   strip whitespace before
{% tag -%}   strip whitespace after
{{- expr -}} strip both sides
```

Without trimming, `{% for %}` / `{% endfor %}` tags produce blank lines
that break Markdown list formatting.

#### Expression Grammar

```
expression  = or_expr
or_expr     = and_expr ( "or" and_expr )*
and_expr    = not_expr ( "and" not_expr )*
not_expr    = "not" not_expr | compare
compare     = access ( ( "==" | "!=" ) access )?
access      = primary ( "." ident | "[" expression "]" )*
primary     = "(" expression ")" | "true" | "false" | string_literal | ident
```

Keywords use Jinja2 style (`and`, `or`, `not`) rather than C-style
(`&&`, `||`, `!`) used in visibility expressions.

Identifiers may contain hyphens (matching Flowable field IDs). Since
arithmetic operators are not supported, `item.japan-grant-number` is
unambiguous dot-access, not subtraction.

#### Resolution

Template expressions resolve names from the wizard's field context:
1. Task variables (Flowable process variables)
2. Form field values (all pages, overriding task variables)

Same context as page visibility expressions.

#### Truthiness

`false`, `null`, `undefined`, `""`, `0`, and empty arrays `[]` are falsy.

#### Filters

| Filter | Syntax | Description |
|--------|--------|-------------|
| `default` | `{{ val \| default('fallback') }}` | Returns fallback if value is `null`, `undefined`, or `""` |
| `length` | `{{ arr \| length }}` | Array length or string length |

#### Example

Display funding information from three data sources in a unified format:
```
### Funding
{%- for pm in funding_project_metadata %}

**{{ pm.data.japan-grant-number.value | default('') }}**
- Funder: {{ pm.data.funder.value | default('') }}
- Program: {{ pm.data.program-name-ja.value | default('') }}
{%- endfor %}
{%- if japan-grant-number %}

**{{ japan-grant-number }}**
- Funder: {{ funder | default('') }}
- Program: {{ program-name-ja | default('') }}
{%- endif %}
{%- for item in additional-funding %}

**{{ item.japan-grant-number | default('') }}**
- Funder: {{ item.funder | default('') }}
- Program: {{ item.program-name-ja | default('') }}
{%- endfor %}
```

### Alias

Declarative field-value synchronization. Key = alias field ID, value = source field ID.

```json
{
  "alias": {
    "confirmation_field_1": "original_field_1",
    "confirmation_field_2": "original_field_2"
  }
}
```

**Purpose**: Confirmation pages need to show values from other pages as
read-only. Flowable does not allow duplicate field IDs, so alias fields
(e.g. `confirmation_field_1`) reference source fields.

**Behavior**:
- **Read-only alias**: No own value. Always reflects the source field's current value.
  No copy timing issue -- independent of page navigation order.
- **Editable alias**: Uses source value as default. Once edited by user, becomes independent.
- **On submit**: Read-only aliases send the source's current value.
  Editable aliases send the user's edit (or source value if untouched).
  Alias fields are submitted as separate variables (distinct IDs).

**Validation rules** (Python validator):
- Both key and value must exist in `fields`
- Key and value must differ
- No circular references

### Field Hints

Per-field UI hints and input suggestions, defined within the wizard config.

```json
{
  "fieldHints": {
    "japan-grant-number": {
      "ui": { "width": "narrow" },
      "suggestion": [
        {
          "key": "erad:japan_grant_number",
          "template": "<div><span>{{japan_grant_number}}</span><small>{{kadai_mei}}</small></div>",
          "autofill": {
            "funder": "haibunkikan_cd",
            "project-research-field": "bunya_cd"
          }
        }
      ]
    },
    "funder": {
      "ui": { "width": "half", "freetext": true, "optionMap": { "JST": "科学技術振興機構" } }
    }
  }
}
```

#### `ui` Properties

| Property | Type | Description |
|----------|------|-------------|
| `width` | `'narrow'` \| `'half'` \| `'full'` | Display width (25% / 50% / 100%). Default: `full` |
| `freetext` | boolean | Allow free-text input on dropdowns. Default: `false` |
| `optionMap` | `Record<string, string>` | Code-to-display mapping for dropdown autofill (see below) |

#### `visible`

| Property | Type | Description |
|----------|------|-------------|
| `visible` | `string \| boolean` | Visibility expression. Same grammar as page `visible`. Default: `true` |

Field-level visibility control. Hidden fields are excluded from rendering
and validation, but their values are preserved and included in submission
(same semantics as page-level `visible`).

```json
"fieldHints": {
  "confirmation_データ収集": {
    "visible": "hasEvidenceData"
  }
}
```

#### `suggestion` Properties

Uses the same structure as metadata schema `suggestion` definitions.

| Property | Type | Description |
|----------|------|-------------|
| `key` | string | Suggestion API key (e.g. `"erad:japan_grant_number"`) |
| `template` | string | HTML template for candidate display. `{{field}}` placeholders |
| `valueField` | string | API response field to set as the input value |
| `autofill` | `Record<string, string>` | `{ targetFieldId: responseFieldName }` mapping |

#### `optionMap` and Autofill

Flowable dropdown options have only `name` (display text), no code values.
When autofill sets a dropdown value from an API response code (e.g. `"JST"`),
`optionMap` resolves it to the display text (e.g. `"科学技術振興機構"`).

```json
"optionMap": {
  "AMED": "日本医療研究開発機構",
  "JST": "科学技術振興機構",
  "JSPS": "日本学術振興会"
}
```

#### Array Sub-field Hints

For fields inside `_ARRAY_INPUT`, use dot notation: `<arrayFieldId>.<subFieldId>`.
Autofill targets within dot-notation hints use sub-field IDs only (same row).

```json
{
  "fieldHints": {
    "additional-funding.japan-grant-number": {
      "suggestion": [{
        "key": "erad:japan_grant_number",
        "autofill": { "funder": "haibunkikan_cd" }
      }]
    }
  }
}
```

### Navigation

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `allowBack` | boolean | `true` | Show "Back" button |
| `allowHeaderNavigation` | boolean | `false` | Allow direct page jumps from progress sidebar |

### Progress

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `style` | string | `"sidebar"` | `"sidebar"` (side panel) or `"steps"` (step bar) |

Hidden pages (`visible = false`) are excluded from the progress display.

### Draft Persistence

Wizard auto-saves field values and current page to `localStorage`.

**Storage key**: `rdm-wizard:{taskId}`

**Saved data**:
- `formKey` -- integrity check against current form
- `currentPageId` -- page to restore
- `fieldValues` -- `{ [fieldId]: value }`
- `savedAt` -- timestamp for expiry

**Save triggers**: page navigation, field value change (debounced 1s).

**Restore**: on form open, if `formKey` matches and `savedAt` < 7 days.

**Cleanup**: on task complete (delete key), on formKey mismatch or expiry (delete key),
on any wizard form open (GC all `rdm-wizard:*` entries older than 7 days).

**localStorage unavailable**: silently skip. No error, no impact on form behavior.

### Renderer Behavior

- **Next**: validate current page fields, advance to next visible page
- **Back**: go to previous visible page (no validation)
- **Submit** (last page): validate all pages, complete the task
- **Hidden page fields**: values preserved in memory, excluded from validation,
  included in submission (page `visible` is UI-only, does not suppress fields)
- **Task variables**: passed through to all pages. Field values override
  same-named task variables (same precedence as visibility expression scope)

### Known Limitations

**User tasks only**: The wizard renderer is implemented in the task-form
component. Start forms (attached to `startEvent`) do not support `_rdmWizard`.
Place wizard forms on `userTask` elements, not on `startEvent`.

**Flowable Modeler**: Modeler overwrites form JSON on save, which may drop
the `_rdmWizard` field. Workaround: edit form JSON manually or use a merge
script after Modeler export.
