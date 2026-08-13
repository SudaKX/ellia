## ADDED Requirements

### Requirement: Example SHALL register purchasable Hint content

在演示配置下，example 模块 SHALL 注册三个静态 Hint：两个登录后可见的 Hint，价格分别为 2 和 3 VTB；一个在 `example.completed` 解锁后可见、价格为 5 VTB 的 Hint。Hint 正文 SHALL 使用 example 模块 `assets/hints/` 下的静态源文件，并 SHALL 通过现有 HintRegistry 和静态资源物化流程发布。

#### Scenario: New player sees public example Hints

- **WHEN** 新玩家完成注册并请求 `GET /api/v1/hints`
- **THEN** 响应 SHALL 返回两个可见 Hint，包含公开 `hint_id`、展示信息、价格、媒体类型、大小和 `disclosed: false`，且不暴露 stable ID 或正文

#### Scenario: Completed player sees gated example Hint

- **WHEN** 玩家解锁 `example.completed` 后重新请求 `GET /api/v1/hints`
- **THEN** 响应 SHALL 额外包含价格为 5 VTB 的 gated Hint

### Requirement: Demo players SHALL receive a finite initial VTB balance

在 development/test 演示配置下，玩家首次 Construct SHALL 获得 5 VTB；同一玩家后续登录或刷新 SHALL 不重复获得。production 配置 SHALL 不因该演示能力自动发放 VTB。

#### Scenario: New demo player receives initial balance

- **WHEN** 玩家在 development/test 演示配置下注册
- **THEN** 玩家余额 SHALL 为 5 VTB，且余额变化 SHALL 在注册事务中完成

#### Scenario: Repeated login does not grant more VTB

- **WHEN** 已 Construct 的玩家重复登录或刷新访问
- **THEN** 玩家 VTB SHALL 保持原值，不得再次增加 5 VTB

### Requirement: Example UI SHALL present current VTB and available Hints

玩家认证后，`/example/` SHALL 加载当前 VTB 余额和当前可见 Hint 列表。每个 Hint SHALL 展示标题、teaser、VTB 价格、媒体类型、大小和购买状态；页面 SHALL 在认证、Virtual Account 切换、答案提交成功和全局刷新后重新加载这些数据。

#### Scenario: Authenticated page loads Hint workspace

- **WHEN** 玩家完成注册或登录
- **THEN** 页面 SHALL 请求余额和 Hint 列表，并显示当前 VTB 余额及至少一个可购买 Hint

#### Scenario: Workspace refresh reflects server state

- **WHEN** 玩家点击全局 Refresh 或完成会改变 Hint access rule 的答案提交
- **THEN** 页面 SHALL 重新读取余额和 Hint 列表，并反映服务器返回的可见性、购买状态和余额

### Requirement: Player SHALL be able to purchase a Hint from the Example UI

每次点击可购买 Hint 的 Purchase 控件，页面 SHALL 生成新的 UUID `Request-ID` 并调用对应的 `POST /api/v1/hints/{hint_id}/disclose`。购买请求进行中 SHALL 只锁定当前 Hint 的控件；成功后 SHALL 标记 Hint 为已购买并刷新余额。

#### Scenario: Successful Hint purchase

- **WHEN** 玩家余额不少于 Hint 价格并点击 Purchase
- **THEN** 页面 SHALL 收到 200 响应，将 Hint 标记为已购买，显示 content token 可用状态，并显示扣费后的余额

#### Scenario: Repeated purchase is idempotent

- **WHEN** 玩家再次请求已经购买的 Hint
- **THEN** 页面 SHALL 接受后端的幂等成功响应，Hint 仍保持已购买，余额不得再次扣除

### Requirement: Example UI SHALL expose insufficient-credit behavior

当玩家余额不足时，页面 SHALL 允许发出实际购买请求，而不是仅根据本地余额禁用控件；收到 `409 insufficient-credits` 后 SHALL 显示余额不足错误，且不得把 Hint 标记为已购买。

#### Scenario: Purchase fails without enough VTB

- **WHEN** 玩家点击价格高于当前余额的 Hint Purchase 控件
- **THEN** 页面 SHALL 请求 `/disclose`，显示余额不足错误，余额和 disclosure 状态 SHALL 保持不变

### Requirement: Player SHALL be able to reveal purchased Hint content

已购买 Hint SHALL 提供 Reveal 控件。页面 SHALL 使用当前 content token 请求 `/api/v1/hints/{hint_id}/{content_token}/content-url`，再直接读取返回的预签名对象 URL 并在预览区域展示正文。预签名 URL SHALL 只保存在运行时内存，不得写入 localStorage 或其他持久化前端状态。

#### Scenario: Reveal purchased text Hint

- **WHEN** 玩家点击已购买 Hint 的 Reveal 控件
- **THEN** 页面 SHALL 获取预签名 URL、读取对象内容，并在 Hint 预览区域展示正文

#### Scenario: Stale Hint content is refreshed

- **WHEN** content-url 请求返回 `412 hint-content-version-mismatch`
- **THEN** 页面 SHALL 刷新 Hint 元数据并最多重新尝试一次，之后显示明确的失败状态

### Requirement: Example UI SHALL retain existing runtime workflows

Hint 面板的加入 SHALL 不改变现有认证、Virtual Account、文件树、文件预览、Progress、Scripts、Validation 和 Recovery Console 的行为；Hint 请求错误 SHALL 继续记录在现有 Requests 区域。

#### Scenario: Existing file and answer flow remains usable

- **WHEN** 玩家在 Hint 面板存在时登录 Virtual Account、打开文件或提交答案
- **THEN** 原有流程 SHALL 继续完成，Hint 状态刷新不得清空或破坏文件、Progress 和答案状态
