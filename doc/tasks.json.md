# tasks.json 任务文件结构设计

## 1. 目的

`tasks.json` 是 DataCapturer 的持久化任务队列，用于保存用户希望程序执行的视频下载和评论抓取任务。

`main.py` 启动时首先检查 `tasks.json`：

1. 如果存在待处理任务，则直接执行 `tasks.json` 中的任务。
2. 如果不存在任务，则进入当前交互式 CLI，要求用户输入新任务。
3. 交互式产生的新任务必须写入 `tasks.json`。
4. 每个任务执行结束后，立即将执行结果写回 `tasks.json`。
5. 当前批次所有任务均成功后，清空 `tasks.json`。
6. 如果存在失败任务，则保留失败任务，以便下一次启动时继续处理。
7. 失败任务最多自动执行两次；第二次仍失败后，将 `retry` 设置为 `false`，后续启动自动跳过该任务。
8. 用户可以手动修改 `retry` 为 `true`，重新允许该任务执行。

---

## 2. 基本结构

`tasks.json` 顶层只包含一个 `tasks` 数组。

```json
{
  "tasks": [
    {
      "id": "任务唯一ID",
      "app": "douyin",
      "type": "video",
      "url": "https://www.douyin.com/video/123456789",
      "options": {},
      "result": null
    }
  ]
}
```

### 顶层字段

| 字段      | 类型    | 必需 | 含义      |
| ------- | ----- | -: | ------- |
| `tasks` | array |  是 | 待执行任务列表 |

`tasks` 可以为空：

```json
{
  "tasks": []
}
```

这表示当前没有待执行任务。

---

# 3. Task 对象

每个 `tasks` 元素代表一个独立任务。

```json
{
  "id": "7d5c8b3e-3d8d-4e92-9e5d-8e4f6e3a12ab",
  "app": "douyin",
  "type": "video",
  "url": "https://www.douyin.com/video/123456789",
  "options": {
    "output_dir": "data/videos"
  },
  "result": null
}
```

---

## 3.1 `id`

类型：

```text
string
```

含义：

任务的唯一标识符。

建议使用 UUID，例如：

```text
7d5c8b3e-3d8d-4e92-9e5d-8e4f6e3a12ab
```

要求：

* 每个任务必须唯一。
* 创建任务时由程序自动生成。
* 程序重新启动后不得改变。
* 任务失败、重试时仍使用原来的 `id`。

`id` 的作用主要是：

* 标识任务；
* 日志中定位任务；
* 调试；
* 后续扩展任务管理功能。

---

# 4. `app`

类型：

```text
string
```

表示任务属于哪个平台。

当前允许：

```text
douyin
kuishou
youtube
...
```

例如：

```json
"app": "douyin"
```

第一阶段只实现：

```text
douyin
```

以后增加其他平台时，在任务执行器中增加对应的 app handler。

因此：

```json
{
  "app": "douyin"
}
```

表示该任务由 Douyin 平台处理。

---

# 5. `type`

类型：

```text
string
```

表示任务类型。

当前定义：

```text
video
comment
```

含义：

| type      | 含义   |
| --------- | ---- |
| `video`   | 下载视频 |
| `comment` | 抓取评论 |

例如：

```json
"type": "video"
```

表示视频下载任务。

```json
"type": "comment"
```

表示评论抓取任务。

后续如果需要增加其他任务类型，可以继续扩展，例如：

```text
profile
search
metadata
```

但第一阶段不实现。

---

# 6. `url`

类型：

```text
string
```

表示任务的输入地址或原始输入内容。

这里有一个重要设计：

`url` 不要求一定是已经解析完成的最终 URL。

它可以是：

1. 完整 URL；
2. 短链接；
3. 包含 URL 的分享文案；
4. 平台分享口令。

例如：

```json
"url": "https://www.douyin.com/video/123456789"
```

或者：

```json
"url": "7.23 复制打开抖音，看看这个视频…… https://v.douyin.com/xxxx/"
```

程序实际执行任务时，再交给对应平台的 URL 解析器处理。

这样做与当前 Douyin 模块的设计保持一致：`download_video()` 和 `capture_comments()` 本身都已经支持分享文本/链接的解析。

因此 `tasks.json` 不负责保存“解析后的 URL”，而保存用户原始任务输入。

---

# 7. `options`

类型：

```text
object
```

用于保存任务特有的可选参数。

设计原则：

> 只有用户明确指定、并且任务需要覆盖默认值的参数才写入 `options`。

没有指定的参数由具体功能模块使用默认值。

---

## 7.1 `max_comments`

