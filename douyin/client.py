"""
douyin/client.py

统一的“打开视频页面、监听 aweme/detail 接口”逻辑。
之前这部分代码在 tests/browser_test.py 和 tests/mainfunctest.py
里各写了一遍，这里合并成一个共用函数。
"""

from playwright.async_api import async_playwright

from .utils import USER_AGENT

AWEME_DETAIL_PATH = "aweme/v1/web/aweme/detail"


async def fetch_aweme_detail(
    video_id: str,
    headless: bool = True,
    wait_ms: int = 8000,
    timeout_ms: int = 60000,
) -> dict | None:
    """
    打开抖音视频页面，监听 aweme/detail 接口，返回其 JSON。

    参数：
        video_id:  抖音视频 ID
        headless:  是否使用无头浏览器
        wait_ms:   页面打开后额外等待接口返回的时间
        timeout_ms: 页面导航超时时间

    返回：
        接口返回的 JSON（dict），如果没有捕获到则返回 None
    """

    target_url = f"https://www.douyin.com/video/{video_id}"
    result: dict | None = None

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(user_agent=USER_AGENT)

        async def handle_response(response):
            nonlocal result

            if AWEME_DETAIL_PATH not in response.url:
                return

            try:
                result = await response.json()
            except Exception:
                # 响应可能已经失效或者不是合法 JSON，忽略即可
                pass

        page.on("response", handle_response)

        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            await page.wait_for_timeout(wait_ms)
        except Exception as e:
            print("页面加载异常:", e)
        finally:
            await browser.close()

    return result
