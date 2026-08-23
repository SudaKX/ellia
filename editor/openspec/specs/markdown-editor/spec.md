# Markdown-Editor Specification

## Purpose

Adds a markdown source-file entity type with ordered segments, server-side state validation, and a dedicated editor that supports rendering, editing, locking, and reordering individual markdown segments.

## Requirements

### Requirement: Markdown entity state is a source-namespaced ordered segment collection

The system SHALL support a `markdown` entity kind with `ui_kind` `markdown` and resource_id namespace `source`. Its state SHALL contain `sort`, an explicit array of segment UUIDs, and `segments`, a record keyed by segment UUID where each segment has an `id` matching its key and a `content` string.

#### Scenario: Create an empty markdown entity

- **WHEN** a user creates a markdown entity with resource_id `source:guide` and state `{ "sort": [], "segments": {} }`
- **THEN** the entity is created with `ui_kind` `markdown` and an empty ordered segment collection

#### Scenario: Create a markdown entity with ordered segments

- **WHEN** a user creates a markdown entity with `sort: ["s1", "s2"]` and matching segments
- **THEN** the entity is accepted and preserves the explicit order

### Requirement: Markdown state is validated before persistence

The system SHALL reject markdown state where `sort` is not an array, contains duplicate UUIDs, references a segment that does not exist, or does not cover every segment key. Each segment SHALL have an `id` equal to its record key and a string `content`.

#### Scenario: Reject incomplete sort coverage

- **WHEN** a user creates a markdown entity whose `sort` omits a segment present in `segments`
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject duplicate sort entries

- **WHEN** a user creates a markdown entity whose `sort` contains the same UUID twice
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject mismatched segment id

- **WHEN** a user creates a markdown entity where a segment key differs from its `id`
- **THEN** the system rejects the request with a validation error

### Requirement: Markdown editor displays segments in explicit order

The system SHALL render markdown segments in the order defined by `sort`, as a vertical list of cards. The editor SHALL provide a way to add new segments and SHALL preserve the explicit order when segments are reordered.

#### Scenario: Render segments by sort order

- **WHEN** a markdown entity has `sort: ["s2", "s1"]`
- **THEN** the editor displays segment `s2` before segment `s1`

#### Scenario: Add a segment

- **WHEN** a user adds a new segment to a markdown entity
- **THEN** the new segment is appended to the end of `sort` and appears in the editor

### Requirement: Segment editing is locked per segment

The system SHALL require a segment-level lock before a user can edit a markdown segment. While another user holds the lock for a segment, the editor SHALL prevent editing that segment and SHALL indicate the lock holder.

#### Scenario: Edit a segment acquires a segment lock

- **WHEN** a user begins editing a markdown segment
- **THEN** the system acquires a lock on that segment path and the user can modify its content

#### Scenario: Another user locks a segment

- **WHEN** a segment is locked by another user
- **THEN** the editor prevents editing that segment and displays the lock holder

### Requirement: Markdown segments can be saved, deleted, and reordered

The system SHALL allow an editing user to save segment content, delete a segment, and change segment order. Deleting a segment SHALL remove it from both `segments` and `sort`. Reordering SHALL update `sort` without changing segment contents.

#### Scenario: Save segment content

- **WHEN** a user confirms edits to a segment
- **THEN** the segment content is persisted and the editor returns to preview mode

#### Scenario: Delete a segment

- **WHEN** a user deletes a segment
- **THEN** the segment is removed from `segments` and `sort`, and the editor no longer displays it

#### Scenario: Move a segment up or down

- **WHEN** a user moves a segment up or down in the editor
- **THEN** the `sort` array is updated and the card order changes accordingly

### Requirement: Markdown preview renders markdown content

The system SHALL render a segment's markdown content as HTML in preview mode using a markdown parser with raw HTML disabled. The rendered preview SHALL use the current theme's color tokens.

#### Scenario: Render markdown preview

- **WHEN** a segment contains `# Title` and is not being edited
- **THEN** the editor displays the segment as a rendered heading

#### Scenario: Raw HTML is not enabled

- **WHEN** a segment contains raw HTML
- **THEN** the rendered preview does not execute or display the raw HTML as active markup
