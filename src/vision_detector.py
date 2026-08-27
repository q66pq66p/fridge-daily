import json
import time
from pathlib import Path

import cv2
from ultralytics import YOLOWorld


MODEL_NAME = "yolov8s-worldv2.pt"

FOOD_CLASSES = [
    # 유제품 / 달걀 / 두부
    "milk carton", "milk bottle", "yogurt", "cheese", "butter",
    "egg", "egg carton", "tofu package",

    # 채소 / 과일
    "kimchi", "onion", "green onion", "garlic", "carrot", "cabbage",
    "lettuce", "spinach", "mushroom", "cucumber", "zucchini",
    "potato", "sweet potato", "pepper", "broccoli",
    "apple", "banana", "orange", "tomato", "lemon", "grape",
    "strawberry", "vegetables", "fruit",

    # 육류 / 수산 / 가공식품
    "meat package", "beef", "pork", "chicken", "fish", "seafood",
    "sausage", "ham", "bacon",
    "frozen food package", "food package", "prepared food",
    "leftover food", "side dish"
]

CONTAINER_CLASSES = [
    # 조리/보관 용기
    "cooking pot", "food storage container", "plastic food container",
    "glass food container", "lunch box", "bowl", "plate", "tray", "cup",

    # 병 / 캔 / 팩
    "bottle", "plastic bottle", "glass bottle", "glass jar",
    "jar", "can", "tin can", "carton", "food carton",

    # 봉투 / 포장재
    "plastic food bag", "plastic bag", "ziplock bag", "vinyl bag",
    "food pouch", "sealed pouch", "vacuum bag", "food wrapper",
    "plastic wrap", "aluminum foil",

    # 박스 / 기타 냉장고 내 보관물
    "food box", "cardboard box", "paper bag", "basket"
]


class VisionDetector:

    def __init__(self):
        print("YOLO-World 모델 로딩...")
        self.model = YOLOWorld(MODEL_NAME)
        print("모델 로딩 완료")

    def _detect(self, image, classes, category,
                conf=0.12, imgsz=960):

        self.model.set_classes(classes)

        results = self.model.predict(
            source=image,
            imgsz=imgsz,
            conf=conf,
            iou=0.50,
            device="cpu",
            verbose=False
        )

        detections = []

        result = results[0]

        for box in result.boxes:

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append({
                "category": category,
                "class_name": result.names[class_id],
                "confidence": round(confidence, 4),
                "bbox": [
                    round(x1),
                    round(y1),
                    round(x2),
                    round(y2)
                ]
            })

        return detections

    def _create_tiles(self, image,
                      rows=3,
                      cols=3,
                      overlap=0.15):

        height, width = image.shape[:2]

        tile_width = width / cols
        tile_height = height / rows

        tiles = []

        for row in range(rows):
            for col in range(cols):

                x1 = int(col * tile_width)
                y1 = int(row * tile_height)

                x2 = int((col + 1) * tile_width)
                y2 = int((row + 1) * tile_height)

                margin_x = int(tile_width * overlap)
                margin_y = int(tile_height * overlap)

                x1 = max(0, x1 - margin_x)
                y1 = max(0, y1 - margin_y)

                x2 = min(width, x2 + margin_x)
                y2 = min(height, y2 + margin_y)

                crop = image[y1:y2, x1:x2]

                tiles.append({
                    "image": crop,
                    "offset_x": x1,
                    "offset_y": y1
                })

        return tiles

    @staticmethod
    def _iou(box1, box2):

        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)

        area1 = (
            (box1[2] - box1[0]) *
            (box1[3] - box1[1])
        )

        area2 = (
            (box2[2] - box2[0]) *
            (box2[3] - box2[1])
        )

        union = area1 + area2 - intersection

        if union <= 0:
            return 0

        return intersection / union

    def _remove_duplicates(self,
                           detections,
                           threshold=0.50):

        detections = sorted(
            detections,
            key=lambda x: x["confidence"],
            reverse=True
        )

        selected = []

        for candidate in detections:

            duplicate = False

            for existing in selected:

                # FOOD와 CONTAINER는 서로 다른 의미이므로
                # 서로 제거하지 않는다.
                if (
                    candidate["category"]
                    != existing["category"]
                ):
                    continue

                iou = self._iou(
                    candidate["bbox"],
                    existing["bbox"]
                )

                if iou >= threshold:
                    duplicate = True
                    break

            if not duplicate:
                selected.append(candidate)

        return selected

    def detect(self, image_path):

        image_path = Path(image_path)

        image = cv2.imread(str(image_path))

        if image is None:
            raise FileNotFoundError(
                f"이미지를 읽을 수 없습니다: {image_path}"
            )

        start = time.time()

        all_detections = []

        # -------------------------------------------
        # 전체 이미지 탐지
        # -------------------------------------------

        print("전체 이미지 FOOD 탐지...")

        all_detections += self._detect(
            image,
            FOOD_CLASSES,
            "FOOD",
            conf=0.10
        )

        print("전체 이미지 CONTAINER 탐지...")

        all_detections += self._detect(
            image,
            CONTAINER_CLASSES,
            "CONTAINER",
            conf=0.10
        )

        # -------------------------------------------
        # Tile 탐지
        # -------------------------------------------

        tiles = self._create_tiles(image)

        print(f"Tile 탐지 시작: {len(tiles)}개")

        for index, tile in enumerate(tiles):

            print(
                f"  Tile {index + 1}/{len(tiles)}"
            )

            tile_detections = []

            tile_detections += self._detect(
                tile["image"],
                FOOD_CLASSES,
                "FOOD",
                conf=0.12
            )

            tile_detections += self._detect(
                tile["image"],
                CONTAINER_CLASSES,
                "CONTAINER",
                conf=0.12
            )

            # Tile 좌표 → 원본 좌표
            for detection in tile_detections:

                bbox = detection["bbox"]

                bbox[0] += tile["offset_x"]
                bbox[1] += tile["offset_y"]
                bbox[2] += tile["offset_x"]
                bbox[3] += tile["offset_y"]

                all_detections.append(detection)

        # -------------------------------------------
        # 중복 제거
        # -------------------------------------------

        before = len(all_detections)

        final_detections = self._remove_duplicates(
            all_detections,
            threshold=0.50
        )

        after = len(final_detections)

        elapsed = time.time() - start

        print()
        print(f"중복 제거 전: {before}")
        print(f"중복 제거 후: {after}")
        print(f"총 처리시간: {elapsed:.1f}초")

        return image, final_detections, elapsed