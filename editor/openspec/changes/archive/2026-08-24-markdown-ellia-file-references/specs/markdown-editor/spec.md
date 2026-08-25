## MODIFIED Requirements

### Requirement: Markdown preview renders markdown content

The system SHALL render a segment's markdown content as HTML in preview mode using a markdown parser with raw HTML disabled. The rendered preview SHALL use the current theme's color tokens. In addition, a valid `ellia://file/<file_uuid>` image destination SHALL be resolved to the current site's authenticated file endpoint only in the rendered HTML; the segment's stored Markdown content SHALL remain unchanged.

#### Scenario: Render markdown preview

- **WHEN** a segment contains `# Title` and is not being edited
- **THEN** the editor displays the segment as a rendered heading

#### Scenario: Raw HTML is not enabled

- **WHEN** a segment contains raw HTML
- **THEN** the rendered preview does not execute or display the raw HTML as active markup

#### Scenario: Render an Ellia file image without changing source content

- **WHEN** a segment contains `![Cover](ellia://file/550e8400-e29b-41d4-a716-446655440000)` and is not being edited
- **THEN** the editor displays the image using the current site's file endpoint while the segment content remains the original `ellia://file/<file_uuid>` Markdown

#### Scenario: Keep invalid Ellia image references safe

- **WHEN** a segment contains an invalid `ellia://file/...` image destination
- **THEN** the editor does not issue an unvalidated file request or render the custom-protocol value as an arbitrary network source
