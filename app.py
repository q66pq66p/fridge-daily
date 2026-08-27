\
from pathlib import Path
from src.services.fridge_service import FridgeService

IMAGE_PATH = Path("images/test2_fridge02.jpg")


def main():
    service = FridgeService()
    result = service.process_photo(IMAGE_PATH)

    print()
    print("====================================")
    print("Fridge AI 통합 처리 결과")
    print("====================================")
    print(f"photo_id: {result['photo_id']}")
    print(f"YOLO 객체: {len(result['detections'])}")
    print(f"UNKNOWN 후보: {len(result['unknown']['candidates'])}")
    print(f"CONTENT_UNKNOWN: {len(result['content_unknown']['items'])}")
    print("\n====================================")
    print("UNKNOWN Tracking")
    print("====================================")
    for item in result["unknown"]["items"]:
        print(f"UT{item['track_id']:06d} {item['state']:5} score={item['score']:.3f}")

    print("\n====================================")
    print("CONTENT_UNKNOWN Tracking")
    print("====================================")
    for item in result["content_unknown"]["items"]:
        print(
            f"CU{item['track_id']:06d} {item['state']:5} "
            f"{item['container_class']:<25} score={item['score']:.3f}"
        )


    if result["alert_targets"]:
        print()
        print(result["alert_message"])
        print(f"알림 이미지: {result['alert_image']}")
        # Telegram 전송 성공 후에만 아래 호출
        # service.mark_alert_sent(result["alert_targets"])
    else:
        print("현재 알림 대상 없음")


if __name__ == "__main__":
    main()
