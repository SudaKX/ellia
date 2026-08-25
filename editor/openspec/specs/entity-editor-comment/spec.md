# Entity-Editor-Comment Specification

## Purpose

为实体提供可持久化的多行注释字段，支持卡片摘要展示、ActionBar 完整查看、协作编辑与锁定状态提示。

## Requirements

### Requirement: 实体注释字段

系统 SHALL 为所有实体提供 `comment` 文本字段。`comment` 允许任意多行文本，不参与格式校验。实体卡片 SHALL 展示 `comment` 的第一行（按 `\n` 分割）；无注释时卡片不显示注释区。编辑器 ActionBar SHALL 在第二行以 surface 容器完整展示注释，无注释时使用虚线边框与半透明配色。

#### Scenario: 创建带注释的实体

- **WHEN** 用户在创建实体面板的注释区域输入多行文本并提交
- **THEN** 实体创建成功且 `comment` 保存为该文本

#### Scenario: 实体卡片展示注释首行

- **WHEN** 实体 `comment` 为 `"第一行\n第二行"` 且在实体卡片上渲染
- **THEN** 卡片仅显示 `"第一行"`

#### Scenario: 无注释的卡片

- **WHEN** 实体 `comment` 为空字符串
- **THEN** 卡片不显示注释区

#### Scenario: ActionBar 注释区样式

- **WHEN** 实体 `comment` 为空时在 ActionBar 渲染注释区
- **THEN** 注释区使用虚线边框和半透明配色；有注释时使用实线边框和正常配色

### Requirement: 注释编辑

系统 SHALL 支持在编辑器 ActionBar 点击"编辑"/"添加"按钮弹出模态对话框编辑注释。编辑需要先获取 `@comment:` 字段锁；被他人锁定时展示覆盖层并禁止编辑。

#### Scenario: 编辑注释

- **WHEN** 用户点击"编辑"按钮、输入新注释并保存
- **THEN** 注释被更新，ActionBar 与实体卡片同步展示新注释

#### Scenario: 他人锁定注释时不可编辑

- **WHEN** 连接 B 持有该实体 `@comment:` 锁
- **THEN** 连接 A 的编辑按钮禁用，注释区显示覆盖层
