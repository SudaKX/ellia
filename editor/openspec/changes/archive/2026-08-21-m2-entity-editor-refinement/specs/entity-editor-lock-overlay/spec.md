## Purpose

将字段编辑时的锁定覆盖层提取为独立可复用组件，供表单字段、ActionBar 的 resource_id 和注释区共用。

## ADDED Requirements

### Requirement: LockOverlay 可复用组件

系统 SHALL 提供 `LockOverlay.vue` 独立组件，接受 `username` prop，渲染覆盖层并显示持有者用户名标签。覆盖层 SHALL 位于容器绝对定位、不可点击穿透、带半透明 backdrop。

#### Scenario: 渲染覆盖层
- **WHEN** 某字段被他人锁定且容器渲染 LockOverlay
- **THEN** 容器上显示半透明覆盖层和底部右侧持有者用户名标签

#### Scenario: 覆盖层不可交互
- **WHEN** 覆盖层存在时点击容器
- **THEN** 点击不触发容器下层的按钮或输入事件