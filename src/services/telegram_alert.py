\
async def send_fridge_alert(bot, chat_id, result, fridge_service):
    """
    python-telegram-bot의 Bot 객체를 받아 경고를 전송한다.
    실제 전송 성공 후 alert_history를 기록한다.
    """
    if not result.get("alert_targets"):
        return False

    with open(result["alert_image"], "rb") as image_file:
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_file,
            caption=result["alert_message"],
        )

    fridge_service.mark_alert_sent(result["alert_targets"])
    return True
