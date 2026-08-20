import asyncio
import hashlib
import json
import os
import random
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta


from playwright.async_api import async_playwright


# ============================================================
# 配置
# ============================================================

# Edge 专用用户数据目录
# 登录一次以后，Cookie 等浏览器状态会保存在这里
EDGE_PROFILE_DIR = "data/edge_profile"

# 评论保存目录
OUTPUT_DIR = "data/comments"

# 每次滚动后的等待时间
SCROLL_WAIT = 2.0

# 连续多少次没有获得新评论后停止
MAX_NO_NEW_COMMENT = 5

# 最大评论数量
# None = 不限制
MAX_COMMENTS = None

# 是否对评论中的用户信息做脱敏处理
# True: user_id / nickname 会被替换为哈希值，仅用于去重和统计
# False: 保留原始信息
ANONYMIZE_USERS = False

# 滚动等待时间的随机抖动范围（秒）
# 实际等待 = SCROLL_WAIT + random.uniform(-SCROLL_JITTER, SCROLL_JITTER)
SCROLL_JITTER = 0.8

# 登录检测：
# 未登录时最多等待多少秒
LOGIN_TIMEOUT = 300

# 登录检测间隔
LOGIN_CHECK_INTERVAL = 2


# ============================================================
# 工具函数
# ============================================================

def get_video_id(video_url):
    """
    从抖音视频 URL 中提取 video_id。

    例如：

    https://www.douyin.com/video/7668904077169790227

    返回：

    7668904077169790227
    """

    path = urlparse(video_url).path

    parts = [
        part
        for part in path.split("/")
        if part
    ]

    if not parts:
        raise ValueError(
            f"无法从 URL 中提取视频 ID: {video_url}"
        )

    return parts[-1]


# ============================================================
# 用户信息脱敏
# ============================================================

def _anonymize(value):
    """
    对用户标识做简单的哈希脱敏。
    保留可用于去重/统计的一致性，但不再是原始明文。
    """

    if value is None:
        return None

    digest = hashlib.sha256(
        str(value).encode("utf-8")
    ).hexdigest()

    return digest[:12]


# ============================================================
# 评论解析
# ============================================================

def parse_comment(comment, anonymize=ANONYMIZE_USERS):
    """
    从抖音评论 JSON 中提取需要的数据。

    create_time:
        抖音返回 Unix 时间戳。
        保存时转换为北京时间：

        YYYY-MM-DD HH:MM:SS
    """

    user = comment.get("user") or {}

    create_time = comment.get(
        "create_time"
    )

    # --------------------------------------------------------
    # Unix 时间戳 -> 北京时间
    # --------------------------------------------------------

    if create_time is not None:

        try:

            timestamp = int(
                create_time
            )

            # Unix 时间戳 -> UTC
            utc_time = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            )

            # UTC -> UTC+8（北京时间）
            beijing_time = utc_time.astimezone(
                timezone(
                    timedelta(hours=8)
                )
            )

            create_time = beijing_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        except Exception as e:

            print(
                "create_time 转换失败:",
                repr(create_time),
                e
            )

            create_time = None

    user_id = user.get("uid")
    nickname = user.get("nickname")

    if anonymize:
        user_id = _anonymize(user_id)
        nickname = _anonymize(nickname)

    return {
        "comment_id": comment.get(
            "cid"
        ),

        "user_id": user_id,

        "nickname": nickname,

        "text": comment.get(
            "text"
        ),

        "digg_count": comment.get(
            "digg_count",
            0
        ),

        "create_time": create_time,
    }
# ============================================================
# 保存评论
# ============================================================

def save_comments(
    video_id,
    comments
):
    """
    保存评论 JSON。
    """

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    filename = os.path.join(
        OUTPUT_DIR,
        f"{video_id}.json"
    )

    data = {
        "video_id": video_id,
        "comment_count": len(comments),
        "comments": comments,
    }

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("评论保存完成")
    print("=" * 60)

    print("文件:")
    print(filename)

    print("数量:", len(comments))


# ============================================================
# 评论采集器
# ============================================================

