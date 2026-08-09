# Example VTB Task Console

## Purpose

定义 Example test console 对 VTB recovery 任务状态的展示、倒计时、显式处理和认证状态清理行为。

## Requirements

### Requirement: Example console displays lazy VTB recovery state

The Example test console SHALL load the existing `GET /api/v1/tasks` snapshot with Credits data and SHALL display the `example.vtb-allowance` task state when the player is authenticated. The display SHALL include the current VTB balance, the task state, the next due time from `time_2`, a client-side countdown when a due time exists, and the persisted `meta` fields `initial_grant_applied`, `total_granted`, and `last_granted_at`.

#### Scenario: Authenticated console shows recovery state

- **WHEN** an authenticated player loads or reads the Example workspace
- **THEN** the console SHALL show the current VTB balance and the latest `example.vtb-allowance` snapshot, including its next due time and persisted grant metadata

#### Scenario: Console communicates lazy execution

- **WHEN** the next due time is reached while the player does not activate a task trigger
- **THEN** the console SHALL indicate that the task is ready or due, but SHALL NOT automatically call `POST /api/v1/tasks/process` or claim that VTB has already been granted

#### Scenario: Missing task state is visible

- **WHEN** the authenticated task snapshot does not contain `example.vtb-allowance`, or its first-processing metadata is incomplete
- **THEN** the console SHALL show an explicit not-initialized state rather than inferring a successful grant

### Requirement: Example console provides explicit VTB task processing

The Example test console SHALL provide a separate active control for processing the current task state. The control SHALL call the existing `POST /api/v1/tasks/process` endpoint with a fresh UUID `Request-ID` for every activation, prevent concurrent duplicate activation while the request is pending, and reload authoritative Credits and Task state after a successful response.

#### Scenario: Player actively processes allowance

- **WHEN** an authenticated player activates the VTB recovery control
- **THEN** the console SHALL disable the control while pending, display the task report, and refresh the displayed VTB balance and task metadata from the server

#### Scenario: Read-only refresh does not process tasks

- **WHEN** the player activates the existing general refresh control
- **THEN** the console SHALL perform only the existing read operations and SHALL NOT call `POST /api/v1/tasks/process`

#### Scenario: Processing fails

- **WHEN** the explicit task request returns an error or cannot reach the server
- **THEN** the console SHALL keep the last known task and VTB state, show a user-readable error, and re-enable the active control

#### Scenario: Authentication is cleared

- **WHEN** the player logs out or the session becomes invalid
- **THEN** the console SHALL clear the VTB task snapshot, countdown, processing state, and recovery message
