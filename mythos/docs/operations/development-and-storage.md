# Mythos 开发与存储运行

本文定义 Mythos 后端在本仓库中的开发启动方式、运行路径和外部服务要求。

## 1. 结论

开发命令统一从后端项目根目录执行：

```text
<repository>/mythos/
```

`mythos/.venv` 是 Mythos 唯一允许使用的 Python 虚拟环境：

```text
<repository>/mythos/.venv/
```

当前默认装配 `Example` 模块。它包含静态文件 Source，应用启动期必须将这些文件发布到 S3 兼容对象存储；应用自身管理内容摘要和 token，bucket versioning 必须停用。因此，已配置并可访问的 RustFS 或 S3 bucket 是启动后端的必要条件，不是可选增强。

## 2. 运行路径

`mythos.core.config.PROJECT_ROOT` 从 `config.py` 的源码位置推导，默认路径不依赖进程当前工作目录：

| 项目 | 默认绝对位置 |
| --- | --- |
| 配置文件 | `<repository>/mythos/.env` |
| SQLite 数据库 | `<repository>/mythos/data/mythos.sqlite3` |
| checkpoint 目录 | `<repository>/mythos/data/checkpoints` |
| 谜题资产根目录 | `<repository>/mythos/src/mythos/puzzles` |
| 开发交互页 | `<repository>/mythos/example` |

但以下值使用相对路径时，仍相对于启动进程的当前工作目录解析：

- `MYTHOS_DATABASE_URL` 中的 SQLite 相对路径。
- `MYTHOS_PUZZLE_ROOT`。
- `MYTHOS_CHECKPOINT_DIRECTORY`。
- Uvicorn 的 `--app-dir` 参数。

因此项目规定从 `mythos/` 目录启动。不要在仓库根目录、IDE 的任意目录或服务管理器默认目录中复用下文命令。确需改变工作目录时，应为上述所有路径提供绝对值，或同步调整相对值。

## 3. 前置服务

### 3.1 本地持久化

SQLite 不需要单独运行服务，但 `mythos/data/` 必须可写且应在开发调试期间保留。目录内容被 Git 忽略；不要把数据库、WAL 文件或 checkpoint 提交到仓库。

### 3.2 RustFS 或 S3

需要一个已创建的私有 bucket，并保持 bucket versioning 停用。后端启动时会全量读取谜题资产，以 SHA-256 摘要和媒体类型决定是否上传；对象 key 固定，不依赖 mtime 或对象存储的 `VersionId`。

后端身份至少需要：

- 上传静态对象。
- 针对指定对象生成预签名读取 URL。
- 读取应用已写入的对象。

浏览器从 `/example/` 或未来 `/console/` 预览预签名 URL 时，RustFS 与 Mythos 通常不同源。bucket CORS 必须允许页面 Origin 的 `GET` 和 `HEAD` 请求；本地页面固定使用 `http://127.0.0.1:8000` 时，应将该完整 Origin 加入规则。不要用 `*` 替代生产环境的精确 Origin。

## 4. 开发配置

复制 `mythos/.env.example` 为 `mythos/.env`，该文件不得提交。所有设置使用 `MYTHOS_` 前缀。

最少需要稳定的签名密钥和完整对象存储配置：

```text
MYTHOS_ENVIRONMENT=development
MYTHOS_JWT_SIGNING_KEY=<at least 32 bytes>
MYTHOS_REFRESH_TOKEN_PEPPER=<at least 32 bytes>
MYTHOS_FILE_ID_SIGNING_KEY=<at least 32 bytes>
MYTHOS_PROBLEM_TYPE_BASE_URL=https://api.example.com/problems

MYTHOS_OBJECT_STORE_ENDPOINT=http://127.0.0.1:9000
MYTHOS_OBJECT_STORE_REGION=us-east-1
MYTHOS_OBJECT_STORE_BUCKET=mythos-dev
MYTHOS_OBJECT_STORE_ACCESS_KEY=<access key>
MYTHOS_OBJECT_STORE_SECRET_KEY=<secret key>
MYTHOS_OBJECT_STORE_USE_TLS=false
```

非生产环境未配置签名密钥时框架会临时生成它们，但重启后 JWT、刷新会话和公开文件 ID 都会失效。开发环境也应提供稳定的本地密钥。

从 `mythos/` 目录运行时，路径覆盖值应写为：

```text
MYTHOS_DATABASE_URL=sqlite+aiosqlite:///./data/mythos.sqlite3
MYTHOS_PUZZLE_ROOT=./src/mythos/puzzles
MYTHOS_CHECKPOINT_DIRECTORY=./data/checkpoints
```

也可以完全省略这三项，使用框架提供的绝对默认路径。

## 5. 启动步骤

从 `mythos/` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install --editable ".[dev]"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m mythos --reload
```

迁移必须先于应用启动执行。`Example` 发布静态资产时会查询静态文件登记表，未执行迁移会导致启动失败。`python -m mythos` 默认监听 `127.0.0.1:8000`；可使用 `--host`、`--port` 和 `--reload` 参数覆盖。

启动成功后：

| 路径 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000/health` | 健康检查 |
| `http://127.0.0.1:8000/api/v1/...` | Mythos API |
| `http://127.0.0.1:8000/example/` | 开发模式的 Example 交互测试页 |

`/example/` 仅在 `MYTHOS_ENVIRONMENT=development` 时挂载。它与 API 同源，因此 Mythos API 不需要为该页面配置 CORS。

## 6. 常见启动问题

| 现象 | 原因与处理 |
| --- | --- |
| `Object storage is not configured` | Example 有静态资产。补齐 endpoint、bucket、access key、secret key 和 TLS 配置，并确认 bucket 可私有读写。 |
| 静态资产发布失败 | 检查 bucket 存在、身份有上传权限、`MYTHOS_PUZZLE_ROOT` 指向 `puzzles` 目录，且 Source 文件存在。 |
| `no such table: static_file_registrations` | 从 `mythos/` 目录执行 Alembic upgrade head。 |
| `/example/` 返回 404 | 确认环境为 `development`，并通过开发服务器而非生产部署访问。 |
| 页面能获取 content URL 但预览失败 | 为 RustFS bucket 配置该页面 Origin 的 CORS；“Open”导航不等同于 JavaScript `fetch()` 预览。 |

## 7. 部署边界

本仓库当前只提供开发 Uvicorn 命令，没有 Docker、Nginx、systemd 或生产 ASGI 进程配置。生产部署需要另行提供：

- HTTPS 反向代理与 ASGI 进程托管。
- 私有、停用 bucket versioning 的 RustFS/S3 bucket 及精确 CORS 规则。
- 持久化 SQLite 与 checkpoint 存储卷。
- 生产 secrets 的部署平台注入。
- `/console/`、`/api/v1/` 等同源路由策略。

当前 SQLite、checkpoint 文件、Artifact/VirtualAccount Catalog 快照和进程内 Request-ID cache 只适合单实例运行，不能直接水平扩容。
