# Entity-Editor-Random-Panel Specification

## Purpose

提供随机生成工具面板，支持常见格式的随机字符串生成和基于输入数据的变换，帮助用户快速填充测试数据或实体标识符。

## Requirements

### Requirement: 纯随机生成

系统 SHALL 支持 UUID v4、kebab-case、snake_case、`[a-zA-Z0-9]` 四种纯随机生成类型。kebab-case 和 snake_case SHALL 可配置段数与每段长度；`[a-zA-Z0-9]` SHALL 可配置总长度。

#### Scenario: 生成 UUID v4

- **WHEN** 用户选择 UUID v4 类型并点击生成
- **THEN** 输出符合 RFC 4122 v4 格式的 UUID 字符串

#### Scenario: 生成 kebab-case

- **WHEN** 用户选择 kebab-case、段数 2、每段长度 3 并点击生成
- **THEN** 输出形如 `"ab-cd"` 的小写字母+数字段，段间以 `-` 分隔，每段首字符为字母

#### Scenario: 生成随机字母数字

- **WHEN** 用户选择随机字母数字、长度 16 并点击生成
- **THEN** 输出 16 位 `[a-zA-Z0-9]` 字符

### Requirement: 基于输入数据的变换

系统 SHALL 支持对用户输入的原始数据计算 SHA-256 hex 摘要、标准 Base64 编码、UUID v5 确定性 UUID。

#### Scenario: SHA-256 生成

- **WHEN** 用户输入 `"hello"` 并点击 SHA-256
- **THEN** 输出 `"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"`

#### Scenario: 相同输入生成相同 UUID v5

- **WHEN** 用户两次输入相同文本并点击 UUID v5
- **THEN** 两次输出相同

### Requirement: 复制结果

输出区域 SHALL 提供一键复制到剪贴板功能，复制后按钮显示"已复制"反馈持续 2 秒。

#### Scenario: 复制结果

- **WHEN** 用户点击复制按钮
- **THEN** 结果文本被复制到剪贴板，按钮显示"已复制"
