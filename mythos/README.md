# Mythos

Mythos 是 Ellia 在线解谜活动的 FastAPI 后端。它负责平台玩家认证、玩家进度、虚拟文件、谜题验证、ElLInA 演出和活动统计；前端不持有这些领域的权威状态。

后端按“框架 + 谜题模块”组织：框架提供玩家数据服务、全局资源注册服务和固定 API 端点；谜题模块提供文件、演出脚本、验证规则、checkpoint、统计项和端点回调。完整设计见 [docs/design_v1.md](docs/design_v1.md)。

## 当前进度

已完成：

- 建立 `src/mythos` 包结构与领域目录。
- 声明 FastAPI、SQLAlchemy、Alembic、认证和测试基础依赖。
- 提供最小 FastAPI 应用与 `GET /health` 健康检查。
- 建立异步 SQLite 数据库基础设施、初始 Alembic 迁移与玩家认证模型。
- 实现平台注册、登录、JWT 刷新、Refresh Cookie 轮换和登出端点。
- 覆盖健康检查和完整认证生命周期测试。

尚未实现：

- 玩家服务、文件与演出注册服务、模块注册表和回调端点派发。
- 具体谜题模块、前端 API 接入及活动管理统计。

## 本地开发

项目使用根目录的 `.venv` 虚拟环境。安装开发依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install --editable ".\mythos[dev]"
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest mythos/tests
```

首次运行前，将 `.env.example` 复制为 `.env` 并替换认证密钥；随后执行迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic -c mythos/alembic.ini upgrade head
```
