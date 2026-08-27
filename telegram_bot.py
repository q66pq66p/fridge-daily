import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.services.fridge_service import FridgeService


# ============================================================
# 기본 설정
# ============================================================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BASE_DIR = Path(__file__).resolve().parent
TELEGRAM_IMAGE_DIR = BASE_DIR / "images" / "telegram"
TELEGRAM_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# YOLO 모델을 메시지마다 다시 로딩하지 않도록 한 번만 생성
fridge_service = FridgeService()

# 동시에 여러 사진 분석 방지
analysis_lock = asyncio.Lock()


# ============================================================
# /start
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "냉장고 관리 Bot입니다.\n\n"
        "냉장고 내부 사진을 보내주세요.\n"
        "사진을 분석하여 오래 보관되고 있는 "
        "알 수 없는 식재료를 확인합니다."
    )


# ============================================================
# 사진 처리
# ============================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.photo:
        return

    # Telegram은 여러 해상도의 PhotoSize를 제공하므로
    # 가장 큰 이미지를 선택
    photo = update.message.photo[-1]

    now = datetime.now()

    filename = (
        f"fridge_"
        f"{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    )

    image_path = TELEGRAM_IMAGE_DIR / filename

    await update.message.reply_text(
        "📷 냉장고 사진을 받았습니다.\n"
        "분석을 시작합니다. 잠시 기다려주세요."
    )

    try:
        telegram_file = await photo.get_file()

        await telegram_file.download_to_drive(
            custom_path=str(image_path)
        )

        logger.info(
            "Telegram image saved: %s",
            image_path,
        )

        # ----------------------------------------------------
        # YOLO 처리는 동기 함수이며 시간이 오래 걸리므로
        # Telegram event loop와 별도 thread에서 실행
        # ----------------------------------------------------

        async with analysis_lock:

            result = await asyncio.to_thread(
                fridge_service.process_photo,
                image_path,
            )

        # ----------------------------------------------------
        # 분석 결과
        # ----------------------------------------------------

        yolo_count = len(result["detections"])

        unknown_count = len(
            result["unknown"]["candidates"]
        )

        content_unknown_count = len(
            result["content_unknown"]["items"]
        )

        logger.info(
            "photo_id=%s yolo=%s unknown=%s "
            "content_unknown=%s",
            result["photo_id"],
            yolo_count,
            unknown_count,
            content_unknown_count,
        )

        # ----------------------------------------------------
        # 장기보관 대상 있음
        # ----------------------------------------------------

        if result["alert_targets"]:

            message = result["alert_message"]

            alert_image = result["alert_image"]

            with open(alert_image, "rb") as image_file:

                await update.message.reply_photo(
                    photo=image_file,
                    caption=message,
                )

            # Telegram 전송에 성공한 후에만
            # alert_history 등록
            fridge_service.mark_alert_sent(
                result["alert_targets"]
            )

        # ----------------------------------------------------
        # 장기보관 대상 없음
        # ----------------------------------------------------

        else:

            await update.message.reply_text(
                "✅ 냉장고 사진 분석이 완료되었습니다.\n\n"
                f"검출 객체: {yolo_count}개\n"
                f"알 수 없는 후보: {unknown_count}개\n"
                f"내용물 미확인 용기: "
                f"{content_unknown_count}개\n\n"
                "현재 장기보관 경고 대상은 없습니다."
            )

    except Exception:

        logger.exception(
            "냉장고 사진 처리 중 오류 발생"
        )

        await update.message.reply_text(
            "❌ 냉장고 사진 분석 중 오류가 발생했습니다.\n"
            "프로그램 로그를 확인해주세요."
        )


# ============================================================
# 일반 메시지
# ============================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "냉장고 내부 사진을 보내주세요."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN이 설정되어 있지 않습니다."
        )

    print("====================================")
    print("Fridge AI Telegram Bot")
    print("====================================")
    print("Bot 시작...")
    print("냉장고 사진을 Telegram으로 보내주세요.")
    print()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()