类型：

```text
integer | null
```

只对：

```text
type = comment
```

有效。

表示最多抓取多少条评论。

例如：

```json
"options": {
  "max_comments": 500
}
```

表示最多抓取 500 条评论。

如果：

```json
"max_comments": null
```

表示不限制数量。

当前 Douyin 评论模块已经支持 `max_comments` 参数，并且 `None` 表示不限制。

---

## 7.2 `anonymize`

类型：

```text
boolean
```

只对评论任务有效。

表示是否对评论作者的信息进行脱敏。

```json
"anonymize": true
```

表示：

* `user_id` 哈希化；
* `nickname` 哈希化。

```json
"anonymize": false
```

表示保留原始信息。

当前 Douyin 评论模块已经提供这一参数。

默认值：

```text
false
```

---

## 7.3 `output_dir`

类型：

```text
string
```

表示任务输出目录。

例如：

```json
"options": {
  "output_dir": "data/videos"
}
```

或者：

```json
"options": {
  "output_dir": "data/comments"
}
```

如果没有指定，则由对应功能模块使用自己的默认目录。

当前代码中：

* 视频下载默认目录为 `data/downloads`；
* 评论默认目录为 `data/comments`。

因此第一阶段建议不要强制要求 `output_dir`，以保持现有功能兼容。

---

# 8. `result`

类型：

```text
object | null
```

表示任务最近一次执行的结果。

新创建但尚未执行的任务：

```json
"result": null
```

任务执行后：

```json
"result": {
  "status": "success",
  "finished_at": "2026-08-21T14:30:25+08:00",
  "error": null,
  "retry": false,
  "attempts": 1
}
```

---

# 9. `result.status`

类型：

```text
string
```

允许：

```text
success
failed
```

### `success`

表示任务执行成功。

例如：

```json
"status": "success"
```

### `failed`

表示任务执行失败。

例如：

```json
"status": "failed"
```

不在 `status` 中加入 `retrying`、`running` 等状态。

`tasks.json` 的职责是保存持久化任务及最近一次结果，而不是实时运行状态。

---

# 10. `result.finished_at`

类型：

```text
string | null
```

表示最近一次任务执行结束的时间。

使用 ISO 8601 格式。

例如：

```text
2026-08-21T14:30:25+08:00
```

成功和失败都应该记录。

---

# 11. `result.error`

类型：

```text
string | null
```

表示任务失败的原因。

成功：

```json
"error": null
```

失败：

```json
"error": "无法从输入内容中找到有效的抖音链接"
```

或者：

```json
"error": "下载失败，已重试 3 次: Connection timed out"
```

这里保存的是适合用户阅读和调试的错误摘要。

如果任务成功，不应该保留上一次失败的错误。

---

# 12. `result.retry`

类型：

```text
boolean
```

表示该任务下次启动时是否允许自动重试。

### `true`

允许下一次启动继续执行。

### `false`

不再自动执行。

例如：

```json
"retry": true
```

表示：

> 本次失败，下次启动继续尝试。

而：

```json
"retry": false
```

表示：

> 该任务已经达到自动重试限制，后续启动跳过。

这里使用 Boolean 而不是 `"yes"` / `"ignore"`，因为这个字段本质上是程序控制标志。

---

# 13. `result.attempts`

类型：

```text
integer
```

表示该任务已经执行过多少次。

第一次执行：

```json
"attempts": 1
```

第一次失败并准备重试：

```json
"attempts": 1,
"retry": true
```

第二次失败：

```json
"attempts": 2,
"retry": false
```

这样可以明确表达“最多自动执行两次”的规则，而不需要根据其他字段推断。

---

# 14. 重试规则

任务执行规则如下：

```text
新任务
  │
  ▼
attempts = 0
  │
  ▼
执行任务
  │
  ├── 成功 ──→ status=success
  │             retry=false
  │
  └── 失败
        │
        ▼
    attempts=1
    retry=true
        │
        ▼
   下一次启动
        │
        ▼
    再次执行
        │
        ├── 成功 ──→ status=success
        │             retry=false
        │
        └── 失败 ──→ attempts=2
                      retry=false
                      后续自动跳过
```

因此一个任务最多被程序自动执行两次。

---

# 15. 用户手动重新启用任务

如果任务第二次执行仍然失败：

```json
{
  "result": {
    "status": "failed",
    "finished_at": "2026-08-21T15:20:00+08:00",
    "error": "下载失败",
    "retry": false,
    "attempts": 2
  }
}
```

程序下一次启动时应该跳过该任务。

