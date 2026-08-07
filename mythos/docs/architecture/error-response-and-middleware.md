# 错误响应与中间件路径

## 范围与响应格式

Mythos 的 API 错误响应使用 RFC 9457 `application/problem+json`。所有 `4xx` 和 `5xx` 均以 Problem Details 作为整个响应 body，不使用命令成功响应的 `{content, followups}` 包装。字段定义、Problem Type 和客户端恢复规则见 [错误与缓存](../api/errors-and-caching.md)。

```json
{
  "type": "https://api.example.com/problems/access-token-invalid",
  "title": "Invalid access token",
  "status": 401,
  "detail": "The access token is invalid or expired.",
  "instance": "urn:uuid:..."
}
```

`type` 由 `MYTHOS_PROBLEM_TYPE_BASE_URL` 与 Problem Type 后缀组成。`detail` 只用于向用户说明本次问题，客户端不能解析它做控制流；机器逻辑使用完整 `type` URI。`instance` 是服务端生成的错误关联 ID。Problem Details 默认有 `Cache-Control: no-store`，但序列化器会保留调用方显式提供的响应 Header。框架不会主动添加 `WWW-Authenticate`，但会保留调用方显式提供的该 Header。

## 请求路径

应用没有使用 `app.add_middleware()` 注册自定义中间件。FastAPI/Starlette 建立的请求路径为：

```text
HTTP request
  -> ServerErrorMiddleware
  -> ExceptionMiddleware
  -> AsyncExitStackMiddleware
  -> APIRouter / FastAPI dependency resolution
  -> endpoint, Service, CommandTransactionExecutor
  -> success JSON response or Problem Details response
```

`AsyncExitStackMiddleware` 管理诸如 `get_session()` 的 yield dependency 生命周期。鉴权、Session、Player Context 和 Request-ID Header 的依赖均在 endpoint handler 执行前解析；因此它们抛出的异常也会进入相同的错误处理链。

## 异常路由

`create_app()` 注册四类全局处理器。`ApiProblem`、`StarletteHTTPException` 和 `RequestValidationError` 由 `ExceptionMiddleware` 分发；兜底的 `Exception` handler 由最外层 `ServerErrorMiddleware` 用于生成 `500`。

```python
application.add_exception_handler(ApiProblem, api_problem_handler)
application.add_exception_handler(StarletteHTTPException, http_exception_handler)
application.add_exception_handler(RequestValidationError, request_validation_exception_handler)
application.add_exception_handler(Exception, unhandled_exception_handler)
```

### 自定义 Exception Handler

| Handler | 捕获输入 | 响应转换 | 特殊行为 |
| --- | --- | --- | --- |
| `api_problem_handler` | 模块、认证依赖或 Router 主动抛出的 `ApiProblem` | 调用 `problem_response()`；type 由 `Settings.problem_type_url()` 生成 | 保留 Problem Type、title、status、detail、instance 与允许的顶层扩展 |
| `http_exception_handler` | 既有 `HTTPException`、路由 `404`、方法不允许等 `StarletteHTTPException` | 将状态、HTTP 状态短语和字符串 detail 转为 `about:blank` Problem Details | 原样保留异常给出的 Header；特殊识别 JSON Body 解析 `400` 并转为 `422 invalid-request` |
| `request_validation_exception_handler` | FastAPI 的 `RequestValidationError` | 返回 `422 invalid-request` | 将 Pydantic `loc` 转为 JSON Pointer；每项写入顶层 `errors: [{pointer, reason}]` |
| `unhandled_exception_handler` | 未被前面处理器捕获的 `Exception` | 返回 `500 internal-error` | 生成 `instance`，按该 ID 记录完整异常堆栈；响应不包含异常类型或堆栈 |

底层序列化入口为 `_problem_details_response()`：

```python
response_headers = dict(headers or {})
response_headers.setdefault("Cache-Control", "no-store")
return JSONResponse(
    status_code=details.status,
    content=details.model_dump(mode="json", exclude_none=True),
    headers=response_headers,
    media_type="application/problem+json",
)
```

认证依赖和框架创建的 `ApiProblem` 不主动提供 `WWW-Authenticate`。如果 Router、上游组件或显式 `HTTPException` 提供该 Header，序列化器会保留它。`ApiProblem` 不允许扩展成员覆盖 RFC 9457 标准字段 `type`、`title`、`status`、`detail` 或 `instance`。

