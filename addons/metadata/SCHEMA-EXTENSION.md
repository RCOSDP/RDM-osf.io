# Metadata Schema Extensions

This document describes extensions to the standard metadata schema format.

## display_template

For `type: "array"` fields, you can specify a `display_template` to control how the data is displayed in collapsed view.

**Note**: `display_template` for `type: "object"` fields is not currently supported. The implementation focuses on array fields only.

### Behavior

#### For `type: "array"`
- **View mode**: Table display where `display_template` is split by `|` to define each column
  - Example: `"{{prop1}}|{{prop2}}|{{prop3}}"` creates 3 columns
- **Edit mode**: Row expands to show all fields vertically

#### For `type: "object"`
- **Not supported**: `display_template` is ignored for object type fields
- Object fields always display all properties in a standard table format

### Template Variables
- Use `{{property_id}}` to reference properties
- For nested properties, use dot notation: `{{object_id.child_id}}`
- Empty values are rendered as empty strings