# Example VTB Task

## Purpose

定义 Example VTB allowance 任务的注册、激活、惰性发放、状态记录和请求触发行为。

## Requirements

### Requirement: Example registers and activates the VTB allowance task

Example SHALL register the stable Task identity `example.vtb-allowance` with an asynchronous Handler that declares `PlayerInterfaces.CREDITS` as a dependency. Example SHALL activate the task for a player during Construct through `Player.tasks.add_task()`.

#### Scenario: Construct activates the task

- **WHEN** a player completes Example Construct
- **THEN** the player's task state SHALL contain `example.vtb-allowance`

#### Scenario: Repeated Construct does not reset state

- **WHEN** Construct or activation runs for a player who already has the task
- **THEN** the existing task `time_1`, `time_2`, `exception`, and `meta` SHALL remain unchanged

### Requirement: First VTB allowance is granted immediately and recorded in meta

The Example Handler SHALL grant up to 5 VTB on its first effective execution, limited by the remaining amount before 10 VTB. The Handler SHALL set the next due time 60 seconds after the effective grant and SHALL record a versioned initialization state in JSON `meta`. The Handler SHALL use the current Credits Interface value as the source of truth for the cap.

#### Scenario: First execution grants five VTB

- **WHEN** a task with empty meta is processed for a player with fewer than 5 VTB
- **THEN** the player SHALL receive 5 VTB, the task SHALL complete normally, and `meta.initial_grant_applied` SHALL be true

#### Scenario: First execution is limited by the cap

- **WHEN** a task with empty meta is processed for a player with 8 or 9 VTB
- **THEN** the Handler SHALL grant only the amount needed to reach 10 VTB and SHALL NOT exceed the cap

#### Scenario: Meta records the initial grant

- **WHEN** the first allowance succeeds
- **THEN** task meta SHALL contain `schema_version`, `initial_grant_applied`, `total_granted`, and `last_granted_at` with JSON-compatible values

### Requirement: VTB allowance follows lazy 60-second periods

After initialization, the Example Handler SHALL defer without changing `time_1` when the current time is before `time_2`. When one or more 60-second periods are due, it SHALL grant at most one VTB per due period and may grant multiple due periods in one request. The resulting VTB SHALL NOT exceed 10.

#### Scenario: Processing before the due time defers

- **WHEN** the player processes the task before `time_2`
- **THEN** the player VTB SHALL remain unchanged, `time_1` SHALL remain unchanged, and the task SHALL remain active

#### Scenario: One due period grants one VTB

- **WHEN** exactly one 60-second period is due and the player has fewer than 10 VTB
- **THEN** the Handler SHALL grant one VTB and advance the next due time

#### Scenario: Missed periods are caught up

- **WHEN** three or more 60-second periods are due and the player has enough room below the cap
- **THEN** the Handler SHALL grant one VTB for each due period in the same Task transaction

#### Scenario: Reaching the cap stops further grants

- **WHEN** the task grant brings the player to 10 VTB
- **THEN** the Handler SHALL grant no additional VTB on subsequent processing until the current VTB is below the cap

### Requirement: Example VTB task remains request-triggered

The Example VTB allowance SHALL execute only through existing TaskExecutor activity points and SHALL NOT create a background scheduler, new HTTP route, or direct Session commit path.

#### Scenario: Explicit task processing executes the allowance

- **WHEN** an authenticated player calls `POST /api/v1/tasks/process`
- **THEN** the existing task transaction SHALL process `example.vtb-allowance` and return its result in the task report

#### Scenario: Read-only access does not grant VTB

- **WHEN** the player reads task or credit state without a write trigger
- **THEN** the VTB balance and task grant metadata SHALL remain unchanged
