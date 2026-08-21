import os

import yt_dlp


# ============================================================
# 配置
# ============================================================

DEFAULT_OUTPUT_DIR = "data/bilibili"

# 下载模式
#
# video:
#     只下载 URL 当前指向的视频
#
# playlist:
#     下载 URL 所在合集的全部视频
#
DEFAULT_DOWNLOAD_MODE = "video"


# ============================================================
# 工具函数
# ============================================================

def clean_filename(name):
    """
    清理 Windows 文件名中的非法字符。
    """

    bad = '\\/:*?"<>|'

    for char in bad:
        name = name.replace(char, "_")

    return name.strip()


# ============================================================
# 获取视频信息
# ============================================================

def get_video_info(url, download_mode="video"):
    """
    获取 B 站视频信息。

    download_mode:
        video:
            只获取当前视频

        playlist:
            获取当前视频所在合集的全部视频
    """

    if download_mode not in ("video", "playlist"):
        raise ValueError(
            f"不支持的 download_mode: {download_mode}"
        )

    print("正在解析B站页面...")

    opts = {
        "extract_flat": False,
        "quiet": False,
        "ignoreerrors": True,
    }

    # --------------------------------------------------------
    # video 模式
    #
    # 不主动展开合集，只处理当前 URL 对应的视频。
    # --------------------------------------------------------

    if download_mode == "video":

        opts["noplaylist"] = True

    # --------------------------------------------------------
    # playlist 模式
    #
    # 允许 yt-dlp 获取当前 URL 所在合集。
    # --------------------------------------------------------

    else:

        opts["noplaylist"] = False

    with yt_dlp.YoutubeDL(opts) as ydl:

        info = ydl.extract_info(
            url,
            download=False
        )

    return info


# ============================================================
# 获取待下载视频列表
# ============================================================

def get_entries(info, download_mode="video"):
    """
    根据 download_mode 将解析结果转换成统一的视频列表。
    """

    if not info:
        return []

    # --------------------------------------------------------
    # 单视频
    # --------------------------------------------------------

    if download_mode == "video":

        return [info]

    # --------------------------------------------------------
    # 合集
    # --------------------------------------------------------

    entries = info.get("entries")

    if not entries:

        return [info]

    return [
        entry
        for entry in entries
        if entry
    ]


# ============================================================
# 获取视频 URL
# ============================================================

def get_video_url(video_info):
    """
    从 yt-dlp 返回的信息中获取实际网页 URL。
    """

    url = video_info.get("webpage_url")

    if url:
        return url

    url = video_info.get("original_url")

    if url:
        return url

    url = video_info.get("url")

    if not url:
        return None

    # --------------------------------------------------------
    # 某些情况下 yt-dlp 返回 BV 号
    # --------------------------------------------------------

    if not url.startswith("http"):

        return (
            "https://www.bilibili.com/video/"
            + url
        )

    return url


# ============================================================
# 下载单个视频
# ============================================================

def download_video(
    url,
    filename,
    output_dir=DEFAULT_OUTPUT_DIR
):
    """
    下载单个 B 站视频。

    返回：
        成功：MP4 文件路径
        失败：None
    """

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    mp4 = os.path.join(
        output_dir,
        filename + ".mp4"
    )

    # --------------------------------------------------------
    # 已经存在
    # --------------------------------------------------------

    if os.path.exists(mp4):

        print(
            "已存在:",
            mp4
        )

        return mp4

    print()
    print(
        "下载:",
        filename
    )

    opts = {
        "outtmpl": mp4,

        # 最佳音视频
        "format": "bestvideo+bestaudio/best",

        # 合并为 MP4
        "merge_output_format": "mp4",

        # 单个视频失败时不要让 yt-dlp 继续
        # 把错误吞掉，我们自己处理异常。
        "ignoreerrors": False,
    }

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            result = ydl.download(
                [url]
            )

    except Exception as exc:

        print()
        print(
            "下载失败:",
            exc
        )

        return None

    # --------------------------------------------------------
    # yt-dlp 返回非 0
    # --------------------------------------------------------

    if result not in (None, 0):

        print()
        print(
            "下载失败，yt-dlp 返回码:",
            result
        )

        return None

    # --------------------------------------------------------
    # 最终确认文件存在
    # --------------------------------------------------------

    if not os.path.exists(mp4):

        print()
        print(
            "下载完成，但没有找到输出文件:",
            mp4
        )

        return None

    print(
        "完成:",
        mp4
    )

    return mp4


