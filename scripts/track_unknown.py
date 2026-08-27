
from datetime import datetime
from pathlib import Path
import cv2

from config import RESULT_DIR, UNKNOWN_MATCH_THRESHOLD
from src.database import FridgeDatabase
from src.services.unknown_tracking_service import UnknownTrackingService

try:
    from src.vision_detector import VisionDetector
except ModuleNotFoundError as exc:
    raise SystemExit(
        "src/vision_detector.py가 필요합니다. 기존 VisionDetector 소스를 프로젝트의 src/에 복사하세요."
    ) from exc

IMAGE_PATH = Path("images/test2_fridge03.jpg")
RESULT_PATH = RESULT_DIR / "unknown_tracking.jpg"


def main():
    db = FridgeDatabase()
    db.initialize()

    image = cv2.imread(str(IMAGE_PATH))
    if image is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {IMAGE_PATH}")

    height, width = image.shape[:2]
    now = datetime.now().isoformat(timespec="seconds")
    photo_id = db.insert_photo(
        image_path=IMAGE_PATH,
        original_filename=IMAGE_PATH.name,
        width=width,
        height=height,
        taken_at=now,
    )

    detector = VisionDetector()
    _, detections, elapsed = detector.detect(IMAGE_PATH)

    service = UnknownTrackingService(db, match_threshold=UNKNOWN_MATCH_THRESHOLD)
    result = service.process(photo_id, image, detections, observed_at=now)

    # draw in script so service stays UI-independent
    output = result["result_image"]
    for item in result["items"]:
        x1, y1, x2, y2 = item["bbox"]
        label = f"UT{item['track_id']:06d} {item['state']}"
        if item["state"] == "MATCH":
            label += f" {item['score']:.2f}"
        cv2.rectangle(output, (x1, y1), (x2, y2), (255, 255, 255), 3)
        cv2.putText(output, label, (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    cv2.imwrite(str(RESULT_PATH), output)
    print(f"YOLO 처리시간: {elapsed:.1f}초")
    print(f"기존 UNKNOWN 매칭: {result['matched_count']}")
    print(f"신규 UNKNOWN: {result['new_count']}")
    print(f"미관찰 UNKNOWN: {result['missing_count']}")
    print(f"UNKNOWN 후보: {len(result['candidates'])}")
    print(f"결과 이미지: {RESULT_PATH.resolve()}")


if __name__ == "__main__":
    main()
