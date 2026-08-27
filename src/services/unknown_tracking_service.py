
from datetime import datetime
from pathlib import Path
import cv2

from config import UNKNOWN_DIR, UNKNOWN_EXPIRE_THRESHOLD
from src.vision import UnknownDetector, UnknownTracker


class UnknownTrackingService:
    """YOLO 결과에서 UNKNOWN 후보를 추출하고 지속 추적한다."""

    def __init__(self, database, match_threshold=0.68):
        self.db = database
        self.detector = UnknownDetector()
        self.tracker = UnknownTracker(match_threshold=match_threshold)

    def process(self, photo_id, image, yolo_detections, observed_at=None):
        if image is None:
            raise ValueError("image is None")

        observed_at = observed_at or datetime.now().isoformat(timespec="seconds")
        height, width = image.shape[:2]
        candidates = self.detector.detect(image, yolo_detections)
        existing_tracks = self.db.get_unknown_candidates()
        used_track_ids = set()

        matched_count = 0
        new_count = 0
        result_image = image.copy()
        items = []

        for index, candidate in enumerate(candidates, start=1):
            x1, y1, x2, y2 = candidate["bbox"]
            crop = image[y1:y2, x1:x2]

            matched, score, details = self.tracker.find_best_match(
                candidate, crop, existing_tracks, width, height, used_track_ids
            )

            if matched is not None:
                track_id = matched["track_id"]
                used_track_ids.add(track_id)
                folder = UNKNOWN_DIR / f"UT{track_id:06d}"
                folder.mkdir(parents=True, exist_ok=True)
                crop_path = folder / f"photo_{photo_id}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(crop_path), crop)

                self.db.update_unknown_track(
                    track_id, photo_id, candidate["bbox"], crop_path, observed_at
                )
                matched_count += 1
                state = "MATCH"
            else:
                # DB insert is performed once; save crop directly to its final folder afterwards.
                # A temporary path is only a placeholder until the generated track_id is known.
                placeholder = UNKNOWN_DIR / f"pending_photo_{photo_id}_{index}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(placeholder), crop)

                track_id = self.db.insert_unknown_track(
                    photo_id, candidate["bbox"], placeholder, observed_at
                )
                folder = UNKNOWN_DIR / f"UT{track_id:06d}"
                folder.mkdir(parents=True, exist_ok=True)
                crop_path = folder / f"photo_{photo_id}.jpg"
                if crop.size > 0:
                    cv2.imwrite(str(crop_path), crop)

                # Update only crop/bbox path without incrementing hit_count a second time.
                with self.db.connect() as conn:
                    conn.execute(
                        """UPDATE unknown_track
                           SET bbox_x1=?, bbox_y1=?, bbox_x2=?, bbox_y2=?,
                               crop_path=?, updated_at=?
                           WHERE track_id=?""",
                        (x1, y1, x2, y2, str(crop_path), observed_at, track_id),
                    )
                try:
                    placeholder.unlink()
                except FileNotFoundError:
                    pass

                used_track_ids.add(track_id)
                new_count += 1
                score, details, state = 0.0, None, "NEW"

            items.append({
                "track_id": track_id,
                "state": state,
                "score": float(score),
                "details": details,
                "bbox": candidate["bbox"],
            })

        missing_count = 0
        for track in existing_tracks:
            if track["track_id"] not in used_track_ids:
                self.db.mark_unknown_track_missing(
                    track["track_id"], expire_threshold=UNKNOWN_EXPIRE_THRESHOLD
                )
                missing_count += 1

        return {
            "candidates": candidates,
            "items": items,
            "matched_count": matched_count,
            "new_count": new_count,
            "missing_count": missing_count,
            "result_image": result_image,
        }
