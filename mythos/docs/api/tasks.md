# 任务 API

## 查询任务

```http
GET /api/v1/tasks
Authorization: Bearer <access token>
```

该端点只读取当前玩家已激活的任务，不执行 Handler，也不修改任务状态。

成功响应：

```json
{
  "tasks": [
    {
      "task_id": "example.vtb-allowance",
      "time_1": "2026-08-08T10:00:00+00:00",
      "time_2": null,
      "exception": 0,
      "meta": {}
    }
  ]
}
```

## 显式处理任务

```http
POST /api/v1/tasks/process
Authorization: Bearer <access token>
Request-ID: <UUID>
```

请求没有必需的 JSON body。它在一个 Task transaction 中处理当前玩家的任务，并返回本轮每个任务的状态。

成功响应：

```json
{
  "content": {
    "tasks": [
      {
        "task_id": "example.vtb-allowance",
        "status": "success",
        "exception": 0
      }
    ]
  },
  "followups": []
}
```

Handler 抛出普通 `Exception` 时，整个任务 batch 回滚，服务端随后仅持久化该任务的 `exception + 1`，并返回 `500 internal-error` Problem Details；不会返回部分任务报告或 `failure` 状态。Task Handler 可以通过 `TaskContext.follow(Followup(action, data))` 发出结构化通知；失败 batch 中该检查点之后的 Followup 会被回滚。任务阶段的 Hook、数据库、JSON、保存点或提交错误同样直接返回 Problem Details，且不会执行 Operation transaction。

Request-ID 遵循现有命令契约：同一玩家重放已完成 ID 返回完全相同的缓存响应，执行中的 ID 返回 `409`，其他玩家使用该 ID 也返回 `409`。系统不提供通过任务身份直接调用 Handler 的通用接口。

Example 的 `example.vtb-allowance` 使用 `time_2` 保存下一次 60 秒周期的到期时间，`time_1` 仍由 `TaskService` 在未 defer 的成功处理后写入。任务 `meta` 保存 `schema_version`、`initial_grant_applied`、`total_granted` 和 `last_granted_at`；这些字段只用于任务状态和诊断，VTB 上限始终以当前 Credits Interface 为准。玩家没有请求时不会实时获得奖励，下一次任务触发会按已过去的周期惰性补算。
