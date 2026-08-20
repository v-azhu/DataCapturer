"""
DataCapturer - 统一命令行入口

用法：
    python main.py

会提示你选择：
    1. 下载视频
    2. 抓取评论
然后输入抖音分享链接/口令即可。
"""

import asyncio

from douyin import capture_comments, download_video


async def run():

    print("=" * 60)
    print("DataCapturer")
    print("=" * 60)
    print()
    print("1. 下载视频")
    print("2. 抓取评论")
    print()

    choice = input("请选择功能 (1/2): ").strip()

    share_text = input(
        "\n请输入抖音分享链接或分享口令:\n> "
    ).strip()

    if choice == "1":
        try:
            filepath = await download_video(share_text)
            print("\n视频已保存到:", filepath)
        except (ValueError, RuntimeError) as e:
            print("\n下载失败:", e)

    elif choice == "2":
        anonymize_input = input(
            "是否对评论作者信息脱敏? (y/N): "
        ).strip().lower()

        anonymize = anonymize_input == "y"

        comments = await capture_comments(
            share_text,
            anonymize=anonymize
        )

        print("\n共采集到评论:", len(comments))

    else:
        print("无效选择")


if __name__ == "__main__":
    asyncio.run(run())
