# 谜题出题后端（question-server）临时设计讨论稿

> 状态：设计讨论稿，尚未实现。
>
> 本文整理前端出题器（`desktop_designer`）对后端的完整需求，用于后续 OpenSpec proposal、design 和实现任务的输入。
> 完整规格草案已放在 `openspec/changes/2026-08-06-question-design-backend/`（proposal + 4 份能力 spec + 任务拆分），实现时请以该目录为权威输入，本稿作为上下文说明。
>
> 感谢后端同学接手，有任何边界不清晰的地方欢迎随时对齐。

## 1. 背景与现状

前端侧已经完成的铺垫：

- 游戏端（desktop）有通用"题目窗口"播放器（`PuzzlePlayer`），支持三种题型：**单选（2~10 选项）／多选（2~10 选项）／填空（多空）**，题面为富媒体块（文本／图片／视频／富文本）。
- 出题器前端（`desktop_designer`）已实现：登录注册、出题、编辑、删除、测试预览、审核（通过／驳回）、发布导出。
- 出题器目前是**纯前端 localStorage 模拟**（账号、题库、审核状态都在浏览器里），这是当前最大的缺口：数据随浏览器丢失、多人协作不可能、答案明文暴露、无法作为正式结算依据。

当前代码中没有 Question 相关的 Registry、Service、持久化模型或 HTTP Router，需要后端补齐。

## 2. 目标范围

本阶段需要实现：

1. 出题者账号体系（注册即出题者；管理员账号由种子流程创建）。
2. 题目 CRUD（创建、读取、编辑、删除）与生命周期状态机。
3. 提交审核与管理员审核（通过／驳回，可填备注）。
4. 公开只读的"已发布题目"接口，供游戏端自动发现。
5. 作者可对题目提交答案做服务端校验（测试，不落库）。

明确不包含：

- 不修改现有 `mythos/` 主仓库的行为（建议以独立副本 `question-server/` 承载，见 §8）。
- 不实现"答案不可见"的服务端校验模式（当前与游戏端单机本地校验模式一致，答案随发布接口下发；如未来要求收紧，另开变更）。
- 不引入消息队列、后台调度器或新通用回调路由。

## 3. 角色与权限

| 角色 | 能力 |
|---|---|
| `author`（出题者，默认） | 注册即获得；只能操作**自己的**题目（增删改查、提交审核、测试） |
| `admin`（管理员） | 查看**全部**题目、任意删除、执行审核（通过／驳回） |

建议：`PlayerRecord` 增加 `role` 列（默认 `author`）；首个管理员由 CLI（环境变量 `ADMIN_USERNAME/ADMIN_PASSWORD`）幂等创建。

## 4. 题目生命周期

```text
draft ──submit──▶ pending ──review(approve)──▶ approved（写入 publishedAt）
   ▲                │
   │                └──review(reject)──▶ rejected（记录 reviewNote）
   │                                          │
   └──────────────────────────────────────────┘
```

关键规则：

- 只有 `pending` 状态可审核；只有 `approved` 会出现在发布接口。
- **编辑已发布题目会自动重置为 `pending`**（需重新审核），并清空 `publishedAt`。
- 已发布题目不可重复提交审核。

## 5. 数据契约（PuzzleDefinition）

与前端出题器／游戏播放器完全对齐，前后端共用：

```ts
type ContentBlock =
  | { type: 'text'; text: string; variant?: 'normal' | 'code' }
  | { type: 'image'; url: string; alt?: string; caption?: string }
  | { type: 'video'; url: string; caption?: string }
  | { type: 'rich'; html: string }        // 富文本，审核后渲染

type QuestionType = 'single' | 'multi' | 'fill'

interface PuzzleDefinition {
  id: string
  title: string
  blocks: ContentBlock[]
  type: QuestionType
  options?: { text: string; correct?: boolean }[]  // 选择题 2~10 项
  fillAnswers?: string[]                            // 填空多空
  hints?: string[]
  explanation?: string
}
```

