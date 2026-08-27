import json
from pathlib import Path

import cv2

from src.vision_detector import VisionDetector


IMAGE_PATH = "images/test_fridge.jpg"

RESULT_DIR = Path("results")
RESULT_DIR.mkdir(exist_ok=True)


detector = VisionDetector()

image, detections, elapsed = detector.detect(
    IMAGE_PATH
)


print()
print("====================================")
print("최종 검출 결과")
print("====================================")

for i, item in enumerate(detections, start=1):

    print(
        f"{i:02d}. "
        f"[{item['category']}] "
        f"{item['class_name']} "
        f"{item['confidence']:.2f}"
    )


# --------------------------------------------------
# JSON 저장
# --------------------------------------------------

json_path = RESULT_DIR / "detections.json"

with open(
    json_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        {
            "processing_seconds": round(elapsed, 2),
            "detected_count": len(detections),
            "items": detections
        },
        f,
        ensure_ascii=False,
        indent=2
    )


# --------------------------------------------------
# 결과 이미지 작성
# --------------------------------------------------

for item in detections:

    x1, y1, x2, y2 = item["bbox"]

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        3
    )

    label = (
        f"{item['category']} "
        f"{item['class_name']} "
        f"{item['confidence']:.2f}"
    )

    cv2.putText(
        image,
        label,
        (x1, max(30, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )


image_path = RESULT_DIR / "detected.jpg"

cv2.imwrite(
    str(image_path),
    image
)


print()
print("------------------------------------")
print("검출 객체:", len(detections))
print(f"처리시간: {elapsed:.1f}초")
print()
print("JSON:", json_path.resolve())
print("이미지:", image_path.resolve())