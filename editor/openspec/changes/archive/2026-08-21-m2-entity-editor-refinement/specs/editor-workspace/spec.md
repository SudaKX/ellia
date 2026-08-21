## Purpose

定义编辑器工作区的 UI 行为，包括 ActionBar 两行布局、resource_id 编辑、注释编辑、LockOverlay 复用和删除实体提示，作为多人协作编辑器的操作栏与反馈层。

## ADDED Requirements

### Requirement: ActionBar 两行布局

编辑器 ActionBar SHALL 分为两行。第一行横向 flex 包含 resource_id（可点击）、kind、`v{version} · r{revision}`、版本回退按钮和删除按钮。第二行为注释 surface，完整展示注释并提供"编辑"/"添加"按钮。

#### Scenario: 打开实体显示两行
- **WHEN** 用户打开任意实体
- **THEN** ActionBar 显示两行，第一行实体元数据与操作按钮，第二行注释区

### Requirement: resource_id 编辑

resource_id SHALL 以可点击按钮形式展示，点击后弹出模态对话框，仅允许修改 `:` 之后的 id 部分，命名空间前缀不可更改。编辑前 SHALL 获取 `@resource_id:` 锁。

#### Scenario: 修改 id 部分
- **WHEN** 用户点击 resource_id、修改 id 部分并保存
- **THEN** resource_id 更新，标签页标题同步更新

#### Scenario: 他人锁定时禁止编辑
- **WHEN** 他人持有 `@resource_id:` 锁
- **THEN** 当前用户按钮禁用并显示覆盖层

### Requirement: 标签页标题同步

标签页标题 SHALL 始终反映实体当前 `resource_id`，修改后自动更新。

#### Scenario: 修改后标题同步
- **WHEN** 实体 resource_id 由 `hint:a` 改为 `hint:b` 且标签已打开
- **THEN** 标签标题变为 `hint:b`

### Requirement: 注释展示与编辑

ActionBar 第二行 SHALL 展示完整多行注释。无注释时 surface 使用虚线边框和半透明配色。点击"编辑"/"添加"弹出模态对话框，编辑需获取 `@comment:` 锁。

#### Scenario: 有注释展示
- **WHEN** 实体有注释
- **THEN** ActionBar 完整展示多行注释，无高度限制

#### Scenario: 无注释样式
- **WHEN** 实体注释为空
- **THEN** 注释 surface 使用虚线边框、半透明配色，显示"无注释"

### Requirement: LockOverlay 组件复用

系统 SHALL 提供 `LockOverlay` 独立组件，供 resource_id 按钮和注释 surface 在他人锁定时展示覆盖层。

#### Scenario: resource_id 被锁定显示覆盖层
- **WHEN** 他人持有 `@resource_id:` 锁
- **THEN** resource_id 按钮上显示 LockOverlay，展示持有者用户名

#### Scenario: 注释被锁定显示覆盖层
- **WHEN** 他人持有 `@comment:` 锁
- **THEN** 注释 surface 上显示 LockOverlay

### Requirement: 删除实体 UI 提示

收到 `deleted` 消息后，系统 SHALL 记录被删除实体 id；对已打开该实体的标签，编辑器区域 SHALL 显示"实体已被删除"覆盖层并提供关闭按钮。

#### Scenario: 被删除实体显示提示
- **WHEN** 他人删除当前打开的实体
- **THEN** 编辑器区域显示删除覆盖层

#### Scenario: 关闭已删除标签
- **WHEN** 用户点击删除覆盖层的关闭按钮
- **THEN** 标签关闭，回到空状态

### Requirement: 回退错误模态框

版本回退失败（包括 `HISTORY_EMPTY`）SHALL 通过模态对话框展示错误信息，不在 ActionBar 内联插入文本提示。

#### Scenario: 回退到头显示模态框
- **WHEN** 实体无历史快照时用户点击版本回退
- **THEN** 弹出模态对话框显示错误信息