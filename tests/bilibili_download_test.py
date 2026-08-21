from bilibili.download import download_videos


def main():
    # Test only the first 3 items.
    # Playlist extraction remains lazy; detailed metadata is fetched only
    # when each selected item is about to be downloaded.
    result = download_videos(
        "https://www.bilibili.com/video/BV1Pr4y1F7d4/?spm_id_from=333.337.search-card.all.click",
        output_dir="data/bilibili",
        mode="playlist",
        playlist_items="1-3",
    )

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
