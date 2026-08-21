from bilibili.download import download_videos


VIDEO_URL = (
    "https://www.bilibili.com/video/"
    "BV1Pr4y1F7d4/?spm_id_from=333.337.search-card.all.click"
)


def main():
    # Test the lazy open-ended playlist range "3-".
    #
    # The downloader should:
    #   1. resolve p=3
    #   2. continue with p=4, p=5, ...
    #   3. stop when the requested playlist reaches its end
    #
    # If you only want to observe the behavior without downloading the
    # whole playlist, press Ctrl+C after several items have been checked.
    result = download_videos(
        VIDEO_URL,
        output_dir="data/bilibili",
        mode="playlist",
        playlist_items="3-",
    )

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
