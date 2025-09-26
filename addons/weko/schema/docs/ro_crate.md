# RO-Crate Split Handling

## Purpose of `wk:isSplited`

`wk:isSplited` indicates whether the root `Dataset` (`@id: "./"`) is represented as a single dataset or split into item-level nodes. The flag must be decided by the exporter, not supplied from metadata.

- `false`: the root `Dataset` is self-contained. Its `hasPart` array points directly to `File` entities (`@type: "File"`).
- `true`: the root `Dataset` becomes a collection of item nodes. Its `hasPart` only lists those item nodes; each item then points to the actual files.

## Item Node Structure

When `wk:isSplited` is `true`, the exporter reuses each grouped dataset entity as an item node.

- The root `Dataset` (`./`) is synthesized as an aggregator with `@type = Dataset`, `wk:isSplited = true`, and `hasPart` pointing at the grouped dataset IDs.
- Attributes that are identical (ignoring null/empty values) across every grouped dataset — `name`, `description`, `datePublished`, and any field prefixed with `wk:` (except `wk:isSplited`) — are lifted up to the aggregator. Other fields stay on the item nodes.
- Each dataset node keeps its original `@id` (e.g., `#dataset-1`) but drops `@type`, matching the specification that items are typeless.
- Per-item metadata such as `name`, `description`, `dc:type`, `wk:index`, and `wk:publishStatus` stays attached to those dataset nodes.
- Each dataset node’s `hasPart` now contains only the referenced files (`files/<path>`); the aggregator does not point to files directly.

When splitting, the exporter also rewrites the RO-Crate metadata record (`ro-crate-metadata.json`) so that its `about` field points to the synthesized root (`./`).

## Split Decision Logic

The RO-Crate builder already groups file metadata by their normalized content. The number of groups determines the flag value:

- Single group → `wk:isSplited = false`; keep the legacy behaviour where the root `Dataset` lists files directly.
- Two or more groups → `wk:isSplited = true`; the root `Dataset` lists only item nodes, and each item lists its files.

The same decision logic can be applied to additional datasets (`#dataset-2`, etc.) so that every dataset node follows a consistent rule.

## Behaviour When `wk:isSplited = false`

The confirmed rule is to preserve the legacy behaviour: the root `Dataset` lists the `File` entities in its `hasPart` array without introducing intermediate item nodes.
