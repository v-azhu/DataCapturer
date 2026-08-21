"""
Bilibili downloader.

Supports:
- video mode: download only the video represented by the URL
- playlist mode: download selected playlist items lazily
- playlist ranges: "1-3", "5", "3-", "-3"
- no MP3 conversion
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yt_dlp


DEFAULT_OUTPUT_DIR = Path("data/bilibili")


def _safe_filename(name: str) -> str:
    """Make a Windows-safe filename while preserving Chinese text."""
    name = (name or "").strip()
    if not name:
        return "unknown"

    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(" .")
    return name or "unknown"


def _build_ydl_opts(
    output_template: str,
    *,
    no_playlist: bool = False,
    extract_flat: bool = False,
) -> dict[str, Any]:
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


def _get_info(
    url: str,
    *,
    no_playlist: bool,
    extract_flat: bool = False,
) -> dict[str, Any] | None:
    """Extract metadata without downloading."""
    opts = _build_ydl_opts(
        "%(title)s.%(ext)s",
        no_playlist=no_playlist,
        extract_flat=extract_flat,
    )

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _build_part_url(url: str, part_number: int) -> str:
    """
    Build a Bilibili anthology URL for one specific p=N item.

    Existing query parameters are preserved, while p is replaced.
    """
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)

    # Remove an existing p parameter and replace it with the requested one.
    query = [(key, value) for key, value in query if key.lower() != "p"]
    query.append(("p", str(part_number)))

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _parse_playlist_items(value: str | None) -> tuple[str, int | None, int | None]:
    """
    Parse the supported playlist range forms.

    Returns:
        ("fixed", start, end)
        ("open_end", start, None)

    Supported:
        None / "" -> all, represented as open_end from 1
        "5"       -> item 5 only
        "1-3"     -> items 1 through 3
        "-3"      -> items 1 through 3
        "3-"      -> item 3 through the end

    A comma-separated selector is deliberately not handled here; the
    current downloader's lazy model is based on one contiguous range.
    """
    if value is None or not value.strip():
        return "open_end", 1, None

    text = value.strip()

    if re.fullmatch(r"\d+", text):
        number = int(text)
        if number < 1:
            raise ValueError("playlist_items 中的集数必须 >= 1")
        return "fixed", number, number

    match = re.fullmatch(r"(\d*)\s*-\s*(\d*)", text)
    if not match:
        raise ValueError(
            "playlist_items 只支持：'5'、'1-3'、'-3'、'3-'"
        )

    left, right = match.groups()

    if not left and not right:
        raise ValueError("playlist_items 范围不能为空")

    if not left:
        end = int(right)
        if end < 1:
            raise ValueError("playlist_items 中的集数必须 >= 1")
        return "fixed", 1, end

    start = int(left)
    if start < 1:
        raise ValueError("playlist_items 中的集数必须 >= 1")

    if not right:
        return "open_end", start, None

    end = int(right)
    if end < start:
        raise ValueError("playlist_items 的结束集数不能小于开始集数")

    return "fixed", start, end


def _download_single(url: str, output_path: Path) -> Path | None:
    """Download exactly one video to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"已存在: {output_path}")
        return output_path

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

    candidates = list(output_path.parent.glob(output_path.stem + ".*"))
    candidates = [
        p
        for p in candidates
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


def _resolve_playlist_item(
    url: str,
    part_number: int,
) -> tuple[str, dict[str, Any]] | None:
    """
    Resolve exactly one playlist item.

    No parent playlist extraction is performed. The p=N URL is resolved
    directly with noplaylist=True.
    """
    item_url = _build_part_url(url, part_number)

    print(f"\n解析第 {part_number} 集...")
    print("正在解析B站页面...")

    try:
        info = _get_info(
            item_url,
            no_playlist=True,
            extract_flat=False,
        )
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"获取第 {part_number} 集信息失败: {exc}")
        return None

    if not info:
        return None

    return item_url, info


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
        Supported lazy selectors:
            "1-3" -> items 1 through 3
            "5"   -> item 5
            "-3"  -> items 1 through 3
            "3-"  -> item 3 through the end

        None / "" means the entire playlist, starting from item 1 and
        continuing until the first unavailable item.

    Important:
        Playlist mode NEVER calls extract_info() on the parent playlist.
        Every requested p=N item is resolved independently.
    """
    if mode not in {"video", "playlist"}:
        raise ValueError("mode 必须是 'video' 或 'playlist'")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # video mode
    # ------------------------------------------------------------------
    if mode == "video":
        print("正在解析B站页面...")
        info = _get_info(
            url,
            no_playlist=True,
            extract_flat=False,
        )

        if not info:
            return {
                "success": False,
                "count": 1,
                "downloaded": 0,
                "failed": 1,
                "files": [],
            }

        title = info.get("title") or "unknown_1"
        print("\n下载模式: video")
        print("视频数量: 1")

        print("\n" + "=" * 60)
        print("处理: 1")
        print(title)

        filename = f"01_{_safe_filename(str(title))}.mp4"
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

    # ------------------------------------------------------------------
    # playlist mode
    # ------------------------------------------------------------------
    selector_type, start, end = _parse_playlist_items(playlist_items)

    print(f"\n下载模式: playlist")
    if playlist_items:
        print(f"下载范围: {playlist_items}")
    else:
        print("下载范围: 全部")
    if selector_type == "fixed":
        assert start is not None
        assert end is not None
        print(f"视频数量: {end - start + 1}")
    else:
        print("视频数量: 从开始集数逐集解析")

    downloaded_files: list[str] = []
    failed = 0
    attempted = 0

    assert start is not None
    current = start

    while True:
        if selector_type == "fixed":
            assert end is not None
            if current > end:
                break

        resolved = _resolve_playlist_item(url, current)

        # For open-ended ranges, the first unavailable item marks the end
        # of the playlist. For a fixed range, it is a real failure.
        if resolved is None:
            if selector_type == "open_end":
                print(f"\n第 {current} 集不存在或无法解析，结束 playlist。")
                break

            print("\n" + "=" * 60)
            print(f"处理: {current}")
            print(f"第 {current} 集无法解析")
            failed += 1
            attempted += 1
            current += 1
            continue

        item_url, detail = resolved
        attempted += 1

        print("\n" + "=" * 60)
        print(f"处理: {current}")

        title = detail.get("title") or f"unknown_{current}"
        title = str(title)
        print(title)

        filename = f"{current:02d}_{_safe_filename(title)}.mp4"
        output_path = output_dir / filename

        print(f"\n下载: {filename}")
        result = _download_single(item_url, output_path)

        if result:
            print(f"完成: {result}")
            downloaded_files.append(
                str(result).replace("/", os.sep)
            )
        else:
            failed += 1

        current += 1

    # A playlist ending naturally with zero successful items is not a
    # successful download operation.
    success = failed == 0 and len(downloaded_files) > 0

    print("\n" + "=" * 60)
    print("下载完成")
    print("总数:", attempted)
    print("成功:", len(downloaded_files))
    print("失败:", failed)

    return {
        "success": success,
        "count": attempted,
        "downloaded": len(downloaded_files),
        "failed": failed,
        "files": downloaded_files,
    }
