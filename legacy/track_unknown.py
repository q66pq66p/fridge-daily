from datetime import datetime
from pathlib import Path

import cv2

from src.database import FridgeDatabase
from src.vision_detector import VisionDetector
from src.unknown_detector import UnknownDetector
from src.unknown_tracker import UnknownTracker


IMAGE_PATH = Path(
    "images/test2_fridge03.jpg"
)

RESULT_PATH = Path(
    "results/unknown_tracking.jpg"
)

UNKNOWN_DIR = Path(
    "data/unknown"
)

UNKNOWN_DIR.mkdir(
    parents=True,
    exist_ok=True
)


db = FridgeDatabase()
db.initialize()

detector = VisionDetector()
unknown_detector = UnknownDetector()

tracker = UnknownTracker(
    match_threshold=0.68
)


image = cv2.imread(
    str(IMAGE_PATH)
)

height, width = image.shape[:2]

now = datetime.now().isoformat(
    timespec="seconds"
)


# ------------------------------------------------------------
# 여기서는 UNKNOWN 테스트용 photo 등록
# ------------------------------------------------------------

photo_id = db.insert_photo(
    image_path=IMAGE_PATH,
    original_filename=IMAGE_PATH.name,
    width=width,
    height=height,
    taken_at=now
)


# ------------------------------------------------------------
# YOLO
# ------------------------------------------------------------

_, detections, elapsed = detector.detect(
    IMAGE_PATH
)


# ------------------------------------------------------------
# UNKNOWN 후보
# ------------------------------------------------------------

candidates = unknown_detector.detect(
    image,
    detections
)

existing_tracks = (
    db.get_unknown_candidates()
)

used_track_ids = set()

matched_count = 0
new_count = 0

result_image = image.copy()

print()
print("====================================")
print("UNKNOWN Tracking 결과")
print("====================================")


for index, candidate in enumerate(
    candidates,
    start=1
):

    x1, y1, x2, y2 = candidate["bbox"]

    crop = image[
        y1:y2,
        x1:x2
    ]

    matched, score, details = (
        tracker.find_best_match(
            candidate,
            crop,
            existing_tracks,
            width,
            height,
            used_track_ids
        )
    )

    # --------------------------------------------------------
    # 기존 후보
    # --------------------------------------------------------

    if matched is not None:

        track_id = matched["track_id"]

        used_track_ids.add(
            track_id
        )

        folder = (
            UNKNOWN_DIR /
            f"UT{track_id:06d}"
        )

        folder.mkdir(
            parents=True,
            exist_ok=True
        )

        crop_path = (
            folder /
            f"photo_{photo_id}.jpg"
        )

        if crop.size > 0:
            cv2.imwrite(
                str(crop_path),
                crop
            )

        db.update_unknown_track(
            track_id,
            photo_id,
            candidate["bbox"],
            crop_path,
            now
        )

        matched_count += 1
        
        cv2.rectangle(
            result_image,
            (x1, y1),
            (x2, y2),
            (255, 255, 255),
            3
        )

        cv2.putText(
            result_image,
            f"UT{track_id:06d} MATCH {score:.2f}",
            (x1, max(30, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        print(
            f"{index:02d}. "
            f"MATCH UT{track_id:06d} "
            f"score={score:.3f} "
            f"{details}"
        )

    # --------------------------------------------------------
    # 신규 후보
    # --------------------------------------------------------

    else:

        temp_path = (
            UNKNOWN_DIR /
            f"temp_{photo_id}_{index}.jpg"
        )

        if crop.size > 0:

            cv2.imwrite(
                str(temp_path),
                crop
            )

        track_id = db.insert_unknown_track(
            photo_id,
            candidate["bbox"],
            temp_path,
            now
        )

        # 정식 Track 폴더 생성
        folder = (
            UNKNOWN_DIR /
            f"UT{track_id:06d}"
        )

        folder.mkdir(
            parents=True,
            exist_ok=True
        )

        final_path = (
            folder /
            f"photo_{photo_id}.jpg"
        )

        if crop.size > 0:

            cv2.imwrite(
                str(final_path),
                crop
            )

        # crop_path를 정식 경로로 갱신
        db.update_unknown_track(
            track_id,
            photo_id,
            candidate["bbox"],
            final_path,
            now
        )

        # insert에서 이미 hit_count=1인데
        # update하면 2가 되므로 보정
        with db.connect() as conn:

            conn.execute("""
                UPDATE unknown_track
                SET hit_count = 1
                WHERE track_id = ?
            """, (
                track_id,
            ))

        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass

        used_track_ids.add(
            track_id
        )

        new_count += 1
        
        cv2.rectangle(
            result_image,
            (x1, y1),
            (x2, y2),
            (0, 0, 255),
            3
        )

        cv2.putText(
            result_image,
            f"UT{track_id:06d} NEW",
            (x1, max(30, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

        print(
            f"{index:02d}. "
            f"NEW   UT{track_id:06d}"
        )


# ------------------------------------------------------------
# 이번 사진에서 안 보인 기존 후보
# ------------------------------------------------------------

missing_count = 0

for track in existing_tracks:

    track_id = track["track_id"]

    if track_id not in used_track_ids:

        db.mark_unknown_track_missing(
            track_id,
            expire_threshold=3
        )

        missing_count += 1


print()
print("------------------------------------")
print("기존 UNKNOWN 매칭:", matched_count)
print("신규 UNKNOWN:", new_count)
print("미관찰 UNKNOWN:", missing_count)
print("UNKNOWN 후보:", len(candidates))


RESULT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)

cv2.imwrite(
    str(RESULT_PATH),
    result_image
)

print()
print(
    "Tracking 결과 이미지:",
    RESULT_PATH
)