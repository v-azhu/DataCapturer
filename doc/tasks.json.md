# DataCapturer — tasks.json 功能实现任务

## 1. 开发基准

本任务以仓库当前 `main` 分支最新代码为唯一代码基准，并遵循仓库根目录 `AGENTS.md`。

当前仓库已经增加：

- `doc/`：项目文档
- `config/`：配置文件

`tasks.json` 的实现应遵循仓库当前的目录职责，不要把任务持久化逻辑散落到 `douyin/` 业务模块中。

当前 `main.py` 仍然是交互式 CLI 入口：
- 1：下载视频
- 2：抓取评论

任务系统应在此入口之上增加统一的任务管理/执行层，同时保持现有交互式功能。

---

## 2. tasks.json 文件位置

任务文件放在：

```text
config/tasks.json
```

如果文件不存在，程序应按空任务队列处理，并在需要保存任务时创建它。

文档放在：

```text
doc/
```

---

## 3. tasks.json 顶层结构

```json
{
  "tasks": []
}
```

每个任务：

```json
{
  "id": "唯一任务ID",
  "app": "douyin",
  "type": "video",
  "url": "原始URL或分享口令/文本",
  "options": {},
  "result": null
}
```

---

## 4. Task 字段

### id

- 类型：`string`
- 必填
- 全局唯一
- 创建任务时自动生成
- 建议使用 UUID
- 重试时不得改变

### app

- 类型：`string`
- 第一阶段支持：`douyin`
- 预留：`kuishou`、`youtube` 等

### type

- 类型：`string`
- 第一阶段只允许：

```text
video
comment
```

含义：

- `video`：下载视频
- `comment`：抓取评论

### url

保存用户原始输入，可以是：

- 完整 URL
- 短链接
- 包含 URL 的分享文本
- 分享口令

不要要求任务创建阶段必须提前解析成最终 URL；由具体平台模块负责解析。

---

## 5. options 规则

`options` 是与任务类型相关的参数。

### video

`video` 任务只允许视频下载相关参数：

```json
"options": {
  "output_dir": "data/videos"
}
```

**绝对不要向 `video` 任务写入：**

```text
max_comments
anonymize
```

### comment

`comment` 任务可以使用：

```json
"options": {
  "max_comments": 500,
  "anonymize": false,
  "output_dir": "data/comments"
}
```

字段：

- `max_comments`：整数，最大评论数量
- `anonymize`：布尔值，是否对评论作者信息脱敏
- `output_dir`：输出目录

没有显式指定的选项，应使用现有业务模块的默认值。

---

## 6. result

新任务：

```json
"result": null
```

任务执行结束后写入：

```json
"result": {
  "status": "success",
  "finished_at": "2026-08-21T15:00:00+08:00",
  "error": null,
  "retry": false,
  "attempts": 1
}
```

字段：

### status

允许：

```text
success
failed
```

### finished_at

使用 ISO 8601 时间格式，记录最近一次执行结束时间。

### error

- 成功：`null`
- 失败：保存适合用户查看和调试的错误信息

### retry

布尔值：

- `true`：下一次启动允许自动重试
- `false`：下一次启动不自动执行

### attempts

表示程序已经自动执行该任务的次数。

第一轮：

```text
attempts = 1
```

第二轮：

```text
attempts = 2
```

---

## 7. 自动重试规则

一个任务最多自动执行两次。

第一次失败：

```json
"result": {
  "status": "failed",
  "finished_at": "...",
  "error": "...",
  "retry": true,
  "attempts": 1
}
```

第二次仍失败：

```json
"result": {
  "status": "failed",
  "finished_at": "...",
  "error": "...",
  "retry": false,
  "attempts": 2
}
```

`retry=false` 的失败任务仍然保留在 `tasks.json`，只是后续启动自动跳过。

用户可以手工把：

```json
"retry": false
```

改成：

```json
"retry": true
```

以重新启用任务。

---

## 8. main.py 启动行为

启动时首先读取 `config/tasks.json`。

### 情况 A：没有任务

如果：

```json
{
  "tasks": []
}
```

直接进入现有的新建任务交互流程。

---

### 情况 B：存在待重试任务

“待重试任务”严格定义为：

```text
result.status == "failed"
AND
result.retry == true
```

如果存在 N 个待重试任务，启动时提示：

```text
检测到 N 个待重试任务，是否现在处理？(Y/n)
```

#### 用户输入 Y

执行所有待重试任务。

执行规则：

- 成功：`status=success`，`retry=false`
- 第一次失败：`retry=true`，等待下一次启动
- 第二次失败：`attempts=2`，`retry=false`

#### 用户输入 n

不执行旧的待重试任务。

直接进入新建任务流程。

---

### 情况 C：只有失败但不可重试任务

如果存在：

```text
status=failed
retry=false
```

但不存在：

