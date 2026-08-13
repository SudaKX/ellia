# 前后端整合分歧讨论文档 (2026-08-12)

## 1. 概述
本仓库当前存在三个主要子系统：`desktop/` (前端)、`mythos/` (权威后端) 以及 `desktop_designer/` (出题器)。在对整体代码库进行深入分析后，我们发现各子系统在实现上存在若干关键分歧，这些分歧若不解决，将导致项目无法作为一个有机的整体运行。

本文件旨在记录这些分歧，分析其根源，并提出具体的改进方案，供团队决策参考。

---

## 2. 核心分歧清单

### 2.1 鉴权体系不匹配 (Authentication Mismatch)
*   **现状描述**:
    *   **前端 ([useAuth.ts](file:///d:/Afiles/codes/web_game/ellia/desktop/src/composables/useAuth.ts))**: 使用 `localStorage` 存储 Token，并尝试调用 `/api/auth/validate` 和 `/api/auth/token-login`。
    *   **后端 ([authentication.md](file:///d:/Afiles/codes/web_game/ellia/mythos/docs/api/authentication.md))**: 实际端点为 `/api/v1/auth/login` 等，且要求 Access Token 仅在内存持有，Refresh Token 走 `HttpOnly` Cookie。
*   **潜在风险**: 导致登录状态无法恢复，安全性降低，且 API 调用 404。
*   **改进方案**:
    *   修正 [api.ts](file:///d:/Afiles/codes/web_game/ellia/desktop/src/config/api.ts) 中的端点路径。
    *   重构 `useAuth.ts`，将 Token 存入内存变量，并实现 401 自动触发 `/refresh` 的拦截逻辑。

### 2.2 出题器绕过权威验证 (Bypassing Authority)
*   **现状描述**:
    *   **出题器 ([desktop_designer/](file:///d:/Afiles/codes/web_game/ellia/desktop_designer/))**: 拥有独立的 Node.js 后端，审核后的题目通过公开 JSON 接口下发。
    *   **桌面端 ([usePuzzle.ts](file:///d:/Afiles/codes/web_game/ellia/desktop/src/composables/usePuzzle.ts))**: 拉取题目后，在浏览器本地进行答案比对。
*   **潜在风险**: 违背了「前端不持有权威答案」的原则，玩家可通过 F12 绕过解谜；进度无法同步至 `mythos` 的持久化层。
*   **改进方案**:
    *   **方案 A (推荐)**: 出题器发布时将题目注册进 `mythos` 的 `validations` 和 `scripts` Registry，判定逻辑迁至后端。
    *   **方案 B**: 将出题器后端迁移为 `mythos` 的管理端插件，共享统一的认证和数据模型。

### 2.3 虚拟文件系统 (VFS) 割裂
*   **现状描述**:
    *   **前端 ([useFileSystem.ts](file:///d:/Afiles/codes/web_game/ellia/desktop/src/composables/useFileSystem.ts))**: 目前仍在使用静态定义的 `rootTree`。
    *   **后端 ([files.py](file:///d:/Afiles/codes/web_game/ellia/mythos/src/mythos/services/files/service.py))**: 已经实现了一套支持权限、Artifact 和动态合并的 VFS。
*   **潜在风险**: 玩家无法看到由剧情解锁的新文件或 Artifact，游戏无法推进。
*   **改进方案**:
    *   切换 `USE_REAL_API = true`，前端全面接入 `/api/v1/files/d/tree` 等动态端点。
    *   实现 [backend-integration.md](file:///d:/Afiles/codes/web_game/ellia/desktop/docs/backend-integration.md) 中提到的预签名 URL 读取流程。

### 2.4 进度与演出系统孤立
*   **现状描述**:
    *   **前端 ([useStoryDialog.ts](file:///d:/Afiles/codes/web_game/ellia/desktop/src/composables/useStoryDialog.ts))**: 演出脚本目前主要由前端本地驱动。
    *   **后端 ([scripts.md](file:///d:/Afiles/codes/web_game/ellia/mythos/docs/api/scripts.md))**: 设计了基于脚本系统的演出驱动机制。
*   **潜在风险**: 演出的触发无法与后端的进度状态（Node Graph）同步。
*   **改进方案**:
    *   由 `GET /api/v1/scripts` 获取当前玩家可见脚本，前端作为渲染引擎根据脚本 `kind` 执行。

---

## 3. 部署与整合建议 (Orchestration)

目前 `docker/` 和 `kxpage/` 目录尚为空。为了实现项目的「整体感」，建议：
1.  **Nginx 统一网关**: 使用 Nginx 处理 `/kxpage` (入口)、`/console` (FakeOS) 以及 `/api` (后端) 的转发，解决跨域与 Cookie 策略冲突。
2.  **Docker Compose 编排**: 将 `mythos` 镜像与前端构建产物容器化，一键拉起整套环境。

---

## 4. 待决事项 (Decisions Needed)
1.  **出题器归属**: 是保留独立后端作为工具，还是彻底并入 `mythos`？
2.  **API 版本控制**: 统一使用 `/api/v1` 还是允许特定子系统存在差异？
3.  **Mock 策略**: 接入真实后端后，本地 Mock 逻辑是保留还是彻底删除？

---
