# Credits 与 Hint

Credits 是玩家持久化的货币状态，当前仅有 VTB。`player_credits` 为每位玩家保存一行 `vtb`、单调 `version` 和更新时间；VTB 必须为非负整数。新玩家注册和 `0009_player_credits_and_hints` 迁移都会创建初始零余额。

`CreditInterface` 是 VTB 增减的唯一入口。模块调用 `player.credits.grant_vtb(amount)` 发放 VTB，购买系统调用 `player.credits.try_spend_vtb(amount)` 扣费。两者均在当前命令事务中执行条件 SQL 更新，不能自行提交 Session；余额不足会抛出异常，使外层事务回滚。

Hint 是模块在启动期向 `HintRegistry` 注册的静态内容定义：`stable_id`、`FileReference` source、下载名、`HintDisplayParams`、VTB 价格与可选同步 access rule。公开 `hint_id` 由 stable ID 计算为 `h1_` HMAC，不直接暴露 stable ID。`HintDisplayParams` 使用 `title`、非剧透 `teaser`、语义 `icon` 与 `sort_order`，不与文件节点的 `NodeDisplayParams` 混用。

`player_hint_disclosures` 使用 `(player_id, hint_stable_id)` 主键保存已购买资格和 `disclosed_at`。它不保存价格、正文、模板版本或 Request-ID；玩家始终读取当前 Catalog 中的最新对象内容。删除 Hint 定义会使已购买玩家也不能再读取该提示。

Hint 与 FileRegistry 的静态 sources 在启动期合并后单次交给 `StaticAssetPublisher`。发布器将本地文件上传或复用私有 RustFS/S3 对象；bucket versioning 已停用，`HintCatalog` 持有由应用摘要和固定 key 描述的 `ObjectReference`。不能分别物化 File 与 Hint sources，否则发布器会将另一集合的 source 标记为 retired。

`HintService` 在命令事务内先 claim disclosure，再调用 CreditInterface 条件扣费；余额不足会回滚 claim。同一提示的并发购买由 disclosure 主键去重，不会重复扣费；不同提示竞争有限余额时，条件更新保证余额不会为负。`Request-ID` 仍由命令执行器的进程内 TTLCache 处理，不作为 Hint 的持久化字段。

Hint content token 直接使用玩家无关的计算 Hint version（`hv1_`），该 version 绑定 stable ID、source SHA-256、媒体类型、下载名、展示、价格与 access rule callback ID。请求 content URL 时仍必须校验当前玩家的 disclosure 与 access rule。对象或 Hint 定义变化会使旧 token 失效并返回 `412`。
