## 1. Registry 与稳定 ID

- [x] 1.1 新增 AchievementDefinition、AchievementRegistry 和 AchievementCatalog，校验 stable_id、callback 签名、meta 序列化和 Player Interface 依赖
- [x] 1.2 将 AchievementRegistry 接入 RegistryBundle、freeze 流程和 RuntimeCatalogs
- [x] 1.3 实现基于现有 file-ID signing key、`achievement:v1` 域和 `a1_` 前缀的 public ID codec
- [x] 1.4 为 puzzles 注册入口提供 Achievement 注册支持，并使用框架级测试注册项验证 freeze 行为，不修改具体 puzzle 内容

## 2. 持久化与 Player Interface

- [x] 2.1 新增 PlayerAchievementState ORM 模型和 `player_achievement_states` 数据库迁移
- [x] 2.2 新增 PlayerInterfaces.ACHIEVEMENTS、Player.achievements 和 PlayerLoader.load_achievements()
- [x] 2.3 实现 AchievementInterface 的 earned、claimed_at、幂等状态更新和只读查询
- [x] 2.4 增加玩家删除级联、复合主键和状态查询测试

## 3. Achievement Service 与 fallback

- [x] 3.1 实现事务中立 AchievementService，支持活动 Catalog 与玩家状态合并查询
- [x] 3.2 实现启动期 data-only fallback 注册、冲突校验和已删除成就展示状态
- [x] 3.3 实现 condition 批次评估、earned record 幂等创建和 immediate effect 计划
- [x] 3.4 实现 Effect 批次执行、claimed_at 更新、失败整体回滚和已达成状态保留
- [x] 3.5 为 active、locked、available、claimed、deleted、missing-fallback 状态增加服务层测试

## 4. CommandExecutor 与事务边界

- [x] 4.1 新增 AchievementCommandExecutor，组织独立 Check transaction 和 Effect transaction
- [x] 4.2 将普通写端点的 Achievement 检查接入 Operation 提交后的独立 C/D 流程，不改变 Task/Auth 边界
- [x] 4.3 实现 C/D 失败 warning 聚合、原始 Operation 响应保留和 RequestCache 完成时机
- [x] 4.4 实现 check/claim 的 Request-ID replay、并发 lease 和 deleted achievement claim 拒绝行为
- [x] 4.5 确认 Auth Workflow 与 `/tasks/process` 不执行 Achievement，并覆盖普通写端点不重复执行检查

## 5. HTTP API

- [x] 5.1 新增 `GET /api/v1/achievement`，返回活动 Catalog、玩家状态和 fallback 历史成就
- [x] 5.2 新增 `POST /api/v1/achievement/check`，返回检查结果和安全 warning
- [x] 5.3 新增 `POST /api/v1/achievement/claim/{public_id}`，实现 active available 成就领取和幂等行为
- [x] 5.4 增加 API 鉴权、Request-ID、ProblemDetails、warning 响应和 replay 测试

## 6. 文档与验证

- [x] 6.1 更新主 OpenSpec 的 command-execution-boundaries Achievement transaction requirement
- [x] 6.2 新增或同步 Achievement API、事务、fallback 和 puzzles 注册文档
- [x] 6.3 运行迁移、Achievement 聚焦测试、完整后端测试和 OpenSpec strict validation
- [x] 6.4 检查启动 freeze、HMAC public ID、普通写命令 C/D 失败和 RequestCache replay 的端到端行为
