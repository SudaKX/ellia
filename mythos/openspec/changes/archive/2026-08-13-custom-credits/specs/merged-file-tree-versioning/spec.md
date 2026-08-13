# Merged File Tree Versioning

## Purpose

定义启动期合并文件树、Artifact Slot 路径映射、资源与玩家状态版本、动态文件授权及请求级缓存失效行为。

## ADDED Requirements

### Requirement: Credits interface version SHALL cover all credit balances

作为文件 access_rule 可能依赖的接口，`credits.version` SHALL 表示玩家级聚合状态版本：任何 credit 余额的成功写入（发放、扣费、行创建、reconciliation 删除）SHALL 递增该版本。任何可能改变依赖 CREDITS 的 access_rule 结果的余额变化都 SHALL 使 `pft4_` 动态树版本变化。

#### Scenario: Custom credit change invalidates dynamic tree version

- **WHEN** 某文件 access_rule 声明 CREDITS 依赖，且任意已注册 credit（含自定义 credit）的余额通过合法写入路径变化
- **THEN** `/files/d/version` SHALL 返回新的 `pft4_`

#### Scenario: Aggregate version never regresses

- **WHEN** reconciliation 删除孤儿余额行或任一 credit 余额写入成功
- **THEN** `credits.version` SHALL 不小于写入前的值，树版本不得回退到旧值
