# Questionnaire-Editor Specification

## Purpose

Adds a questionnaire source-file entity type with ordered questions, server-side state validation, and a dedicated editor that supports markdown descriptions, choice/text question preview and editing, per-question locking, and reordering.

## Requirements

### Requirement: Questionnaire entity state is a source-namespaced ordered question collection

The system SHALL support a `questionnaire` entity kind with `ui_kind` `questionnaire` and resource_id namespace `source`. Its state SHALL contain `description` (a markdown string), `sort` (an explicit array of question UUIDs), and `questions` (a record keyed by question UUID). Each question SHALL have an `id` matching its record key, a `type` of `choice` or `text`, a markdown `description`, and type-specific `data`:

- `choice` data SHALL be `{ single: boolean, options: string[] }`;
- `text` data SHALL be `{ format: string | null }`.

#### Scenario: Create an empty questionnaire entity

- **WHEN** a user creates a questionnaire entity with resource_id `source:survey` and state `{ "description": "", "sort": [], "questions": {} }`
- **THEN** the entity is created with `ui_kind` `questionnaire` and an empty ordered question collection

#### Scenario: Create a questionnaire with choice and text questions

- **WHEN** a user creates a questionnaire with `sort: ["q1", "q2"]` and matching questions where `q1` is a choice question and `q2` is a text question
- **THEN** the entity is accepted and preserves the explicit order and type-specific data

### Requirement: Questionnaire state is validated before persistence

The system SHALL reject questionnaire state where `description` is not a string, `sort` is not an array, contains duplicate UUIDs, does not cover every question key, or references a missing question. Each question SHALL have an `id` equal to its record key, a valid `type`, a string `description`, and `data` matching its type. Choice data SHALL contain a boolean `single` and a string array `options`. Text data SHALL contain a `format` that is null or a string.

#### Scenario: Reject invalid question type

- **WHEN** a user creates a questionnaire whose question has `type: "unknown"`
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject choice data missing options

- **WHEN** a user creates a questionnaire whose choice question data has no `options`
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject incomplete sort coverage

- **WHEN** a user creates a questionnaire whose `sort` omits a question present in `questions`
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject duplicate sort entries

- **WHEN** a user creates a questionnaire whose `sort` contains the same UUID twice
- **THEN** the system rejects the request with a validation error

#### Scenario: Reject mismatched question id

- **WHEN** a user creates a questionnaire where a question key differs from its `id`
- **THEN** the system rejects the request with a validation error

### Requirement: Questionnaire editor displays description and questions in explicit order

The system SHALL render the questionnaire description as a markdown preview and render questions in the order defined by `sort`, as a vertical list of cards. The editor SHALL provide a way to add new questions and SHALL preserve the explicit order when questions are reordered.

#### Scenario: Render questions by sort order

- **WHEN** a questionnaire has `sort: ["q2", "q1"]`
- **THEN** the editor displays question `q2` before question `q1`

#### Scenario: Add a question

- **WHEN** a user adds a new question to a questionnaire
- **THEN** the new question is appended to the end of `sort` and appears in the editor

### Requirement: Question editing is locked per question

The system SHALL require a question-level lock before a user can edit a questionnaire question. While another user holds the lock for a question, the editor SHALL prevent editing that question and SHALL indicate the lock holder. The questionnaire description SHALL use a separate description-level lock.

#### Scenario: Edit a question acquires a question lock

- **WHEN** a user begins editing a questionnaire question
- **THEN** the system acquires a lock on that question path and the user can modify its description, type, and data

#### Scenario: Another user locks a question

- **WHEN** a question is locked by another user
- **THEN** the editor prevents editing that question and displays the lock holder

### Requirement: Question preview renders by type

The system SHALL render a question's markdown description in the upper part of its card. The lower part SHALL render type-specific preview content: a choice question SHALL show selectable options using radio buttons when `single` is true and checkboxes when `single` is false; a text question SHALL show an input sample and, when a `format` is present, a regex format hint.

#### Scenario: Preview single-choice question

- **WHEN** a choice question has `single: true` and options `["A", "B"]`
- **THEN** the card displays the description and two radio-button options

#### Scenario: Preview multiple-choice question

- **WHEN** a choice question has `single: false` and options `["A", "B"]`
- **THEN** the card displays the description and two checkbox options

#### Scenario: Preview text question with format hint

- **WHEN** a text question has `format: "^[0-9]{4}$"`
- **THEN** the card displays an input sample and a format hint for that regex

### Requirement: Questionnaire questions can be saved, deleted, and reordered

The system SHALL allow an editing user to save question changes, delete a question, and change question order. Deleting a question SHALL remove it from both `questions` and `sort`. Reordering SHALL update `sort` without changing question contents.

#### Scenario: Save question changes

- **WHEN** a user confirms edits to a question
- **THEN** the question data is persisted and the editor returns to preview mode

#### Scenario: Delete a question

- **WHEN** a user deletes a question
- **THEN** the question is removed from `questions` and `sort`, and the editor no longer displays it

#### Scenario: Move a question up or down

- **WHEN** a user moves a question up or down in the editor
- **THEN** the `sort` array is updated and the card order changes accordingly

### Requirement: Questionnaire markdown preview disables raw HTML

The system SHALL render questionnaire description and question description markdown as HTML in preview mode using a markdown parser with raw HTML disabled. The rendered preview SHALL use the current theme's color tokens.

#### Scenario: Render markdown description

- **WHEN** a questionnaire description contains `# Survey`
- **THEN** the editor displays the description as a rendered heading

#### Scenario: Raw HTML is not enabled

- **WHEN** a questionnaire description contains raw HTML
- **THEN** the rendered preview does not execute or display the raw HTML as active markup
