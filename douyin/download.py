"""
douyin/download.py

抖音视频下载模块。

对外接口:
    download_video(share_text) -> str (保存的文件路径)

内部流程:
    分享文本 -> 短链接 -> 跳转后的真实 URL -> video_id
    -> 打开页面监听 aweme/detail -> 提取 mp4 URL -> 下载
"""

import asyncio
import os

import requests

from .client import fetch_aweme_detail
from .utils import USER_AGENT, extract_douyin_url, extract_video_id, resolve_share_url

OUTPUT_DIR = "data/downloads"


def extract_mp4_url(data: dict) -> str | None:
    """
    从 aweme_detail JSON 中提取视频播放 URL。
    """

    aweme_detail = (data or {}).get("aweme_detail")
    if not aweme_detail:
        print("没有找到 aweme_detail")
        return None

    video = aweme_detail.get("video")
    if not video:
        print("没有找到 video 字段")
        return None

    play_addr = video.get("play_addr")
    if not play_addr:
        print("没有找到 play_addr")
        return None

    url_list = play_addr.get("url_list", [])
    if not url_list:
        print("没有找到视频 URL")
        return None

    # 优先选择明确标注为 mp4 的地址
    for url in url_list:
        if "mime_type=video_mp4" in url.lower():
            return url

    # 备用：douyinvod CDN 地址
    for url in url_list:
        if "douyinvod.com" in url.lower():
            return url

    return url_list[0]


def _download_file(video_url: str, video_id: str, output_dir: str) -> str:
    """
    同步下载 MP4 文件（带重试）。
    """

    os.makedirs(output_dir, exist_ok=True)

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.douyin.com/",
    }

    filepath = os.path.join(output_dir, f"{video_id}.mp4")

    last_error = None

    for attempt in range(1, 4):
        try:
            response = requests.get(
                video_url,
                headers=headers,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            total = 0
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        print(
                            f"\r已下载: {total / 1024 / 1024:.2f} MB",
                            end="",
                        )

            print()
            return filepath

        except Exception as e:
            last_error = e
            print(f"\n下载失败（第 {attempt}/3 次）: {e}")

    raise RuntimeError(f"下载失败，已重试 3 次: {last_error}")


async def download_video(share_text: str, output_dir: str = OUTPUT_DIR) -> str:
    """
    从抖音分享文本/链接下载视频。

    参数：
        share_text: 分享口令，或直接的抖音链接
        output_dir: 保存目录

    返回：
        保存后的文件路径

    抛出：
        ValueError: 无法解析链接 / video_id / mp4 地址
        RuntimeError: 下载失败
    """

    url = extract_douyin_url(share_text)
    if not url:
        raise ValueError("没有在输入内容中找到有效的抖音链接")

    final_url = resolve_share_url(url)

    video_id = extract_video_id(final_url)
    if not video_id:
        raise ValueError(f"无法从 URL 中提取视频 ID: {final_url}")

    print("视频 ID:", video_id)

    data = await fetch_aweme_detail(video_id)
    if not data:
        raise ValueError("没有捕获到 aweme/detail 数据（可能是网络问题或页面结构变化）")

    mp4_url = extract_mp4_url(data)
    if not mp4_url:
        raise ValueError("没有能提取到视频播放地址")

    # requests 是阻塞调用，放到线程池里跑，避免卡住 event loop
    filepath = await asyncio.to_thread(
        _download_file, mp4_url, video_id, output_dir
    )

    print("下载完成:", filepath)
    return filepath
