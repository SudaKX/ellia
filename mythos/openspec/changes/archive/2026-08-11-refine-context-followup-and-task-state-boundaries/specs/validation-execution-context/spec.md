## ADDED Requirements

### Requirement: Validation handlers use a domain-neutral context

系统 SHALL 提供 ValidationContext，Validation Handler SHALL 接收 ValidationContext 和 payload，不得接收 HTTP 专用的 CommandContext。ValidationService SHALL 能在没有 Request-ID、ResponseSpec 或 FastAPI 的情况下执行。

#### Scenario: Endpoint invokes validation without leaking CommandContext

- **WHEN** Validation Endpoint 执行一个 Validation Handler
- **THEN** Endpoint SHALL 传入由当前 Player 和 ContextScope 创建的 ValidationContext，Handler SHALL 不需要读取 Request-ID

#### Scenario: Internal workflow invokes validation

- **WHEN** 非 HTTP Workflow 调用 ValidationService
- **THEN** ValidationService SHALL 只要求 Player、ValidationAttempt 和 payload，并可使用 silent ContextScope

### Requirement: Validation rejection has a fixed HTTP conversion

ValidationContext SHALL 提供不接收 HTTP status code 的 `reject(reason, details)`。该方法 SHALL 抛出领域 `ValidationRejected`；Endpoint SHALL 将所有该异常固定转换为 HTTP `409 Conflict`。

#### Scenario: Handler rejects a validation

- **WHEN** Handler 调用 `context.reject(reason, details)`
- **THEN** ValidationService SHALL 中止当前 Handler，且 Endpoint SHALL 返回 HTTP 409 Problem Details

#### Scenario: Handler cannot choose an HTTP status

- **WHEN** Handler 尝试通过 reject 指定任意 HTTP status code
- **THEN** Handler API SHALL 不提供该参数，HTTP status SHALL 仍由 Endpoint 固定为 409

#### Scenario: Other HTTP status has a separate domain error

- **WHEN** Validation 需要表达 404 或 422 等非冲突语义
- **THEN** 系统 SHALL 使用独立领域异常和明确的 Endpoint 映射，不得改变 ValidationRejected 的固定 409 语义

### Requirement: Validation followups are returned as structured results

Validation Handler 发出的 Followup SHALL 通过 ContextScope 收集，并由 ValidationService 的领域结果或调用方读取；ValidationService SHALL NOT 将 Followup 组装为 ResponseSpec 或 HTTP response body。

#### Scenario: HTTP validation converts followups

- **WHEN** Validation Handler 成功并产生结构化 Followup
- **THEN** Endpoint SHALL 将该 Followup 转换为当前命令响应的 JSON followups

#### Scenario: Non-HTTP validation ignores best-effort followups

- **WHEN** 非 HTTP Workflow 使用 silent ContextScope 执行 Validation
- **THEN** Validation SHALL 完成领域操作，且不得要求或生成 HTTP response body
