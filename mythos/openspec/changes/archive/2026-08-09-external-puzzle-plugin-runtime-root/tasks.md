## 1. 外部插件包迁移

- [x] 1.1 将 `src/mythos/puzzles` 迁移为运行根目录下的 `puzzles` 包，保留 Example 的模块代码、资源目录和逻辑资源路径。
- [x] 1.2 更新 `puzzles.__init__`，暴露 `register_all(registries, *, environment)`，并将 development/test 的 Example 初始 VTB 逻辑保留在插件侧。
- [x] 1.3 删除框架对 `mythos.puzzles` 的顶层导入和旧模块导入路径，更新直接引用谜题模块的测试。

## 2. 插件加载与注册

- [x] 2.1 新增外部 puzzle loader：规范化 `Settings.puzzle_root`，将其上级目录置于 `sys.path` 前部，并通过 `importlib.import_module("puzzles")` 加载。
- [x] 2.2 为 loader 增加包实际路径、`__init__.py`、`register_all` 可调用性和导入异常校验，错误信息包含解析后的插件根目录。
- [x] 2.3 防止同一进程静默切换不同 `puzzles` 根目录，覆盖 `sys.modules` 缓存冲突和多次 `create_app()` 场景。
- [x] 2.4 在 `create_app()` 的 Registry 注册阶段调用插件入口，并确保调用发生在静态资源物化和 Catalog freeze 之前。
- [x] 2.5 保持插件只能使用既有 Registry、Service 和事务边界，不新增通用 HTTP Router 或自行提交 Session。

## 3. 运行根目录与配置解析

- [x] 3.1 将 `PROJECT_ROOT` 改为 `Path.cwd().resolve()`，移除源码位置推导和 `PROJECT_ROOT_OFFSET` 概念，并更新 Settings 的 `.env` 定位。
- [x] 3.2 将默认 `puzzle_root` 改为 `PROJECT_ROOT / "puzzles"`，并将默认数据库、checkpoint、Example 静态页和 Catalog snapshot 统一改为运行根目录派生路径。
- [x] 3.3 实现统一的相对文件路径解析：`puzzle_root`、checkpoint、三个 snapshot path 的相对值相对于 `PROJECT_ROOT`，绝对值保持不变。
- [x] 3.4 使用 SQLAlchemy 结构化 URL 规范化相对 SQLite 文件路径，确保数据库目录和默认 snapshot 目录使用同一绝对基准，并覆盖 Windows 路径。
- [x] 3.5 增加启动路径诊断和必要的运行目录、插件目录校验，明确报告 `PROJECT_ROOT`、`puzzle_root` 及缺失原因。

## 4. Alembic 与部署路径

- [x] 4.1 调整 `alembic.ini` 和 `migrations/env.py`，使迁移脚本、`src` 导入路径和应用 Settings 使用同一运行根目录及数据库 URL。
- [x] 4.2 更新 `.env.example`、README 和开发运维文档，明确必须从 `mythos/` 目录启动，且相对配置路径相对于 `PROJECT_ROOT`。
- [x] 4.3 补充外部插件部署说明：框架 wheel 与 `puzzles/` 目录分别交付，`MYTHOS_PUZZLE_ROOT` 可指向受信任的绝对插件目录。
- [x] 4.4 说明外部插件位于运行根目录之外时的 reload 监控限制及重启要求。

## 5. 测试与验证

- [x] 5.1 增加 loader 测试，覆盖有效插件、缺少 `register_all`、实际包路径不匹配和同进程不同根目录冲突。
- [x] 5.2 增加运行路径测试，覆盖 cwd 根目录、`.env`、默认路径、相对路径、绝对路径和相对 SQLite URL 的统一解析。
- [x] 5.3 增加 wheel 内容测试，确认 Mythos wheel 不包含 `puzzles/`，并在插件目录不位于当前 import 默认路径时验证外部加载成功。
- [x] 5.4 更新 Example、静态资源、RustFS 和任务测试中的插件路径及导入，确认 source locator、对象 key 和启动期物化行为不变。
- [x] 5.5 从 `mythos/` 目录执行 Alembic migration、聚焦测试和完整测试，确认现有数据库可继续使用且无需新增迁移。
