# Entity-Editor-Validation Specification

## Purpose

定义实体字段格式校验、formSpec format 扩展机制以及 validation_id 格式对齐，确保编辑期的字段值符合预期格式。

## Requirements

### Requirement: FieldSpec 支持 format 校验

`FieldSpec` SHALL 支持 `format` 可选字段，仅 `type=string` 时有效，值为正则表达式字符串。`FieldEditDialog` SHALL 在输入时对 `format` 字段执行即时校验，不匹配时禁用确认按钮并显示错误提示。

#### Scenario: format 不匹配时确认按钮禁用

- **WHEN** 字段 `format` 为 `"^[a-z]+$"` 且用户输入 `"ABC"`
- **THEN** 编辑对话框显示格式错误提示，确认按钮不可点击

#### Scenario: 空字符串不匹配 format

- **WHEN** 必填字段有 `format` 且用户输入为空
- **THEN** 空字符串不匹配正则，确认按钮禁用

### Requirement: validation_id 格式对齐

`validation.validation_id` 的 `format` SHALL 为 `^[a-zA-Z0-9_-]{1,64}$`，允许大写字母、下划线、连字符，长度 1～64。服务端 `validateStateShape` SHALL 接受空字符串作为占位值，仅拒绝 `undefined`/`null`。

#### Scenario: 合法 validation_id 可保存

- **WHEN** 用户输入 `"My-Validation_1"` 并保存
- **THEN** 格式校验通过，确认按钮可用

#### Scenario: 超长 validation_id 被拒绝

- **WHEN** 用户输入 65 个字符的 validation_id
- **THEN** 格式校验不通过，确认按钮禁用
