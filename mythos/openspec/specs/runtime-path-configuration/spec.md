# Runtime Path Configuration

## Purpose

定义以当前工作目录为运行根目录的环境加载、默认文件路径、相对路径解析、SQLite 快照路径和 Alembic 迁移策略。

## Requirements

### Requirement: Current working directory is the runtime root

The system SHALL define `PROJECT_ROOT` as `Path.cwd().resolve()` during process startup, SHALL NOT derive it from a source file location, and SHALL NOT use a `PROJECT_ROOT_OFFSET` parameter.

#### Scenario: Application starts from the backend directory

- **WHEN** the process current directory is `<repository>/mythos`
- **THEN** `PROJECT_ROOT` SHALL resolve to `<repository>/mythos`

#### Scenario: Application starts from another directory

- **WHEN** the process current directory is not the intended backend runtime directory
- **THEN** the system SHALL use that directory as the runtime root and startup validation SHALL expose any missing required files or plugin clearly

### Requirement: Environment file follows the runtime root

Settings SHALL load the optional `.env` file from `PROJECT_ROOT/.env`, while explicitly supplied `MYTHOS_` process environment variables SHALL retain precedence.

#### Scenario: Runtime root contains an environment file

- **WHEN** `PROJECT_ROOT/.env` exists
- **THEN** `Settings` SHALL load values from that file

#### Scenario: Source code is installed elsewhere

- **WHEN** the Mythos framework is imported from a wheel outside the runtime root
- **THEN** Settings SHALL continue looking for `.env` under `PROJECT_ROOT`, not beside the installed Python source

### Requirement: Default application paths follow PROJECT_ROOT

The system SHALL derive default database, puzzle, checkpoint, catalog snapshot, and development static page paths from `PROJECT_ROOT`.

#### Scenario: Defaults are used from the backend directory

- **WHEN** no corresponding path override is configured
- **THEN** the system SHALL use `data/mythos.sqlite3`, `puzzles`, `data/checkpoints`, the three catalog snapshots under `data`, and `example` below `PROJECT_ROOT`

#### Scenario: Development page is mounted

- **WHEN** `environment` is `development`
- **THEN** `/example` SHALL serve files from `PROJECT_ROOT/example`, independently from the external puzzle package assets

### Requirement: Relative path settings use PROJECT_ROOT

Relative filesystem paths supplied through Settings SHALL be resolved against `PROJECT_ROOT`; absolute paths SHALL remain absolute. This rule SHALL apply to `puzzle_root`, checkpoint directory, explicit catalog snapshot paths, and relative SQLite database file paths.

#### Scenario: Relative puzzle root is configured

- **WHEN** `MYTHOS_PUZZLE_ROOT=./puzzles`
- **THEN** `Settings.puzzle_root` SHALL resolve to `PROJECT_ROOT/puzzles`

#### Scenario: Relative snapshot path is configured

- **WHEN** a catalog snapshot override is a relative path
- **THEN** the snapshot store SHALL read and write it below `PROJECT_ROOT`

#### Scenario: Absolute path is configured

- **WHEN** a path override is absolute
- **THEN** the system SHALL use that absolute path without prefixing `PROJECT_ROOT`

### Requirement: SQLite and snapshot paths share one base

The system SHALL normalize relative SQLite database URLs before database creation, and default catalog snapshots SHALL be located beside a file-backed SQLite database when one is configured.

#### Scenario: Relative file-backed SQLite URL is used

- **WHEN** `MYTHOS_DATABASE_URL` points to a relative SQLite file
- **THEN** the database directory, database file, and default catalog snapshots SHALL resolve under the same `PROJECT_ROOT`-based location

#### Scenario: In-memory or non-SQLite database is used

- **WHEN** the database URL is in-memory or not SQLite
- **THEN** the system SHALL retain the `PROJECT_ROOT/data` fallback for default catalog snapshots

### Requirement: Alembic uses the runtime root

Alembic commands SHALL be executed with the runtime-root `alembic.ini`, SHALL locate `migrations/` and `src/` below that root, and SHALL obtain the normalized database URL through the same Settings path policy as the application.

#### Scenario: Migration runs from the backend directory

- **WHEN** `alembic -c alembic.ini upgrade head` is executed from `PROJECT_ROOT`
- **THEN** migrations SHALL run against the same default database selected by the application

#### Scenario: Migration configuration is outside the runtime root

- **WHEN** an Alembic configuration from another directory is selected
- **THEN** the command SHALL not be considered a supported way to target the application runtime unless its paths and Settings environment are explicitly aligned

### Requirement: Runtime path failures are diagnosable

The system SHALL report the resolved `PROJECT_ROOT`, `puzzle_root`, and the reason for missing or invalid runtime paths when startup cannot assemble the application.

#### Scenario: Puzzle plugin directory is missing

- **WHEN** the configured puzzle root does not contain the required external package
- **THEN** startup SHALL fail with an error identifying the resolved root and the missing plugin contract