# ============================================================
# 批量下载
# ============================================================

def download_videos(
    url,
    download_mode=DEFAULT_DOWNLOAD_MODE,
    output_dir=DEFAULT_OUTPUT_DIR
):
    """
    下载 B 站视频。

    参数：

        url:
            B站视频 URL / 合集 URL

        download_mode:
            "video"
                只下载当前视频

            "playlist"
                下载整个合集

        output_dir:
            输出目录

    返回：

        {
            "success": True/False,
            "count": 总视频数,
            "downloaded": 成功数量,
            "failed": 失败数量,
            "files": [...]
        }
    """

    if download_mode not in (
        "video",
        "playlist"
    ):

        raise ValueError(
            "download_mode 必须是 "
            "'video' 或 'playlist'"
        )

    # --------------------------------------------------------
    # 初始化结果
    # --------------------------------------------------------

    result = {
        "success": False,
        "count": 0,
        "downloaded": 0,
        "failed": 0,
        "files": [],
    }

    # --------------------------------------------------------
    # 解析
    # --------------------------------------------------------

    try:

        info = get_video_info(
            url,
            download_mode=download_mode
        )

    except Exception as exc:

        print()
        print(
            "无法获取视频信息:",
            exc
        )

        result["failed"] = 1

        return result

    if not info:

        print()
        print(
            "无法获取视频信息"
        )

        result["failed"] = 1

        return result

    # --------------------------------------------------------
    # 获取视频列表
    # --------------------------------------------------------

    entries = get_entries(
        info,
        download_mode=download_mode
    )

    if not entries:

        print()
        print(
            "没有找到可下载的视频"
        )

        result["failed"] = 1

        return result

    result["count"] = len(entries)

    print()
    print(
        "下载模式:",
        download_mode
    )

    print(
        "视频数量:",
        len(entries)
    )

    print()

    # --------------------------------------------------------
    # 逐个下载
    # --------------------------------------------------------

    for index, video in enumerate(
        entries,
        1
    ):

        print()
        print(
            "=" * 60
        )

        print(
            "处理:",
            index
        )

        # ----------------------------------------------------
        # 标题
        # ----------------------------------------------------

        title = video.get(
            "title",
            f"unknown_{index}"
        )

        title = clean_filename(
            title
        )

        print(
            title
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        video_url = get_video_url(
            video
        )

        if not video_url:

            print(
                "无URL，跳过"
            )

            result["failed"] += 1

            continue

        # ----------------------------------------------------
        # 文件名
        # ----------------------------------------------------

        filename = (
            f"{index:02d}_{title}"
        )

        # ----------------------------------------------------
        # 下载
        # ----------------------------------------------------

        try:

            mp4 = download_video(
                video_url,
                filename,
                output_dir=output_dir
            )

        except Exception as exc:

            print()
            print(
                "处理失败:",
                exc
            )

            mp4 = None

        # ----------------------------------------------------
        # 判断结果
        # ----------------------------------------------------

        if mp4:

            result["downloaded"] += 1

            result["files"].append(
                mp4
            )

        else:

            result["failed"] += 1

    # --------------------------------------------------------
    # 最终状态
    # --------------------------------------------------------

    result["success"] = (
        result["failed"] == 0
        and result["downloaded"] > 0
    )

    print()
    print(
        "=" * 60
    )

    print(
        "下载完成"
    )

    print(
        "总数:",
        result["count"]
    )

    print(
        "成功:",
        result["downloaded"]
    )

    print(
        "失败:",
        result["failed"]
    )

    return result