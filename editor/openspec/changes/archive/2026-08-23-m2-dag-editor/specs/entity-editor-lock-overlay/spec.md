## MODIFIED Requirements

### Requirement: LockOverlay 可复用组件

系统 SHALL 提供 `LockOverlay.vue` 独立组件，接受 `username` prop 和可选 `block` prop。`block` 默认 SHALL 为 `true`：此时覆盖层 SHALL 位于容器绝对定位、不可点击穿透、带半透明 backdrop，并显示持有者用户名标签。`block: false` 时，覆盖层 SHALL 仍显示用户名标签，但 SHALL NOT 使用 backdrop 降低亮度、SHALL NOT 阻挡鼠标事件，且 SHALL NOT 改变光标样式。

#### Scenario: 渲染覆盖层

- **WHEN** 某字段被他人锁定且容器渲染 LockOverlay
- **THEN** 容器上显示半透明覆盖层和底部右侧持有者用户名标签

#### Scenario: 覆盖层不可交互

- **WHEN** `block` 为 `true` 且覆盖层存在时点击容器
- **THEN** 点击不触发容器下层的按钮或输入事件

#### Scenario: 非阻塞覆盖层不拦截事件

- **WHEN** `block` 为 `false` 且覆盖层存在时点击容器
- **THEN** 点击可穿透到容器下层，且覆盖层不显示降低亮度效果