class DouyinCommentCapturer:

    def __init__(
        self,
        video_url,
        max_comments=MAX_COMMENTS,
        anonymize=ANONYMIZE_USERS
    ):

        self.video_url = video_url

        self.video_id = get_video_id(
            video_url
        )

        self.max_comments = (
            max_comments
        )

        self.anonymize = anonymize

        # ----------------------------------------------------
        # 评论
        # ----------------------------------------------------

        self.comments = []

        # comment_id -> comment
        self.comment_map = {}

        # ----------------------------------------------------
        # 评论接口状态
        # ----------------------------------------------------

        # 是否还有更多评论
        self.has_more = True

        # 最近一次评论接口 cursor
        self.last_cursor = None

        # 最近一次评论接口是否有新评论
        self.last_response_new_count = 0

        # ----------------------------------------------------
        # Playwright
        # ----------------------------------------------------

        self.page = None

    # ========================================================
    # 登录状态检测
    # ========================================================

    async def is_logged_in(self):
        """
        判断当前抖音页面是否已经登录。

        注意：
        抖音页面的 DOM 会发生变化，因此这里不依赖
        某一个非常具体的页面元素。

        当前策略：
        如果页面上存在明确的“登录”按钮，则认为未登录。

        如果没有检测到“登录”按钮，则认为已经登录。
        """

        if self.page is None:
            return False

        try:

            # ------------------------------------------------
            # 检查常见登录按钮
            # ------------------------------------------------

            selectors = [
                'text="登录"',
                'button:has-text("登录")',
                '[class*="login"]',
            ]

            for selector in selectors:

                try:

                    locator = self.page.locator(
                        selector
                    )

                    count = await locator.count()

                    if count == 0:
                        continue

                    # 至少有一个可见元素
                    for i in range(
                        min(count, 5)
                    ):

                        try:

                            if await locator.nth(
                                i
                            ).is_visible():

                                return False

                        except Exception:

                            continue

                except Exception:

                    continue

            # ------------------------------------------------
            # 没有发现明显的登录按钮
            # ------------------------------------------------

            return True

        except Exception:

            # 检测失败时不要直接认为已登录
            return False

    # ========================================================
    # 等待登录
    # ========================================================

    async def wait_for_login(self):
        """
        检查登录状态。

        已登录：
            自动继续。

        未登录：
            提示用户在浏览器中完成登录，
            然后自动检测登录是否完成。

        不再要求用户按 Enter。
        """

        print()
        print("=" * 60)
        print("检查浏览器登录状态")
        print("=" * 60)

        # ----------------------------------------------------
        # 给抖音页面一点时间完成初始化
        # ----------------------------------------------------

        await self.page.wait_for_timeout(
            2000
        )

        logged_in = await self.is_logged_in()

        # ----------------------------------------------------
        # 已登录
        # ----------------------------------------------------

        if logged_in:

            print()
            print(
                "检测到已有登录状态。"
            )

            print(
                "自动继续采集评论。"
            )

            return True

        # ----------------------------------------------------
        # 未登录
        # ----------------------------------------------------

        print()
        print(
            "当前似乎尚未登录抖音。"
        )

        print()
        print(
            "请在打开的 Edge 浏览器中"
        )

        print(
            "手动完成抖音登录。"
        )

        print()
        print(
            "登录状态会保存到:"
        )

        print(
            EDGE_PROFILE_DIR
        )

        print()
        print(
            "登录完成后，程序会自动继续。"
        )

        print()
        print(
            f"最多等待 {LOGIN_TIMEOUT} 秒..."
        )

        print("-" * 60)

        # ----------------------------------------------------
        # 自动等待登录
        # ----------------------------------------------------

        elapsed = 0

        while elapsed < LOGIN_TIMEOUT:

            await self.page.wait_for_timeout(
                LOGIN_CHECK_INTERVAL * 1000
            )

            elapsed += LOGIN_CHECK_INTERVAL

            try:

                logged_in = await self.is_logged_in()

            except Exception:

                logged_in = False

            if logged_in:

                print()
                print(
                    "检测到登录状态已经完成。"
                )

                print(
                    "继续采集评论。"
                )

                return True

            # ------------------------------------------------
            # 每 10 秒输出一次状态
            # ------------------------------------------------

            if elapsed % 10 == 0:

                print(
                    f"仍在等待登录..."
                    f" ({elapsed}/"
                    f"{LOGIN_TIMEOUT} 秒)"
                )

        # ----------------------------------------------------
        # 超时
        # ----------------------------------------------------

        print()
        print(
            "等待登录超时。"
        )

        return False

    # ========================================================
    # 处理评论接口
    # ========================================================

    async def handle_response(
        self,
        response
    ):

        url = response.url

        # ----------------------------------------------------
        # 只处理一级评论接口
        # ----------------------------------------------------

        if (
            "/aweme/v1/web/comment/list/"
            not in url
        ):
            return

        # ----------------------------------------------------
        # 排除评论回复接口
        # ----------------------------------------------------

        if (
            "/comment/list/reply/"
            in url
        ):
            return

        try:

            data = await response.json()

        except Exception:

            # 浏览器关闭或者响应已经失效
            return

        page_comments = data.get(
            "comments",
            []
        )

        cursor = data.get(
            "cursor"
        )

        has_more = data.get(
            "has_more"
        )

        # ----------------------------------------------------
        # 更新状态
        # ----------------------------------------------------

        self.last_cursor = cursor

        if has_more is not None:

            self.has_more = bool(
                has_more
            )

        # ----------------------------------------------------
        # 输出接口信息
        # ----------------------------------------------------

        print()
        print("-" * 60)

        print(
            f"评论接口: "
            f"cursor={cursor}, "
            f"count={len(page_comments)}, "
            f"has_more={has_more}"
        )

        new_count = 0

        # ----------------------------------------------------
        # 解析评论
        # ----------------------------------------------------

        for comment in page_comments:

            parsed = parse_comment(
                comment,
                anonymize=self.anonymize
            )

            comment_id = parsed[
                "comment_id"
            ]

            if not comment_id:
                continue

            # ------------------------------------------------
            # 去重
            # ------------------------------------------------

            if comment_id in self.comment_map:
                continue

            self.comment_map[
                comment_id
            ] = parsed

            self.comments.append(
                parsed
            )

            new_count += 1

            print(
                f"[{len(self.comments)}] "
                f"{parsed['nickname']}: "
                f"{parsed['text']}"
            )

            # ------------------------------------------------
            # 最大评论数量
            # ------------------------------------------------

            if (
                self.max_comments
                is not None
                and len(self.comments)
                >= self.max_comments
            ):
                break

        self.last_response_new_count = (
            new_count
        )

        print(
            f"本页新增: {new_count}"
        )

        print(
            f"累计评论: "
            f"{len(self.comments)}"
        )

    # ========================================================
    # 自动滚动
    # ========================================================

    async def scroll_and_collect(self):

        no_new_count = 0

        last_count = len(
            self.comments
        )

        print()
        print("=" * 60)
        print("开始自动滚动采集评论")
        print("=" * 60)

        for i in range(1000):

            # ------------------------------------------------
            # 最大评论数量
            # ------------------------------------------------

            if (
                self.max_comments
                is not None
                and len(self.comments)
                >= self.max_comments
            ):

                print()
                print(
                    "达到最大评论数量。"
                )

                break

            # ------------------------------------------------
            # 已经明确没有下一页
            # ------------------------------------------------

            if self.has_more is False:

                print()
                print(
                    "抖音接口返回 "
                    "has_more=0，"
                    "评论已经到底。"
                )

                break

            print()
            print(
                f"第 {i + 1} 次滚动..."
            )

            # ------------------------------------------------
            # 记录滚动前 cursor
            # ------------------------------------------------

            old_cursor = self.last_cursor

            old_count = len(
                self.comments
            )

            # ------------------------------------------------
            # 滚动页面
            # ------------------------------------------------

            await self.page.mouse.wheel(
                0,
                1000
            )

            # ------------------------------------------------
            # 等待评论接口
            # ------------------------------------------------

            wait_seconds = max(
                0.5,
                SCROLL_WAIT + random.uniform(
                    -SCROLL_JITTER, SCROLL_JITTER
                )
            )

            await self.page.wait_for_timeout(
                int(wait_seconds * 1000)
            )

            # ------------------------------------------------
            # 当前评论数量
            # ------------------------------------------------

            current_count = len(
                self.comments
            )

            # ------------------------------------------------
            # 判断是否获得新评论
            # ------------------------------------------------

            if current_count > last_count:

                new_count = (
                    current_count
                    - last_count
                )

                print(
                    f"新增 "
                    f"{new_count} 条"
                )

                no_new_count = 0

            else:

                no_new_count += 1

                print(
                    f"没有新评论 "
                    f"({no_new_count}/"
                    f"{MAX_NO_NEW_COMMENT})"
                )

            # ------------------------------------------------
            # 更新计数
            # ------------------------------------------------

            last_count = current_count

            # ------------------------------------------------
            # 如果 cursor 发生变化，即使评论没有增加，
            # 也说明接口确实在继续分页。
            #
            # 因此这种情况不能算“没有进展”。
            # ------------------------------------------------

            if (
                self.last_cursor is not None
                and self.last_cursor != old_cursor
            ):

                no_new_count = 0

            # ------------------------------------------------
            # 连续多次没有任何进展
            # ------------------------------------------------

            if (
                no_new_count
                >= MAX_NO_NEW_COMMENT
            ):

                print()
                print(
                    "连续多次没有获得新的评论"
                )

                print(
                    "认为已经到底。"
                )

                break

    # ========================================================
    # 主采集流程
    # ========================================================

    async def run(self):

        print("=" * 60)

        print(
            "DataCapturer - "
            "Douyin Comment Capturer"
        )

        print("=" * 60)

        print()
        print("视频:")

        print(
            self.video_url
        )

        async with async_playwright() as p:

            context = None

            try:

                # ------------------------------------------------
                # 启动 Edge
                # ------------------------------------------------

                print()
                print(
                    "正在启动 "
                    "DataCapturer 专用 Edge..."
                )

                context = (
                    await p.chromium.launch_persistent_context(
                        user_data_dir=EDGE_PROFILE_DIR,
                        channel="msedge",
                        headless=False,
                        viewport={
                            "width": 1280,
                            "height": 720,
                        },
                    )
                )

                # ------------------------------------------------
                # 获取页面
                # ------------------------------------------------

                if context.pages:

                    page = context.pages[0]

                else:

                    page = await context.new_page()

                self.page = page

                # ------------------------------------------------
                # 注册评论接口监听
                # ------------------------------------------------

                page.on(
                    "response",
                    self.handle_response
                )

                # ------------------------------------------------
                # 打开视频
                # ------------------------------------------------

                print()
                print(
                    "正在打开视频..."
                )

                await page.goto(
                    self.video_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                print()
                print(
                    "页面已打开。"
                )

                # ------------------------------------------------
                # 检查登录
                # ------------------------------------------------

                login_ok = await self.wait_for_login()

                if not login_ok:

                    print()
                    print(
                        "未检测到有效登录状态，"
                        "本次采集结束。"
                    )

                    return self.comments

                # ------------------------------------------------
                # 等待评论加载
                # ------------------------------------------------

                print()
                print(
                    "等待评论加载..."
                )

                await page.wait_for_timeout(
                    5000
                )

                # ------------------------------------------------
                # 自动滚动
                # ------------------------------------------------

                await self.scroll_and_collect()

                # ------------------------------------------------
                # 等待最后几个 response
                # ------------------------------------------------

                print()
                print(
                    "等待最后的评论请求完成..."
                )

                await page.wait_for_timeout(
                    2000
                )

                # ------------------------------------------------
                # 保存
                # ------------------------------------------------

                save_comments(
                    self.video_id,
                    self.comments
                )

            finally:

                # ------------------------------------------------
                # 关闭浏览器
                # ------------------------------------------------

                if context is not None:

                    print()
                    print(
                        "关闭浏览器..."
                    )

                    try:

                        await context.close()

                    except Exception:

                        pass

        print()
        print("=" * 60)
        print("采集结束")
        print("=" * 60)

        print(
            "总评论:",
            len(self.comments)
        )

        return self.comments


# ============================================================
# 对外接口
# ============================================================

async def capture_comments(
    video_url,
    max_comments=MAX_COMMENTS,
    anonymize=ANONYMIZE_USERS
):
    """
    采集抖音视频评论。

    参数：

        video_url:
            抖音视频 URL

        max_comments:
            最大评论数量。
            None 表示不限制。

        anonymize:
            是否对评论作者的 user_id / nickname 做哈希脱敏。
            默认为 False（保留原始信息，便于个人本地使用）。
            如果计划保存/分享抓取结果，建议设为 True。

    返回：

        评论列表
    """

    capturer = (
        DouyinCommentCapturer(
            video_url,
            max_comments=max_comments,
            anonymize=anonymize
        )
    )

    return await capturer.run()