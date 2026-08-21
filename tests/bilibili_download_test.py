from bilibili.download import download_videos


VIDEO_URL = (
    "https://www.bilibili.com/video/BV1Pr4y1F7d4/?spm_id_from=333.337.search-card.all.click"
)


def main():

    result = download_videos(
        VIDEO_URL,

        # ----------------------------------------------------
        # video:
        #     只下载当前视频
        #
        # playlist:
        #     下载整个合集
        # ----------------------------------------------------

        download_mode="video",

        output_dir="data/bilibili"
    )

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

    print(result)


if __name__ == "__main__":

    main()