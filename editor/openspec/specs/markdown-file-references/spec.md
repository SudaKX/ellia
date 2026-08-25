# Markdown-File-References Specification

## Purpose

Provides a stable, editor-owned Markdown reference format for files stored by Ellia, so previews can resolve file UUIDs without persisting environment-specific HTTP URLs.

## Requirements

### Requirement: Ellia file URI format is stable and validated

The frontend SHALL recognize `ellia://file/<file_uuid>` as the canonical Markdown reference to a file stored by Ellia. The `<file_uuid>` portion MUST identify a UUID in the file storage format; malformed Ellia file URIs MUST NOT be treated as arbitrary HTTP URLs or forwarded to the browser as an unvalidated resource URL.

#### Scenario: Recognize a valid Ellia file URI

- **WHEN** Markdown contains an image destination in the form `ellia://file/550e8400-e29b-41d4-a716-446655440000`
- **THEN** the frontend recognizes it as an Ellia file reference and extracts the file UUID

#### Scenario: Reject a malformed Ellia file URI

- **WHEN** Markdown contains an image destination such as `ellia://file/not-a-uuid` or an Ellia file URI with an extra path component
- **THEN** the frontend does not resolve it to an arbitrary URL or issue a file request for an unvalidated identifier

### Requirement: Preview resolves Ellia file images to the current file API

When previewing Markdown, the frontend SHALL resolve a valid `ellia://file/<file_uuid>` image reference to the current site's authenticated file endpoint `/api/files/<encoded_file_uuid>`. The resolved URL MUST be generated only during rendering; the Markdown source and synchronized entity state MUST retain the original Ellia URI. Existing ordinary image destinations SHALL retain their current behavior.

#### Scenario: Render a valid Ellia file image

- **WHEN** preview renders `![Cover](ellia://file/550e8400-e29b-41d4-a716-446655440000)`
- **THEN** the resulting image element uses the current site's `/api/files/550e8400-e29b-41d4-a716-446655440000` endpoint as its source and preserves the `Cover` alt text

#### Scenario: Preserve image title while resolving

- **WHEN** preview renders `![Cover](ellia://file/550e8400-e29b-41d4-a716-446655440000 "Front cover")`
- **THEN** the resulting image element uses the resolved file endpoint and preserves the `Front cover` title

#### Scenario: Keep ordinary image destinations compatible

- **WHEN** preview renders an image whose destination is an ordinary `https`, `http`, or existing relative destination
- **THEN** the frontend does not apply Ellia file UUID resolution and preserves the existing Markdown image behavior

#### Scenario: Do not persist the resolved URL

- **WHEN** a user previews and saves Markdown containing a valid Ellia file URI
- **THEN** the persisted and synchronized Markdown content still contains `ellia://file/<file_uuid>` and does not contain the current origin or `/api/files/<file_uuid>` URL

#### Scenario: Safely display an invalid Ellia image reference

- **WHEN** preview encounters a malformed Ellia file image destination
- **THEN** the preview does not request an unvalidated custom-protocol or arbitrary network URL and displays a non-network failure/placeholder representation for that image

### Requirement: File manager can copy a Markdown image reference

The file management interface SHALL provide an action to copy a selected file as a Markdown image reference. The copied text MUST use the file's original name as the image alt text when available, fall back to the file UUID when it is not available, and use `ellia://file/<file_uuid>` as the image destination. This action SHALL NOT insert content into an open editor or modify any entity.

#### Scenario: Copy a Markdown image reference for a named file

- **WHEN** a user chooses “复制 Markdown 图片引用” for a file with original name `cover.png` and UUID `550e8400-e29b-41d4-a716-446655440000`
- **THEN** the clipboard receives `![cover.png](ellia://file/550e8400-e29b-41d4-a716-446655440000)`

#### Scenario: Copy a reference for a file without an original name

- **WHEN** a user chooses “复制 Markdown 图片引用” for a file without an original name
- **THEN** the clipboard receives a valid Markdown image reference whose alt text falls back to the file UUID and whose destination contains the unchanged file UUID

#### Scenario: Copying a reference does not edit entities

- **WHEN** a user copies a Markdown image reference
- **THEN** no Markdown segment, questionnaire description, entity revision, or entity version is changed
