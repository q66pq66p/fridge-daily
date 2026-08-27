import os
import asyncio

from dotenv import load_dotenv
from telegram import Bot


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def main():
    if not TOKEN:
        print("오류: TELEGRAM_BOT_TOKEN이 없습니다.")
        return

    bot = Bot(token=TOKEN)

    me = await bot.get_me()

    print("====================================")
    print("Telegram Bot 연결 성공")
    print("====================================")
    print(f"Bot ID   : {me.id}")
    print(f"Bot Name : {me.first_name}")
    print(f"Username : @{me.username}")


if __name__ == "__main__":
    asyncio.run(main())