| 来源 | 异常或状态 | 输出类型 | 说明 |
| --- | --- | --- | --- |
| Bearer dependency | `ApiProblem(access-token-missing)` | `401` 特定 Problem Type | 未提供平台 Access Token |
| Bearer dependency | `ApiProblem(access-token-invalid)` | `401` 特定 Problem Type | Token 无效或过期；框架不主动添加 `WWW-Authenticate` |
| Auth Router | `ApiProblem` | `401` 或 `409` 特定 Problem Type | 主账号凭据、refresh 凭据或用户名冲突 |
| VirtualAccount Router | `ApiProblem` | `401` 或 `422` 特定 Problem Type | 凭据错误或手工解析失败 |
| FastAPI 参数/Body 校验 | `RequestValidationError` | `422 invalid-request` | 顶层 `errors` 扩展含 JSON Pointer 和原因 |
| JSON 文档解析失败 | `RequestValidationError` 或 Starlette `400` | `422 invalid-request` | `errors` 固定指向根 `/`，不暴露解析器内部偏移 |
| 既有 Router 业务异常 | `HTTPException` | 原状态 + `about:blank` | 保留具体 detail，例如文件不存在、冲突和对象存储故障 |
| 未处理异常 | `Exception` | `500 internal-error` | 响应不暴露内部异常；完整堆栈按 `instance` 写入服务器日志 |

`http_exception_handler()` 会保留异常提供的错误 Header，例如 `Retry-After` 或显式的 `WWW-Authenticate`。它把原有 `HTTPException` 的字符串 detail 映射到 `about:blank` Problem Details，因此旧 Router 不需要为通用 `404`、`409`、`412`、`502` 或 `503` 分别实现序列化。

## 认证与虚拟账号

认证依赖在访问 Router、Session 或 Player 前执行：

```text
Authorization Header
  -> get_current_player()
  -> ApiProblem(access-token-missing | access-token-invalid)
  -> ExceptionMiddleware
  -> application/problem+json
```

`POST /auth/refresh` 是例外：Router 必须在 refresh 凭据无效时删除 HttpOnly cookie，因此直接调用 `problem_response()` 创建 `refresh-credential-invalid` 响应，再附加 cookie 删除 Header。

`POST /vac/login` 的用户名或密码错误会从 `AccountService` 穿过 `CommandTransactionExecutor` 到 Account Router。Executor 的 `BaseException` 路径先释放该 Request-ID 的缓存保留，再由 Router 转为 `virtual-account-invalid-credentials`。错误登录不会被缓存为命令响应，使用同一 Request-ID 的后续请求可重新校验。

## 命令与缓存

命令 Router 正常完成时仍返回缓存的成功 body：

```text
CommandTransactionExecutor.execute()
  -> RequestCache.reserve(Request-ID)
  -> transaction + Player row lock + operation + pre-commit hooks
  -> RequestCache.complete()
  -> {content, followups}
```

若 operation、hook 或 Player 加载抛出异常，Executor 回滚事务并调用 `RequestCache.release()`，然后重新抛出。后续全局或 Router 级异常处理器生成 Problem Details。只有操作返回成功 `ResponseSpec` 时才完成并缓存 Request-ID。

## 前端恢复路径

Example 的 `callApi()` 在收到错误响应时用 `response.clone()` 读取 Problem Details，不消耗随后 `readJson()` 要显示的 response body：

```text
401 Problem Details
  -> type ends with /access-token-invalid ?
       yes -> POST /auth/refresh once -> retry original request once
       no  -> 不刷新，直接展示 detail 或 title
```

这避免 VirtualAccount 密码错误触发无意义的 refresh 和重复 `/vac/login`。主账号凭据、refresh 凭据、缺少 Token 和 VirtualAccount 凭据错误都直接向用户显示。

## OpenAPI 与扩展

`create_app()` 覆盖 OpenAPI 生成过程：为每个操作声明 `400`、`401`、`403`、`404`、`409`、`412`、`422`、`500`、`502`、`503` 的 `application/problem+json` response，并添加 `ProblemDetails` schema。业务成功响应与 Problem Details 响应在 OpenAPI 中分离。

RFC 9457 允许顶层扩展成员。当前仅 `invalid-request` 使用 `errors`：每项包含 `pointer` 和 `reason`。新增扩展不得覆盖 `type`、`title`、`status`、`detail` 或 `instance`，并且不应包含密码、Token、堆栈或内部基础设施信息。

相关实现：`core/problems.py`、`main.py`、`auth/dependencies.py`、`auth/router.py`、`services/accounts/router.py`、`core/commands/executor.py`。
