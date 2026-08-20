import asyncio

from douyin.comment import capture_comments


VIDEO_URL = (
    "https://www.douyin.com/video/"
    "7668904077169790227"
)


async def main():

    comments = await capture_comments(
        VIDEO_URL
    )

    print()
    print("测试完成")
    print("评论数量:", len(comments))


if __name__ == "__main__":
    asyncio.run(main())