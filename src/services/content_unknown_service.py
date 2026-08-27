\
from datetime import datetime
import cv2

from config import (
    CONTENT_UNKNOWN_DIR, UNKNOWN_EXPIRE_THRESHOLD,
    CONTENT_UNKNOWN_CLASSES, CONTENT_UNKNOWN_MIN_CONFIDENCE,
)
from src.vision import UnknownTracker


class ContentUnknownService:
    """
    YOLO가 CONTAINER로 인식한 물체를 '내용물 미확인' 대상으로 추적한다.
    용기 자체의 정체와 내부 식재료의 정체를 분리해서 관리한다.
    """

    def __init__(self, database, match_threshold=0.68):
        self.db = database
        self.tracker = UnknownTracker(match_threshold=match_threshold)

    def process(self, photo_id, image, detections, observed_at=None):
        observed_at = observed_at or datetime.now().isoformat(timespec="seconds")
        height, width = image.shape[:2]

        containers = [
            d for d in detections
            if d.get("category") == "CONTAINER"
            and d.get("class_name") in CONTENT_UNKNOWN_CLASSES
            and float(d.get("confidence", 0.0)) >= CONTENT_UNKNOWN_MIN_CONFIDENCE
        ]

        existing = self.db.get_content_unknown_candidates()
        used_ids = set()
        items = []

        for index, det in enumerate(containers, start=1):
            bbox = det["bbox"]
            x1, y1, x2, y2 = bbox
            crop = image[y1:y2, x1:x2]

            candidate = {"bbox": bbox}
            matched, score, details = self.tracker.find_best_match(
                candidate, crop, existing, width, height, used_ids
            )

            if matched is not None:
                track_id = matched["track_id"]
                folder = CONTENT_UNKNOWN_DIR / f"CU{track_id:06d}"
                folder.mkdir(parents=True, exist_ok=True)
                crop_path = folder / f"photo_{photo_id}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(crop_path), crop)

                self.db.update_content_unknown_track(
                    track_id, photo_id, det["class_name"], bbox,
                    crop_path, observed_at
                )
                used_ids.add(track_id)
                state = "MATCH"
            else:
                placeholder = CONTENT_UNKNOWN_DIR / f"pending_{photo_id}_{index}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(placeholder), crop)

                track_id = self.db.insert_content_unknown_track(
                    photo_id, det["class_name"], bbox, placeholder, observed_at
                )
                folder = CONTENT_UNKNOWN_DIR / f"CU{track_id:06d}"
                folder.mkdir(parents=True, exist_ok=True)
                crop_path = folder / f"photo_{photo_id}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(crop_path), crop)

                with self.db.connect() as conn:
                    conn.execute("""
                        UPDATE content_unknown_track
                        SET crop_path=?, updated_at=?
                        WHERE track_id=?
                    """, (str(crop_path), observed_at, track_id))

                try:
                    placeholder.unlink()
                except FileNotFoundError:
                    pass

                used_ids.add(track_id)
                score, details, state = 0.0, None, "NEW"

            items.append({
                "track_id": track_id,
                "code": f"CU{track_id:06d}",
                "state": state,
                "container_class": det["class_name"],
                "confidence": det.get("confidence"),
                "score": float(score),
                "details": details,
                "bbox": bbox,
            })

        missing = 0
        for row in existing:
            if row["track_id"] not in used_ids:
                self.db.mark_content_unknown_missing(
                    row["track_id"], UNKNOWN_EXPIRE_THRESHOLD
                )
                missing += 1

        return {
            "containers": containers,
            "items": items,
            "matched_count": sum(1 for i in items if i["state"] == "MATCH"),
            "new_count": sum(1 for i in items if i["state"] == "NEW"),
            "missing_count": missing,
        }
