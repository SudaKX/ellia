# VirtualAccount 系统

## 注册与玩家状态

模块在启动期向 `VirtualAccountRegistry` 注册 `VirtualAccountTemplate(account_id, display_name, permission, metadata)`。`permission` 是框架原样透传的整数，语义完全由模块定义；模板不保存用户名或密码。需要为新玩家初始化账号时，模块在 Lifecycle Construct 回调中调用 `Player.accounts.issue()`。

`PlayerVirtualAccount` 以 `(player_id, account_id)` 标识已发放账号，保存模块指定的 `username`、规范化用户名、Argon2 密码哈希和成功登录统计。用户名只在玩家范围唯一，密码允许重复。`PlayerVirtualAccountState` 保存当前账号和单调版本，复合外键保证当前账号属于同一玩家。

## Player Interface 与模块

`Player.accounts` 是惰性 Interface。模块在 Construct lifecycle callback 或可写命令中调用 `issue(account_id, username, password)` 发放账号，或调用 `delete(account_id)` 删除账号；读取 `current`、`accounts`、`has()` 和 `is_current()` 获取状态。模块永远不能读取密码哈希或明文密码。

模块访问规则、验证命令和 Artifact 生成器均会加载 Account Interface，因此可读取当前账号及模板权限。Catalog 无法解析的账号在只读路径中 fail closed，表现为未登录且不提供权限。

## HTTP 与协调

`POST /api/v1/vac/login` 接受 `username`、`password` 和 `Request-ID`，登录成功后更新当前账号。`POST /api/v1/vac/logout` 清空当前账号。两个端点都使用平台 Bearer Token，不签发 VirtualAccount 专属令牌。账号不存在、已退休或密码错误均返回相同的 `401`。

启动期 `AccountReconciliationRunner` 将冻结 Catalog 与 SQL 中现有的 `account_id` 对比，删除已不在 Catalog 中的玩家账号，并清空相应当前账号。每次成功协调后原子写入本地 Catalog 快照；快照损坏会阻止启动。若 Catalog 为空但 SQL 中仍有账号，默认阻止启动，除非显式允许全局账号退休。
