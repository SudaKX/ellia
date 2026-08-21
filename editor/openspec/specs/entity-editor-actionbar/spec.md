# Entity-Editor-Actionbar Specification

## Purpose

增强编辑器操作栏，提供两行布局、resource_id 编辑和注释展示，提升实体信息的可读性与可编辑性。

## Requirements

### Requirement: ActionBar 两行布局

编辑器 ActionBar SHALL 分为两行。第一行横向 flex，包含 resource_id、kind、`v{version} · r{revision}` 标识、版本回退按钮和删除按钮。第二行为注释展示 surface，完整展示注释并提供编辑按钮。

#### Scenario: 渲染两行布局

- **WHEN** 打开一个实体
- **THEN** ActionBar 显示两行：第一行实体元数据与操作按钮，第二行注释 surface

### Requirement: resource_id 编辑

`resource_id` SHALL 以可点击按钮形式展示。点击后弹出模态对话框，仅允许修改 `:` 之后的 id 部分，命名空间前缀不可更改。编辑前需获取 `@resource_id:` 锁；被他人锁定时展示覆盖层。

#### Scenario: 修改 id 部分

- **WHEN** 用户点击 resource_id 按钮、修改 id 部分并保存
- **THEN** resource_id 被更新为新的 `namespace:id`，标签页标题同步更新

#### Scenario: 他人锁定 resource_id 时禁止编辑

- **WHEN** 连接 B 持有该实体 `@resource_id:` 锁
- **THEN** 连接 A 的 resource_id 按钮禁用，展示覆盖层

### Requirement: 标签页标题同步

打开实体的标签页标题 SHALL 始终显示实体当前的 `resource_id`。当 `resource_id` 被修改时，所有已打开该实体的标签页标题 SHALL 自动更新。

#### Scenario: 修改 resource_id 后标签同步

- **WHEN** 实体 resource_id 从 `hint:a` 改为 `hint:b` 且该实体标签已打开
- **THEN** 标签标题立即变为 `hint:b`
