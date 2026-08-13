## Context

当前 Mythos 使用 `src` layout。`PROJECT_ROOT` 从 `src/mythos/core/config.py` 的源码位置向上推导，默认 `puzzle_root` 指向 `src/mythos/puzzles`；`main.py` 在模块导入阶段直接导入 `mythos.puzzles.register_all`。Example 的 Python 注册代码和资源也处于同一个安装包目录中。

本变更将 Mythos 框架和谜题内容拆成两个运行时单元：框架作为 wheel 安装，根目录 `puzzles/` 作为外部受信任插件提供。插件目录同时是静态资源根目录，资源仍由现有 Registry 和 `StaticAssetPublisher` 读取、物化和冻结。

运行目录改为启动进程的当前工作目录。`.env`、数据库、checkpoint、Catalog snapshot、Alembic 配置和开发页都以该目录作为默认路径基准。配置中允许使用绝对路径；相对文件路径统一解析为运行根目录相对路径。

## Goals / Non-Goals

**Goals:**

- 使 `puzzles/` 不进入 Mythos wheel，并能在安装后的框架进程中作为外部 Python 包加载。
- 要求插件根包暴露明确、可校验的 `register_all` 注册入口。
- 在加载插件前根据 `Settings.puzzle_root` 注入其上级目录到 `sys.path`，避免依赖当前目录恰好能够导入插件。
- 让 `.env`、应用默认文件路径、相对配置路径和 Alembic 使用同一个运行根目录语义。
- 保持现有 `FileReference` 的逻辑模块名、相对资源路径、对象 key 和 API 契约不变。
- 在插件缺失、入口缺失、路径不匹配或重复加载不同插件根目录时尽早失败。

**Non-Goals:**

- 不实现多个 puzzle 插件的并行加载、目录扫描或 entry point 自动发现。
- 不把插件打包进 wheel，也不建立插件独立发布、依赖解析或版本升级系统。
- 不允许插件新增通用 HTTP Router、Service、ORM Model 或绕过现有事务边界。
- 不改变静态文件、Hint、Artifact、Progress 等 Registry 的运行期冻结模型。
- 不进行数据库 schema migration；资源逻辑 locator 不变时只复用已有静态文件登记。

## Decisions

### 1. 固定外部包名和目录关系

`Settings.puzzle_root` 指向名为 `puzzles` 的常规 Python package 目录，目录中同时包含插件代码和模块资源：

```text
<PROJECT_ROOT>/puzzles/
  __init__.py
  example/
    __init__.py
    assets/
```

`puzzle_root.parent` 是导入搜索路径，`puzzle_root` 是资源读取根。这样 `importlib.import_module("puzzles")` 与 `puzzle_root / module / relative_path` 使用同一份部署内容。

选择固定包名而不是扫描目录，是为了保持注册顺序、错误位置和启动结果确定。`puzzles.__init__` 负责显式导入各模块并实现 `register_all`，框架不遍历子目录。

### 2. 延迟并验证插件加载

移除 `main.py` 的顶层 `mythos.puzzles` 导入。`create_app()` 解析 Settings 后，在默认创建 RegistryBundle 前加载插件：

1. 将 `puzzle_root` 规范化为绝对路径。
2. 将规范化的 `puzzle_root.parent` 置于 `sys.path` 前部。
3. 调用 `importlib.invalidate_caches()`，再导入固定名称 `puzzles`。
4. 检查模块的 `__file__` 所在目录等于配置的 `puzzle_root`。
5. 检查 `register_all` 是可调用对象。
6. 调用 `register_all(registries, environment=resolved_settings.environment)`。

`environment` 是框架传递给插件的通用启动上下文，用来替代当前只服务 Example 的 `example_initial_vtb` 参数；开发/测试初始奖励等内容策略由插件自行决定。

同一进程只允许一个已加载的 `puzzles` 根目录。如果 `sys.modules` 中已有来自其他目录的同名包，加载器必须报告路径冲突，而不能仅依赖 `sys.path` 顺序静默复用旧包。这样可以避免测试或多次创建 app 时使用错误的模块代码和回调引用。

### 3. 保持 wheel 和插件边界

保留 setuptools 的 `where = ["src"]` 包发现范围，不将根目录 `puzzles` 添加到 wheel。框架 wheel 只提供 `mythos`；插件由源码目录、部署卷或其他外部交付方式提供。

构建验证需要检查 wheel 文件列表中不存在 `puzzles/`。运行验证则需要在不同于插件父目录的启动环境中确认：框架仍能通过运行时注入的路径找到插件。

