"""
Bilibili downloader.

Supports:
- video mode: download only the video represented by the URL
- playlist mode: download selected playlist items lazily
- no MP3 conversion
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yt_dlp


DEFAULT_OUTPUT_DIR = Path("data/bilibili")


def _safe_filename(name: str) -> str:
    """Make a Windows-safe filename while preserving Chinese text."""
    name = (name or "").strip()
    if not name:
        return "unknown"

    # Windows forbidden characters.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(" .")
    return name or "unknown"


def _build_ydl_opts(output_template: str, *, no_playlist: bool = False,
                    extract_flat: bool = False) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": no_playlist,
        "quiet": False,
        "no_warnings": False,
    }

    if extract_flat:
        opts["extract_flat"] = True

    return opts


def _get_info(url: str, *, no_playlist: bool, extract_flat: bool = False) -> dict[str, Any]:
    """
    Extract metadata without downloading.

    In playlist mode extract_flat=True prevents yt-dlp from opening every
    playlist entry just to collect metadata.
    """
    opts = _build_ydl_opts(
        "%(title)s.%(ext)s",
        no_playlist=no_playlist,
        extract_flat=extract_flat,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _entry_url(entry: dict[str, Any]) -> str | None:
    """Return a directly usable URL for a flat playlist entry."""
    url = entry.get("webpage_url") or entry.get("original_url")
    if url:
        return url

    url = entry.get("url")
    if not url:
        return None

    # Bilibili flat entries commonly provide the BV id as url.
    if str(url).startswith(("BV", "av")):
        return f"https://www.bilibili.com/video/{url}"

    return str(url)


def _entry_title(entry: dict[str, Any], fallback_index: int) -> str:
    title = entry.get("title")
    if title:
        return str(title)

    return f"unknown_{fallback_index}"


def _download_single(url: str, output_path: Path) -> Path | None:
    """Download exactly one video to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"已存在: {output_path}")
        return output_path

    # %(ext)s is replaced by yt-dlp; merge_output_format ensures mp4.
    stem = str(output_path.with_suffix(""))
    opts = _build_ydl_opts(
        stem + ".%(ext)s",
        no_playlist=True,
    )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"下载失败: {exc}")
        return None

    if output_path.exists():
        return output_path

    # Some yt-dlp versions may choose another final extension.
    candidates = list(output_path.parent.glob(output_path.stem + ".*"))
    candidates = [
        p for p in candidates
        if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
    ]
    if candidates:
        return candidates[0]

    return None


def download_video(
    url: str,
    output_path: str | Path,
) -> str | None:
    """
    Download one Bilibili video.

    The URL is forced into video mode so a multi-part Bilibili anthology
    does not accidentally download the entire playlist.
    """
    path = Path(output_path)
    result = _download_single(url, path)
    return str(result) if result else None


def download_videos(
    url: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    mode: str = "video",
    playlist_items: str | None = None,
) -> dict[str, Any]:
    """
    Download Bilibili video(s).

    Parameters
    ----------
    url:
        Bilibili video/playlist URL.
    output_dir:
        Destination directory.
    mode:
        "video"    -> current video only
        "playlist" -> selected playlist entries
    playlist_items:
        yt-dlp playlist selector, e.g. "1-3", "5", "1,3,5".
        None means the entire playlist.

    Important:
        playlist mode uses extract_flat=True during the initial extraction.
        This means yt-dlp does NOT fully parse all playlist entries.
        Detailed metadata is fetched only for entries that are actually
        selected for download.
    """
    if mode not in {"video", "playlist"}:
        raise ValueError("mode 必须是 'video' 或 'playlist'")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("正在解析B站页面...")

    if mode == "video":
        info = _get_info(url, no_playlist=True, extract_flat=False)

        title = info.get("title") or "unknown_1"
        print("\n下载模式: video")
        print("视频数量: 1")

        print("\n" + "=" * 60)
        print("处理: 1")
        print(title)

        filename = f"01_{_safe_filename(title)}.mp4"
        output_path = output_dir / filename

        print(f"\n下载: {filename}")
        result = _download_single(url, output_path)

        if result:
            print(f"完成: {result}")
            return {
                "success": True,
                "count": 1,
                "downloaded": 1,
                "failed": 0,
                "files": [str(result).replace("/", os.sep)],
            }

        return {
            "success": False,
            "count": 1,
            "downloaded": 0,
            "failed": 1,
            "files": [],
        }

    # playlist mode ---------------------------------------------------------
    # The initial extraction is flat. This is the key to avoiding the
    # previous "parse all 73 videos first" behavior.
    opts = _build_ydl_opts(
        "%(title)s.%(ext)s",
        no_playlist=False,
        extract_flat=True,
    )
    if playlist_items:
        opts["playlist_items"] = playlist_items

    with yt_dlp.YoutubeDL(opts) as ydl:
        playlist_info = ydl.extract_info(url, download=False)

    entries = [
        e for e in (playlist_info.get("entries") or [])
        if e
    ]

    print(f"\n下载模式: playlist")
    if playlist_items:
        print(f"下载范围: {playlist_items}")
    else:
        print("下载范围: 全部")
    print(f"视频数量: {len(entries)}")

    downloaded_files: list[str] = []
    failed = 0

    for index, entry in enumerate(entries, start=1):
        # IMPORTANT:
        # The flat entry normally has no full title. Resolve metadata NOW,
        # one selected video at a time. We do not touch unselected entries.
        entry_url = _entry_url(entry)
        if not entry_url:
            print(f"\n处理: {index}")
            print("无法确定视频URL")
            failed += 1
            continue

        print("\n" + "=" * 60)
        print(f"处理: {index}")

        # Fetch full metadata only for this selected entry.
        try:
            detail = _get_info(
                entry_url,
                no_playlist=True,
                extract_flat=False,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"获取视频信息失败: {exc}")
            detail = entry

        title = _entry_title(detail, index)
        print(title)

        filename = f"{index:02d}_{_safe_filename(title)}.mp4"
        output_path = output_dir / filename

        print(f"\n下载: {filename}")
        result = _download_single(entry_url, output_path)

        if result:
            print(f"完成: {result}")
            downloaded_files.append(str(result).replace("/", os.sep))
        else:
            failed += 1

    return {
        "success": failed == 0,
        "count": len(entries),
        "downloaded": len(downloaded_files),
        "failed": failed,
        "files": downloaded_files,
    }