服务端存储建议：`blocks` / `options` / `fill_answers` / `hints` 用 JSON 列，`type` 用枚举列，校验（如选项数量 2~10）由 schema 层负责。

## 6. HTTP API（前缀 `/api/v1/questions`）

建议复用现有 JWT 认证（`get_current_player`）与事务管线；写端点按当前命令约定携带 `Request-ID`：

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/questions` | 创建草稿 | author |
| GET | `/questions/mine` | 我的题目 | author |
| GET | `/questions/all` | 全部题目 | admin |
| GET | `/questions/{id}` | 单题详情 | 本人或 admin |
| PUT | `/questions/{id}` | 编辑（approved 编辑→pending） | 本人 |
| DELETE | `/questions/{id}` | 删除 | 本人；admin 任意 |
| POST | `/questions/{id}/submit` | 提交审核 → pending | 本人 |
| POST | `/questions/{id}/review` | 审核 approve/reject + note | admin |
| POST | `/questions/{id}/test` | 答案校验（不落库） | 本人 |
| GET | `/questions/published` | **公开只读**，仅 approved，供游戏自动发现 | 匿名 |

发布接口响应格式：

```json
{
  "version": 1,
  "questions": [ /* PuzzleDefinition[]，剔除作者/审核备注/时间戳等管理字段 */ ]
}
```

## 7. 持久化模型（建议）

```text
PlayerRecord            （新增 role 列，默认 author）
    id UUID PK
    username ...
    role        'author' | 'admin'

Question
    id          UUID PK
    author_id   UUID FK -> players.id
    title       String
    blocks      JSON
    type        'single' | 'multi' | 'fill'
    options     JSON NULL
    fill_answers JSON NULL
    hints       JSON NULL
    explanation String NULL
    status      'draft' | 'pending' | 'approved' | 'rejected'
    review_note String NULL
    created_at / updated_at / published_at DateTime
```

## 8. 建议实现路线

仓库已有成熟的游戏后端 `mythos/`（FastAPI + SQLAlchemy + Alembic + JWT/refresh cookie + RFC 9457 错误格式 + 请求幂等/重放保护管线）。为避免破坏现有实现，**建议整体复制 `mythos/` 为独立副本 `question-server/`**（包名保持 `mythos` 避免大规模改名），在副本上：

1. 迁移新增 `role` 列与 `Question` 表。
2. 按现有 registry 模式新增 questions 定义（内容型，存储走 DB）。
3. 新增 `services/questions` 与 `endpoints/questions.py`（挂载进 `endpoints/router.py`）。
4. 复用 `EndpointCommandExecutor` 事务管线与 `RequestCache`（幂等与重放保护）。
5. 补充测试与 `docs/api/questions.md`。

## 9. 验证重点

实现时至少覆盖：

1. author 只能看到／编辑自己的题目；admin 全量可见并可任意删除、审核。
2. 状态机：draft→pending→approved|rejected；approved 编辑后回到 pending。
3. `GET /published` 只返回 approved 且剔除管理字段；匿名可访问。
4. 选项数量 2~10 越界返回 `422`；越权返回 `403`；状态非法返回 `409`。
5. 写端点遵循 `Request-ID` 幂等（重放返回缓存而非重复执行）。
6. 端到端：注册 author → 建题 → 提交审核 → admin 审核通过 → `/published` 可见。

## 10. 相关材料

- 本稿来源：`openspec/changes/2026-08-06-question-design-backend/`（proposal.md、specs/、tasks.md）
- 前端对接点：`desktop_designer/src/composables/useQuestionApi.ts`（函数签名与本稿端点一一对应，后端就绪后前端只改该文件内部实现）
- 游戏端自动发现开关：`desktop/src/config/api.ts` 的 `USE_PUBLISHED_QUESTIONS`（已预留，联调时告知地址即可）

有疑问随时沟通，再次感谢！
