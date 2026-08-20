import re
import requests
from playwright.sync_api import sync_playwright


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
)


def extract_douyin_url(text):
    """
    从分享口令/文本中提取抖音短链接
    """
    pattern = r'https?://v\.douyin\.com/[A-Za-z0-9]+/?'
    match = re.search(pattern, text)

    if match:
        return match.group(0)

    return None


def resolve_url(url):
    """
    跟随抖音短链接跳转，获取最终 URL
    """
    headers = {
        "User-Agent": USER_AGENT
    }

    print("正在解析跳转地址...")

    response = requests.get(
        url,
        headers=headers,
        allow_redirects=True,
        timeout=20
    )

    print("HTTP:", response.status_code)
    print("最终 URL:")
    print(response.url)

    return response.url


def extract_video_id(url):
    """
    从 URL 中提取 video_id
    """
    patterns = [
        r'/share/video/(\d+)',
        r'/video/(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def get_video_info(video_id):
    """
    使用 Playwright 打开真实抖音页面，
    监听 aweme/detail 接口获取视频 JSON。
    """

    target_url = f"https://www.douyin.com/video/{video_id}"

    print()
    print("正在使用浏览器打开视频页面...")
    print(target_url)

    result = None

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent=USER_AGENT
        )

        def handle_response(response):

            nonlocal result

            url = response.url

            if "aweme/v1/web/aweme/detail" not in url:
                return

            print()
            print("捕获到视频详情接口:")
            print(url)

            try:

                data = response.json()

                print("JSON OK")

                result = data

            except Exception as e:

                print("JSON 解析失败:")
                print(e)

        page.on("response", handle_response)

        try:

            page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            # 给抖音一些时间加载接口
            page.wait_for_timeout(8000)

        except Exception as e:

            print()
            print("页面加载异常:")
            print(e)

        browser.close()

    return result


def extract_mp4_url(data):
    """
    从 aweme_detail 中提取视频播放 URL
    """

    aweme_detail = data.get("aweme_detail")

    if not aweme_detail:
        print("没有找到 aweme_detail")
        return None

    video = aweme_detail.get("video")

    if not video:
        print("没有找到 video")
        return None

    play_addr = video.get("play_addr")

    if not play_addr:
        print("没有找到 play_addr")
        return None

    url_list = play_addr.get("url_list", [])

    if not url_list:
        print("没有找到视频 URL")
        return None

    print()
    print("找到视频 URL 数量:", len(url_list))

    for i, url in enumerate(url_list):
        print(f"[{i}] {url}")

    # 优先选择真正的视频 MP4 地址
    for url in url_list:

        if "mime_type=video_mp4" in url.lower():
            return url

    # 备用：如果没有 mime_type，则选择 douyinvod CDN
    for url in url_list:

        if "douyinvod.com" in url.lower():
            return url

    # 最后再返回第一个
    return url_list[0]
def download_video(video_url, video_id):
    """
    下载 MP4
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.douyin.com/",
    }

    filename = f"{video_id}.mp4"

    print()
    print("开始下载:")
    print(filename)

    response = requests.get(
        video_url,
        headers=headers,
        stream=True,
        timeout=60
    )

    print("HTTP:", response.status_code)

    response.raise_for_status()

    total = 0

    with open(filename, "wb") as f:

        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):

            if chunk:

                f.write(chunk)

                total += len(chunk)

                print(
                    f"\r已下载: "
                    f"{total / 1024 / 1024:.2f} MB",
                    end=""
                )

    print()
    print()
    print("下载完成:")
    print(filename)


def main():

    print("=" * 50)
    print("DataCapturer")
    print("=" * 50)

    text = input(
        "请输入抖音分享链接或分享口令:\n> "
    )

    douyin_url = extract_douyin_url(text)

    if not douyin_url:

        print("没有找到抖音分享链接")
        return

    print()
    print("找到 URL:")
    print(douyin_url)

    final_url = resolve_url(douyin_url)

    video_id = extract_video_id(final_url)

    if not video_id:

        print("无法提取视频 ID")
        return

    print()
    print("视频 ID:")
    print(video_id)

    # ----------------------------------
    # 使用 Playwright 获取视频详情
    # ----------------------------------

    data = get_video_info(video_id)

    if not data:

        print()
        print("没有捕获到 aweme/detail 数据")
        return

    # ----------------------------------
    # 提取 MP4 URL
    # ----------------------------------

    mp4_url = extract_mp4_url(data)

    if not mp4_url:

        print()
        print("没有成功获取 MP4 URL")
        return

    print()
    print("选择的 MP4 URL:")
    print(mp4_url)

    # ----------------------------------
    # 下载
    # ----------------------------------

    download_video(
        mp4_url,
        video_id
    )


if __name__ == "__main__":
    main()