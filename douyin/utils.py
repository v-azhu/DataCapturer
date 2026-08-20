"""
douyin/utils.py

共享的 URL 处理工具：
- 从分享文本中提取抖音短链接 / 视频链接
- 解析短链接跳转后的最终 URL
- 从最终 URL 中提取 video_id

这些函数被 download.py 和 comment.py 共用，避免重复实现。
"""

import re

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
)

SHORT_LINK_PATTERN = r"https?://v\.douyin\.com/[A-Za-z0-9_-]+/?"
FULL_VIDEO_PATTERN = r"https?://(?:www\.)?douyin\.com/video/\d+"
VIDEO_ID_PATTERNS = [
    r"/share/video/(\d+)",
    r"/video/(\d+)",
]


def extract_douyin_url(text: str) -> str | None:
    """
    从分享口令/文本中提取抖音链接。

    优先匹配短链接（v.douyin.com），
    如果没有则尝试匹配完整视频链接。
    """

    match = re.search(SHORT_LINK_PATTERN, text)
    if match:
        return match.group(0)

    match = re.search(FULL_VIDEO_PATTERN, text)
    if match:
        return match.group(0)

    return None


def resolve_share_url(url: str, timeout: int = 20) -> str:
    """
    跟随短链接跳转，获取最终 URL。

    如果传入的已经是完整链接（不含跳转），
    requests 也会直接返回原地址，不会报错。
    """

    headers = {"User-Agent": USER_AGENT}

    response = requests.get(
        url,
        headers=headers,
        allow_redirects=True,
        timeout=timeout,
    )
    response.raise_for_status()

    return response.url


def extract_video_id(url: str) -> str | None:
    """
    从 URL 中提取 video_id。
    """

    for pattern in VIDEO_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None
