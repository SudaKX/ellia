# Ellia Agent Guide

## 仓库边界

- `mythos/` 是 Python 3.13+ 的 FastAPI 后端；入口为 `mythos/src/mythos/main.py:create_app()`，固定 Router 全部挂在 `/api/v1`。
- `desktop/` 是独立的 Vue 3/Vite 应用；入口为 `desktop/src/main.ts`，桌面状态由 Pinia 的 `src/stores/desktop.ts` 管理。
- 后端启动期会物化静态文件并冻结 `RegistryBundle` 为只读 Catalog。谜题内容应在冻结前注册；模块不能新增通用 callback HTTP 路由。
- Service 是全局对象，只接收请求级 `Player` 和冻结 Catalog；写入路径必须通过 `CommandTransactionExecutor`，不要在 Service 或模块中自行提交 Session。

## Mythos 后端

- 只使用根目录 `.venv`，不要在 `mythos/` 下创建虚拟环境。
- 从 `mythos/` 目录安装、测试与启动：

  ```powershell
  ..\.venv\Scripts\python.exe -m pip install --editable ".[dev]"
  ..\.venv\Scripts\python.exe -m pytest tests
  ..\.venv\Scripts\python.exe -m mythos --reload
  ```

- 聚焦测试使用完整测试目录加 `-k`，例如：

  ```powershell
  ..\.venv\Scripts\python.exe -m pytest tests -k test_global_services_read_frozen_registered_content
  ```

  不要直接按 `test_registry.py`、`test_services.py` 的顺序指定文件；当前会触发导入顺序相关的循环导入。
- 配置从 `mythos/.env` 读取，环境变量必须使用 `MYTHOS_` 前缀；该文件及 `mythos/credentials.json` 均不得提交。
- 数据库迁移必须从 `mythos/` 目录显式指定配置：

  ```powershell
  ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
  ```

- RustFS 集成测试默认跳过。设置 `MYTHOS_RUSTFS_INTEGRATION=1` 后才会连接本地 S3 端点，并创建、启用版本控制后删除临时 bucket；需要相应权限。

## Desktop 前端

- 使用 pnpm 和 `desktop/pnpm-lock.yaml`；从根目录执行：

  ```powershell
  pnpm --dir desktop install --frozen-lockfile
  pnpm --dir desktop dev
  pnpm --dir desktop build
  ```

- `build` 会先运行 `vue-tsc --build` 再执行 Vite 构建；当前没有独立的 lint 或 test script。
- Vite 部署基路径固定为 `/console/`，`@` 映射到 `desktop/src`；修改路由或资源路径时必须保持这两个约束。

## 提交

- 遵循 `COMMIT_CONVENTION.md`：`type(module): description`，`type` 与 `module` 使用小写；一个提交只处理一个明确目的。
