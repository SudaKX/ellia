## Why

当前谜题模块位于 `src/mythos/puzzles`，与 Mythos 框架一起被 Python 包发现机制管理；这使谜题内容难以作为独立部署单元提供。与此同时，`PROJECT_ROOT` 由框架源码位置推导，安装 wheel 后可能指向 `site-packages`，导致 `.env`、数据库、运行时资源和静态页面不再位于实际部署目录。

需要建立明确的“框架 wheel + 外部 puzzles 插件 + 运行目录”边界，使插件可以独立替换，并让运行时文件路径具有统一、可预测的基准。

## What Changes

- 新增外部 `puzzles` 插件契约：根包必须暴露可调用的 `register_all`，由框架在应用装配期显式加载。
- **BREAKING** 移除框架对 `mythos.puzzles` 的内置导入依赖；谜题模块代码和资源迁移到运行根目录下的 `puzzles/`。
- `puzzles/` 不纳入 Mythos wheel，部署时作为独立的受信任 Python 插件目录提供。
- 框架根据 `Settings.puzzle_root` 将其上级目录加入 `sys.path`，通过 `importlib` 加载固定名称 `puzzles`，并校验加载位置和 `register_all` 契约。
- **BREAKING** `PROJECT_ROOT` 改为进程启动目录 `Path.cwd().resolve()`，取消 `PROJECT_ROOT_OFFSET`。
- `.env`、默认数据库、`puzzles`、checkpoint、Catalog snapshot 和开发交互页等默认路径统一从新的 `PROJECT_ROOT` 派生。
- 配置中的相对文件路径统一解释为相对于 `PROJECT_ROOT`；显式绝对路径保持不变。
- Alembic 的迁移目录和默认数据库路径与运行根目录对齐，并更新开发文档、测试和启动约定。

## Capabilities

### New Capabilities

- `external-puzzle-plugin`: 规定外部 `puzzles` 包的目录、导入、注册、错误处理和 wheel 排除行为。
- `runtime-path-configuration`: 规定 cwd 运行根目录、默认文件路径、相对配置路径和 Alembic 的路径基准。

### Modified Capabilities

无。

## Impact

- 影响 `src/mythos/main.py`、`src/mythos/core/config.py`、`pyproject.toml`、Alembic 配置及迁移入口。
- 影响 `src/mythos/puzzles`、根目录 `puzzles/`、Example 资源和相关测试导入路径。
- 影响本地启动、wheel 部署、服务管理器 working directory 和 reload 行为。
- 不改变静态资源的 `source_locator`、对象键或现有 API；模块名和资源相对路径不变时不需要数据库迁移。
