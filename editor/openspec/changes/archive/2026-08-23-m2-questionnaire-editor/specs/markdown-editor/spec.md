## MODIFIED Requirements

### Requirement: Markdown entity state is a source-namespaced ordered segment collection

The system SHALL support a `markdown` entity kind with `ui_kind` `markdown`, registry grouping `markdown`, and resource_id namespace `source`. Its state SHALL contain `sort`, an explicit array of segment UUIDs, and `segments`, a record keyed by segment UUID where each segment has an `id` matching its key and a `content` string.

#### Scenario: Create an empty markdown entity

- **WHEN** a user creates a markdown entity with resource_id `source:guide` and state `{ "sort": [], "segments": {} }`
- **THEN** the entity is created with `ui_kind` `markdown` and an empty ordered segment collection

#### Scenario: Create a markdown entity with ordered segments

- **WHEN** a user creates a markdown entity with `sort: ["s1", "s2"]` and matching segments
- **THEN** the entity is accepted and preserves the explicit order