### 4. 以 cwd 定义运行根目录

取消 `PROJECT_ROOT_OFFSET`，将：

```python
PROJECT_ROOT = Path.cwd().resolve()
```

作为唯一运行根目录定义。框架不再通过 `__file__` 推导业务运行目录，也不从 `.env` 读取运行根目录，因为 `.env` 的位置必须先由运行根目录确定。

运行契约是从后端项目目录启动：

```text
<repository>/mythos/
```

服务管理器、IDE、Uvicorn reload 子进程和迁移命令都必须保持该 working directory。

### 5. 统一相对路径解析

Settings 构造完成后，所有文件系统路径遵循同一规则：绝对路径保持原值；相对路径以 `PROJECT_ROOT` 为基准解析并规范化。覆盖范围包括 `puzzle_root`、`checkpoint_directory`、三个 snapshot path 和 SQLite URL 中的文件路径。

数据库 URL 需要通过 SQLAlchemy 的结构化 URL API 解析和重建，不能用字符串拼接处理 Windows 路径。数据库路径规范化后，snapshot 的默认目录继续优先跟随数据库所在目录；非 SQLite 或内存数据库继续使用 `PROJECT_ROOT/data` 的 snapshot fallback。

### 6. Alembic 与应用共享运行根目录

`alembic.ini`、`migrations/` 和 `src/` 位于 `PROJECT_ROOT`。Alembic 继续使用 `%(here)s` 定位迁移脚本和 Python 源码，但命令要求从 `PROJECT_ROOT` 执行并使用该目录下的 `alembic.ini`。`migrations/env.py` 通过 `get_settings()` 获取已经规范化的数据库 URL，因此 offline 和 online migration 使用与应用相同的数据库。

### 7. 保持资源逻辑身份

Example 仍以 `example` 作为 module，资源仍使用 `assets/...` 相对路径。物理移动到根目录后，以下值保持不变：

```text
example:assets/public/README.txt
static/example/assets/public/README.txt
```

因此不需要为目录移动创建数据库迁移，也不应将 `puzzles/` 前缀写入 `FileReference.relative_path`。

## Risks / Trade-offs

- **错误 cwd 读取错误配置或数据库** → 启动时记录解析后的 `PROJECT_ROOT` 和 `puzzle_root`，校验插件包实际位置；文档和服务配置强制设置 working directory。
- **外部插件代码与框架 API 不兼容** → 入口校验只解决形状问题，首版通过完整测试和启动失败信息控制风险；后续可增加插件 API version，但不纳入本次范围。
- **`puzzles` 模块缓存导致测试串根** → 单进程只允许一个插件根目录，并在加载器中检查 `__file__`；测试使用隔离进程或统一插件根。
- **外部插件不在 Uvicorn reload 监控目录** → 默认插件位于 `PROJECT_ROOT/puzzles` 时由项目目录覆盖；通过 `MYTHOS_PUZZLE_ROOT` 放到外部目录时，部署必须负责重启或额外配置 reload 监控目录。
- **相对 SQLite URL 的 Windows 解析错误** → 使用 SQLAlchemy URL 对象规范化数据库路径，并增加 Windows 风格路径测试。
- **插件目录可执行任意 Python 代码** → 将 `MYTHOS_PUZZLE_ROOT` 视为部署级受信任配置，不允许由 HTTP 请求或玩家数据影响。
- **wheel 与插件分开交付增加运维步骤** → 在启动前检查插件目录和 `register_all`，并在部署文档中明确同时交付框架 wheel 与插件目录。

## Migration Plan

1. 先增加插件加载器、运行根目录解析器和对应单元测试，保留现有数据逻辑不变。
2. 将 `src/mythos/puzzles` 迁移为根目录 `puzzles`，更新插件入口、资源路径和测试导入。
3. 更新 Settings、默认路径、相对路径规范化、Alembic 配置和开发文档。
4. 在源码目录和独立安装环境中分别验证：wheel 不含 `puzzles`，但外部插件可被加载并完成静态资源物化。
5. 执行完整测试和迁移命令，确认现有 `static_file_registrations` 通过相同 locator 复用。

回滚时恢复框架内置 `mythos.puzzles` 导入、源码相对的 `PROJECT_ROOT` 和旧配置语义；数据库 schema 无需回滚。外部插件目录可保留，不会改变已有对象 key。

## Open Questions

- 是否在首版插件契约中加入 `PLUGIN_API_VERSION`，还是仅要求 `register_all` 入口并依赖测试发现兼容性问题？
