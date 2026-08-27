\
from datetime import datetime
from pathlib import Path
import cv2

from config import UNKNOWN_MATCH_THRESHOLD
from src.database import FridgeDatabase
from src.vision_detector import VisionDetector
from src.services.unknown_tracking_service import UnknownTrackingService
from src.services.content_unknown_service import ContentUnknownService
from src.services.alert_service import AlertService


class FridgeService:
    """사진 한 장을 처리하는 통합 서비스."""

    def __init__(self):
        self.db = FridgeDatabase()
        self.db.initialize()

        self.vision = VisionDetector()
        self.unknown = UnknownTrackingService(
            self.db, match_threshold=UNKNOWN_MATCH_THRESHOLD
        )
        self.content_unknown = ContentUnknownService(
            self.db, match_threshold=UNKNOWN_MATCH_THRESHOLD
        )
        self.alert = AlertService(self.db)

    def process_photo(self, image_path):
        image_path = Path(image_path)
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {image_path}")

        height, width = image.shape[:2]
        now = datetime.now().isoformat(timespec="seconds")

        photo_id = self.db.insert_photo(
            image_path=image_path,
            original_filename=image_path.name,
            width=width,
            height=height,
            taken_at=now,
        )

        # YOLO: FOOD + CONTAINER
        _, detections, elapsed = self.vision.detect(image_path)

        # YOLO가 놓친 영역: UNKNOWN
        unknown_result = self.unknown.process(
            photo_id, image, detections, observed_at=now
        )

        # YOLO가 용기는 찾았지만 내부 내용물은 모르는 경우: CONTENT_UNKNOWN
        content_result = self.content_unknown.process(
            photo_id, image, detections, observed_at=now
        )

        # 이번 사진에 실제로 보이는 장기보관 대상만 알림
        targets = self.alert.get_due_targets(current_photo_id=photo_id)
        alert_image = None
        alert_message = None

        if targets:
            alert_image = self.alert.create_marked_image(
                image, targets, f"alert_photo_{photo_id}.jpg"
            )
            alert_message = self.alert.build_message(targets)

        return {
            "photo_id": photo_id,
            "yolo_elapsed": elapsed,
            "detections": detections,
            "unknown": unknown_result,
            "content_unknown": content_result,
            "alert_targets": targets,
            "alert_image": alert_image,
            "alert_message": alert_message,
        }

    def mark_alert_sent(self, targets):
        self.alert.record_sent(targets)