如果用户确认问题已经解决，可以手动修改：

```json
"retry": true
```

此时程序允许再次执行。

`attempts` 不需要人为修改。

这样可以区分：

* 自动重试次数；
* 用户主动重新启用任务。

---

# 16. 多任务执行

`tasks` 可以包含多个任务。

例如：

```json
{
  "tasks": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "app": "douyin",
      "type": "video",
      "url": "https://www.douyin.com/video/111",
      "options": {
        "output_dir": "data/videos"
      },
      "result": null
    },
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "app": "douyin",
      "type": "comment",
      "url": "https://www.douyin.com/video/222",
      "options": {
        "max_comments": 500,
        "anonymize": true,
        "output_dir": "data/comments"
      },
      "result": null
    }
  ]
}
```

程序按照 `tasks` 数组顺序逐个执行。

第一阶段不实现并发执行。

这样可以避免多个任务同时操作浏览器、网络连接或输出文件而产生额外问题。

---

# 17. 执行过程中的持久化

任务执行结果必须在每个任务结束后立即写回 `tasks.json`。

例如原始文件：

```json
{
  "tasks": [
    {
      "id": "111",
      "app": "douyin",
      "type": "video",
      "url": "...",
      "options": {},
      "result": null
    },
    {
      "id": "222",
      "app": "douyin",
      "type": "comment",
      "url": "...",
      "options": {},
      "result": null
    }
  ]
}
```

第一个任务成功后，应立即保存：

```json
{
  "tasks": [
    {
      "id": "111",
      "app": "douyin",
      "type": "video",
      "url": "...",
      "options": {},
      "result": {
        "status": "success",
        "finished_at": "2026-08-21T14:30:25+08:00",
        "error": null,
        "retry": false,
        "attempts": 1
      }
    },
    {
      "id": "222",
      "app": "douyin",
      "type": "comment",
      "url": "...",
      "options": {},
      "result": null
    }
  ]
}
```

这样即使第二个任务执行过程中程序突然退出，第一个任务的执行结果也不会丢失。

---

# 18. 批次完成后的处理

当所有任务执行结束后：

### 所有任务成功

直接清空：

```json
{
  "tasks": []
}
```

### 存在失败任务

保留任务。

例如：

```json
{
  "tasks": [
    {
      "id": "111",
      "app": "douyin",
      "type": "video",
      "url": "...",
      "options": {},
      "result": {
        "status": "success",
        "finished_at": "2026-08-21T14:30:25+08:00",
        "error": null,
        "retry": false,
        "attempts": 1
      }
    },
    {
      "id": "222",
      "app": "douyin",
      "type": "comment",
      "url": "...",
      "options": {},
      "result": {
        "status": "failed",
        "finished_at": "2026-08-21T14:35:12+08:00",
        "error": "登录超时",
        "retry": true,
        "attempts": 1
      }
    }
  ]
}
```

下一次启动时：

* `111` 不再执行；
* `222` 自动重试。

---

# 19. 第二次失败后的文件状态

例如：

```json
{
  "tasks": [
    {
      "id": "222",
      "app": "douyin",
      "type": "comment",
      "url": "...",
      "options": {},
      "result": {
        "status": "failed",
        "finished_at": "2026-08-21T15:35:12+08:00",
        "error": "登录超时",
        "retry": false,
        "attempts": 2
      }
    }
  ]
}
```

由于：

```text
status = failed
retry = false
attempts = 2
```

程序下一次启动时跳过该任务。

注意：

> 即使任务被跳过，也不能因为它失败而自动清空 `tasks.json`。

因为它仍然是一个未成功完成的任务，需要保留给用户处理。

只有当 `tasks` 中所有任务最终都是 `success`，才可以清空文件。

---

# 20. 启动时任务处理规则

`main.py` 启动后按照以下逻辑：

```text
读取 tasks.json
     │
     ├── 文件不存在
     │       │
     │       ▼
     │    创建空任务状态
     │
     └── 文件存在
             │
             ▼
       检查 tasks
             │
       ┌─────┴─────┐
       │           │
     空数组       有任务
       │           │
       ▼           ▼
    进入 CLI     执行任务
                   │
                   ▼
              更新 result
                   │
                   ▼
             保存 tasks.json
                   │
                   ▼
             所有任务成功？
               │       │
              是       否
               │       │
               ▼       ▼
          清空 tasks   保留 tasks
```

如果 `tasks` 不为空，则**不进入当前交互式模式**。

也就是说：

> `tasks.json` 的任务优先级高于交互式输入。

这样程序就具备了基本的“任务恢复”能力。

