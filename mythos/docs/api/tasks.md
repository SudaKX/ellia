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
      "task_id": "example.hourly-credit",
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
        "task_id": "example.hourly-credit",
        "status": "success",
        "exception": 0
      }
    ]
  },
  "followups": []
}
```

可识别的 Handler 错误会在任务报告中返回 `failure`，并增加该任务的 `exception`；任务阶段的数据库、Hook、序列化或提交错误直接返回 Problem Details，并且不会执行 Operation transaction。

Request-ID 遵循现有命令契约：同一玩家重放已完成 ID 返回完全相同的缓存响应，执行中的 ID 返回 `409`，其他玩家使用该 ID 也返回 `409`。系统不提供通过任务身份直接调用 Handler 的通用接口。