```text
status=failed
retry=true
```

则不显示“检测到 N 个待重试任务”的提示。

直接进入新建任务流程。

这些失败任务必须继续保留。

---

## 9. 新任务必须追加

用户选择 `n` 后进入新建任务流程。

创建的新任务必须追加到已有：

```json
tasks
```

数组中。

例如原来：

```json
{
  "tasks": [
    {
      "id": "old-1",
      "result": {
        "status": "failed",
        "retry": true,
        "attempts": 1
      }
    }
  ]
}
```

用户选择 `n` 并创建新任务后：

```json
{
  "tasks": [
    {
      "id": "old-1",
      "result": {
        "status": "failed",
        "retry": true,
        "attempts": 1
      }
    },
    {
      "id": "new-1",
      "result": null
    }
  ]
}
```

不得覆盖旧任务。

---

## 10. 任务执行后的持久化

每个任务执行结束后，必须立即写回：

```text
config/tasks.json
```

不能等全部任务执行结束后再统一保存。

原因：

如果程序在任务 2 执行过程中异常退出，任务 1 的执行结果仍然必须已经持久化。

---

## 11. 批次清理规则

只有当本次任务队列中的所有任务最终都是：

```text
status == success
```

才清空：

```json
{
  "tasks": []
}
```

只要存在任意失败任务，就不能清空整个任务文件。

特别注意：

```text
retry=false
status=failed
```

的任务虽然不会自动重试，但仍然属于失败任务，因此不能因为它“不再重试”而删除。

---

## 12. 建议的执行模型

不要把 tasks.json 的逻辑直接写进：

```text
douyin/download.py
douyin/comment.py
```

建议增加独立的任务层，例如：

```text
main.py
   │
   ▼
task manager / task runner
   │
   ├── task persistence
   │      └── config/tasks.json
   │
   ├── task validation
   │
   └── task execution
          │
          ├── douyin.video
          │
          └── douyin.comment
```

具体文件名和模块位置以仓库现有 `doc/`、`config/` 组织方式为准，不要为了任务系统重复实现现有 Douyin 业务逻辑。

---

## 13. 交互式任务也必须经过 tasks.json

现有 CLI 的直接执行方式需要改变。

当前：

```text
用户选择功能
    ↓
输入分享链接
    ↓
直接执行
```

改为：

```text
用户选择功能
    ↓
创建 Task
    ↓
追加到 config/tasks.json
    ↓
统一 Task Runner 执行
    ↓
更新 result
    ↓
保存 config/tasks.json
```

这样：

- 预先写入的 tasks.json 任务
- 用户临时创建的新任务

最终都走同一条执行路径。

---

## 14. 第一阶段不要增加的功能

本次实现暂不增加：

- 任务优先级
- 定时任务
- 并发执行
- 完整执行历史
- started_at
- duration
- 复杂任务依赖
- 任务调度器

保持任务系统简单、可恢复、可人工修改。

---

## 15. 验收场景

实现完成后至少验证以下场景。

### 场景 1：没有 tasks.json

程序能够进入新建任务流程。

### 场景 2：tasks.json 存在但 tasks 为空

程序能够进入新建任务流程。

### 场景 3：存在一个待重试任务

显示：

```text
检测到 1 个待重试任务，是否现在处理？(Y/n)
```

### 场景 4：选择 n

旧任务不执行，新任务追加到数组。

### 场景 5：选择 Y 且任务成功

任务变为：

```text
status=success
retry=false
```

### 场景 6：第一次执行失败

任务变为：

```text
status=failed
retry=true
attempts=1
```

### 场景 7：第二次执行仍失败

任务变为：

```text
status=failed
retry=false
attempts=2
```

### 场景 8：同时存在成功和失败任务

成功任务不得导致整个 `tasks.json` 被清空。

### 场景 9：所有任务成功

最终：

```json
{
  "tasks": []
}
```

### 场景 10：video task 参数验证

以下任务必须被判定为非法：

```json
{
  "type": "video",
  "options": {
    "max_comments": 500
  }
}
```

以及：

```json
{
  "type": "video",
  "options": {
    "anonymize": true
  }
}
```

而以下是合法的：

```json
{
  "type": "video",
  "options": {
    "output_dir": "data/videos"
  }
}
```

---

## 16. 实现要求

以仓库最新代码和 `AGENTS.md` 为最高优先级。

不要为了实现 tasks.json 而重写现有 Douyin 下载/评论功能。

优先复用：

```text
douyin.download.download_video()
douyin.comment.capture_comments()
```

任务层负责：

```text
读取任务
→ 验证任务
→ 调用业务函数
→ 捕获执行结果
→ 更新 result
→ 持久化
→ 判断是否清空
```

保持现有交互式 CLI 的用户体验，只把“直接执行”改成“创建任务后由统一任务执行器执行”。