---

# 21. 交互式模式产生新任务

当：

```json
{
  "tasks": []
}
```

或者 `tasks.json` 不存在时，程序进入现有 CLI。

用户选择：

```text
1. 下载视频
2. 抓取评论
```

完成输入后，不再直接执行，而是先创建 Task：

```json
{
  "id": "自动生成 UUID",
  "app": "douyin",
  "type": "video",
  "url": "用户输入",
  "options": {},
  "result": null
}
```

然后写入 `tasks.json`。

之后由统一任务执行器执行。

这样交互式任务和 `tasks.json` 中预先定义的任务最终走同一套执行路径。

---

# 22. 完整示例

## 视频下载任务

```json
{
  "tasks": [
    {
      "id": "7d5c8b3e-3d8d-4e92-9e5d-8e4f6e3a12ab",
      "app": "douyin",
      "type": "video",
      "url": "https://www.douyin.com/video/123456789",
      "options": {
        "output_dir": "data/videos"
      },
      "result": null
    }
  ]
}
```

---

## 评论抓取任务

```json
{
  "tasks": [
    {
      "id": "8f3b7a1c-6d20-4e42-b2e5-6e5f9c1d1234",
      "app": "douyin",
      "type": "comment",
      "url": "https://www.douyin.com/video/123456789",
      "options": {
        "max_comments": 500,
        "anonymize": true,
        "output_dir": "data/comments"
      },
      "result": null
    }
  ]
}
```

---

## 执行成功后的任务

```json
{
  "tasks": [
    {
      "id": "7d5c8b3e-3d8d-4e92-9e5d-8e4f6e3a12ab",
      "app": "douyin",
      "type": "video",
      "url": "https://www.douyin.com/video/123456789",
      "options": {
        "output_dir": "data/videos"
      },
      "result": {
        "status": "success",
        "finished_at": "2026-08-21T14:30:25+08:00",
        "error": null,
        "retry": false,
        "attempts": 1
      }
    }
  ]
}
```

如果这是唯一任务，任务批次完成后最终变成：

```json
{
  "tasks": []
}
```

---

# 23. 第一阶段最终 Schema

第一阶段正式采用以下结构：

```json
{
  "tasks": [
    {
      "id": "string",
      "app": "douyin",
      "type": "video",
      "url": "string",
      "options": {
        "max_comments": 500,
        "anonymize": false,
        "output_dir": "data/videos"
      },
      "result": {
        "status": "success",
        "finished_at": "2026-08-21T14:30:25+08:00",
        "error": null,
        "retry": false,
        "attempts": 1
      }
    }
  ]
}
```

字段定义最终确定为：

```text
tasks
└── task
    ├── id
    ├── app
    ├── type
    ├── url
    ├── options
    │   ├── max_comments
    │   ├── anonymize
    │   └── output_dir
    │
    └── result
        ├── status
        ├── finished_at
        ├── error
        ├── retry
        └── attempts
```

---

# 24. 暂不加入的字段

第一阶段明确不加入以下字段：

### `created_at`

暂时没有必要。

任务本身不需要知道创建时间，只有执行结果需要记录时间。

### `started_at`

暂时不需要。

目前 `tasks.json` 主要负责任务恢复，不负责详细运行统计。

### `duration`

暂时不需要。

后续如果需要性能统计再增加。

### `output_file`

暂时不需要。

当前不同平台、不同任务的输出文件结构并不统一。输出路径由具体功能模块负责。

### `history`

暂时不需要。

`result` 只保存最后一次执行结果。

如果未来需要完整的执行历史，可以增加：

```json
"history": []
```

但第一阶段保持简单。

---

# 25. 设计原则

`tasks.json` 第一阶段遵循以下原则：

1. **简单**：只保存执行任务所必需的信息。
2. **可恢复**：程序中途退出后可以从 `tasks.json` 继续。
3. **可重试**：失败任务最多自动执行两次。
4. **可人工干预**：用户可以修改 `retry` 决定是否重新执行。
5. **统一入口**：交互式任务和预定义任务最终使用同一个 Task 执行器。
6. **平台无关**：顶层任务结构不绑定 Douyin，实现其他平台时只增加对应 handler。
7. **功能与任务分离**：`tasks.json` 描述“做什么”，`douyin/download.py`、`douyin/comment.py` 等模块负责“怎么做”。
8. **立即持久化**：每个任务结束后立即更新 `tasks.json`，避免程序异常退出造成任务状态丢失。
9. **第一阶段不做过度设计**：暂不加入任务调度时间、优先级、并发、历史记录等功能。
