# DataCapturer

一个个人学习/存档用途的小工具，用于：
- 通过抖音分享链接，解析并下载视频；
- 通过抖音视频链接，抓取该视频下的评论。

A small personal-use tool for:
- Resolving a Douyin share link and downloading the video file;
- Capturing the comments under a given Douyin video.

## 项目结构 / Project Structure

```
douyin/
  utils.py      # URL 解析工具 (URL parsing helpers)
  client.py      # 共用的 Playwright 页面/接口监听逻辑 (shared Playwright client)
  download.py    # 视频下载 (video download)
  comment.py     # 评论抓取 (comment scraping)
main.py          # 命令行入口 (CLI entry point)
tests/           # 手动测试脚本 (manual test scripts)
```

## 安装 / Installation

```bash
pip install -r requirements.txt
playwright install chromium
# 评论抓取功能使用 Edge 持久化 profile 登录，如需要:
playwright install msedge
```

## 使用 / Usage

```bash
python main.py
```

程序会提示你选择"下载视频"或"抓取评论"，然后粘贴分享链接/口令即可。

The program will prompt you to choose "download video" or "capture comments", then paste the share link/text.

## 配置 / Configuration

评论抓取相关的可调参数在 `douyin/comment.py` 顶部：

- `ANONYMIZE_USERS`：是否对评论作者的 `user_id` / `nickname` 做哈希脱敏（默认 `False`）。如果你打算保存、分享或长期留存抓取结果，建议改为 `True`。
- `MAX_COMMENTS`：单次抓取的最大评论数量。
- `SCROLL_WAIT` / `SCROLL_JITTER`：控制抓取节奏，避免请求过于密集。

Configurable parameters live at the top of `douyin/comment.py`:

- `ANONYMIZE_USERS`: whether to hash the commenter's `user_id` / `nickname` (default `False`). If you plan to store, share, or retain the scraped data long-term, consider setting this to `True`.
- `MAX_COMMENTS`: maximum number of comments to collect per run.
- `SCROLL_WAIT` / `SCROLL_JITTER`: control the scraping pace to avoid overly aggressive request patterns.

## 免责声明 / Disclaimer

**中文：**

本项目仅用于个人学习、技术研究与个人内容存档目的。使用本工具时请遵守抖音平台的用户协议、Robots 协议及所在地区的相关法律法规，包括但不限于著作权法与个人信息保护相关法律。

- 请勿使用本工具下载、传播他人拥有版权的视频内容，或将其用于商业用途。
- 请勿使用本工具大规模采集、存储或对外分享他人的评论内容、用户昵称、用户 ID 等个人信息。
- 使用本工具所产生的一切法律责任由使用者自行承担，作者不对因使用本工具而导致的任何直接或间接后果负责。
- 抖音的接口、页面结构可能随时变化，本工具不保证长期可用，也不构成对抖音平台任何安全机制的规避担保。

如果你是内容原作者，希望下载并保存自己发布在抖音上的内容，或是出于合理的个人学习目的短时间、小范围使用本工具，这是本项目设计的初衷。请不要将其用于侵犯他人权益的场景。

**English:**

This project is intended solely for personal learning, technical research, and personal archiving of content you have the right to use. When using this tool, please comply with Douyin's Terms of Service, its robots policy, and applicable laws in your jurisdiction, including but not limited to copyright law and personal-data-protection law.

- Do not use this tool to download or redistribute copyrighted video content belonging to others, or for any commercial purpose.
- Do not use this tool to collect, store, or share other users' comments, nicknames, user IDs, or other personal information at scale.
- Any legal responsibility arising from the use of this tool rests solely with the user. The author assumes no liability for any direct or indirect consequences resulting from its use.
- Douyin's APIs and page structure may change at any time; this tool is provided with no guarantee of continued functionality and is not intended to circumvent any platform security mechanism.

This project is meant for creators archiving their own content, or for short, small-scale personal learning use. Please do not use it in ways that infringe on the rights of others.

## License

本项目按 [MIT License](https://opensource.org/licenses/MIT) 开源，仅供学习交流使用。
Released under the MIT License, for educational purposes only.
