## MODIFIED Requirements

### Requirement: 编辑中节点提示

所有正在被编辑的 file-tree 节点卡片 SHALL 显示 `block: false` 的 `LockOverlay`，展示锁定者用户名，不区分锁持有者。系统 SHALL NOT 再使用 `--app-warning` 描边或降低亮度 filter 标记这些卡片；该覆盖层 SHALL 不阻挡鼠标事件、不改变光标。

#### Scenario: 他人编辑节点时显示非阻塞覆盖层

- **WHEN** 其他用户持有某个树节点路径的锁
- **THEN** 该节点卡片显示 `LockOverlay` 用户名标签，且不阻挡点击、不降低亮度

#### Scenario: 自己编辑节点时同样显示覆盖层

- **WHEN** 当前用户持有某个树节点路径的锁
- **THEN** 该节点卡片同样显示 `LockOverlay` 用户名标签，且不阻挡点击
