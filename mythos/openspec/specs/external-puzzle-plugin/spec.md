# External Puzzle Plugin

## Purpose

定义外部 `puzzles` 插件的目录布局、运行时导入、注册入口、路径校验、静态资源身份和框架 wheel 交付边界。

## Requirements

### Requirement: External puzzle package layout

The system SHALL treat `Settings.puzzle_root` as the absolute directory of a regular Python package named `puzzles`, and that package SHALL contain the puzzle module code and its module-relative static assets.

#### Scenario: Default external package is colocated with the runtime root

- **WHEN** no `MYTHOS_PUZZLE_ROOT` override is provided
- **THEN** the system SHALL use `<PROJECT_ROOT>/puzzles` and SHALL expect `<PROJECT_ROOT>/puzzles/__init__.py` to exist

#### Scenario: External package overrides the default location

- **WHEN** `MYTHOS_PUZZLE_ROOT` resolves to an absolute directory containing `puzzles/__init__.py`
- **THEN** the system SHALL use that directory for both Python module loading and static asset lookup

### Requirement: Puzzle package is excluded from the framework wheel

The framework build SHALL NOT include the external `puzzles` package in its wheel, and deployment SHALL provide the package separately as a trusted runtime directory.

#### Scenario: Wheel contents are inspected

- **WHEN** the Mythos wheel is built
- **THEN** the wheel SHALL contain the `mythos` framework package but SHALL NOT contain a `puzzles/` package

#### Scenario: Framework wheel runs with an external plugin

- **WHEN** the framework wheel is installed and a valid external `puzzles` directory is present
- **THEN** the application SHALL load the external package without requiring that package to be installed by pip

### Requirement: Explicit puzzle registration entry point

The external `puzzles` package SHALL expose a callable `register_all(registries, *, environment)` entry point, and the framework SHALL call it during application assembly before runtime catalogs are frozen.

#### Scenario: Valid registration entry point

- **WHEN** `puzzles.register_all` is callable
- **THEN** the framework SHALL pass the mutable `RegistryBundle` and resolved environment to it before entering the application lifespan

#### Scenario: Missing registration entry point

- **WHEN** the imported package does not expose a callable `register_all`
- **THEN** application creation SHALL fail with an error identifying the required entry point

### Requirement: Runtime plugin import validation

The framework SHALL insert the configured `puzzle_root` parent into `sys.path` before importing `puzzles`, and SHALL reject an import whose resolved package directory differs from the configured root.

#### Scenario: Plugin parent is not already importable

- **WHEN** `puzzle_root.parent` is absent from `sys.path`
- **THEN** the framework SHALL insert its normalized string path before calling `importlib.import_module("puzzles")`

#### Scenario: Same package name resolves from another directory

- **WHEN** Python resolves `puzzles` from a directory different from `Settings.puzzle_root`
- **THEN** application creation SHALL fail instead of silently loading the wrong plugin

### Requirement: One puzzle root per process

The framework SHALL NOT silently switch the loaded `puzzles` package to a second root within the same Python process.

#### Scenario: A second app requests a different plugin root

- **WHEN** `puzzles` has already been loaded from one root and a later app requests another root
- **THEN** the framework SHALL report a plugin-root conflict or use an isolated process, but SHALL NOT reuse the first package as the second plugin

### Requirement: Stable logical static identities

Moving puzzle modules to the external package SHALL NOT change a static source locator or object key when its module name and relative path remain unchanged.

#### Scenario: Example assets are moved without renaming

- **WHEN** Example keeps module `example` and relative source path `assets/public/README.txt`
- **THEN** its locator SHALL remain `example:assets/public/README.txt` and its object key SHALL remain `static/example/assets/public/README.txt`
