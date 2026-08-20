import re
import json
from playwright.sync_api import sync_playwright


def extract_video_urls(obj):
    """
    递归搜索 JSON 中可能存在的视频 URL。
    """
    urls = []

    if isinstance(obj, dict):
        for key, value in obj.items():

            # 常见的视频 URL 字段
            if key in (
                "url",
                "url_list",
                "play_addr",
                "download_addr",
                "play_url",
            ):
                urls.extend(extract_video_urls(value))
            else:
                urls.extend(extract_video_urls(value))

    elif isinstance(obj, list):
        for item in obj:
            urls.extend(extract_video_urls(item))

    elif isinstance(obj, str):
        if (
            obj.startswith("http://")
            or obj.startswith("https://")
        ):
            if (
                "douyinvod.com" in obj
                or "zjcdn.com" in obj
                or "douyinstatic.com" in obj
            ):
                urls.append(obj)

    return urls


def main():

    share_text = input("请输入抖音分享链接或分享口令:\n> ").strip()

    # 从分享口令中提取 v.douyin.com URL
    match = re.search(
        r"https?://v\.douyin\.com/[A-Za-z0-9_-]+/?",
        share_text
    )

    if match:
        url = match.group(0)
    else:
        # 如果直接输入的是普通视频 URL
        match = re.search(
            r"https?://(?:www\.)?douyin\.com/video/\d+",
            share_text
        )

        if not match:
            print("没有找到有效的抖音 URL")
            return

        url = match.group(0)

    print()
    print("=" * 60)
    print("打开:")
    print(url)
    print("=" * 60)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        found = {
            "detail": False,
            "video_urls": []
        }

        def handle_response(response):

            response_url = response.url

            # 只关心 aweme/detail
            if "/aweme/v1/web/aweme/detail/" not in response_url:
                return

            print()
            print("=" * 60)
            print("发现 aweme/detail")
            print("=" * 60)

            print("HTTP:", response.status)

            found["detail"] = True

            try:
                data = response.json()

            except Exception as e:
                print("JSON 解析失败:")
                print(e)
                return

            print("JSON OK")

            # 保存一份简单结构信息
            if isinstance(data, dict):

                print("顶层字段:")
                print(list(data.keys())[:20])

                aweme_detail = data.get("aweme_detail")

                if aweme_detail:

                    print()
                    print("找到 aweme_detail")

                    desc = aweme_detail.get("desc", "")

                    if desc:
                        print()
                        print("视频标题:")
                        print(desc)

                    urls = extract_video_urls(
                        aweme_detail
                    )

                    # 去重
                    urls = list(dict.fromkeys(urls))

                    found["video_urls"] = urls

                    print()
                    print("找到视频 URL 数量:", len(urls))

                    for i, video_url in enumerate(urls, 1):

                        print()
                        print(f"[{i}]")
                        print(video_url)

                else:
                    print("没有找到 aweme_detail")

            else:
                print("返回结果不是 dict")

        page.on(
            "response",
            handle_response
        )

        try:

            print()
            print("正在打开页面...")

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print("页面已经打开。")

            print()
            print("等待页面加载 API...")

            # 给抖音一点时间完成 JS 初始化和 API 请求
            page.wait_for_timeout(15000)

        except Exception as e:

            print()
            print("打开页面失败:")
            print(e)

        print()
        print("=" * 60)
        print("结果")
        print("=" * 60)

        if found["detail"]:

            print("aweme/detail: OK")

        else:

            print("aweme/detail: 未捕获")

        if found["video_urls"]:

            print(
                "视频 URL:",
                found["video_urls"][0]
            )

        else:

            print("视频 URL: 未找到")

        print()
        print("按 Enter 关闭浏览器...")

        input()

        browser.close()


if __name__ == "__main__":
    main()