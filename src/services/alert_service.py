\
from datetime import datetime
import cv2

from config import (
    ALERT_AFTER_DAYS,
    ALERT_REPEAT_DAYS,
    MIN_HIT_COUNT_FOR_ALERT,
    RESULT_DIR,
)


class AlertService:

    def __init__(self, database):
        self.db = database

    def _repeat_due(self, target):
        last = self.db.get_last_alert(
            target["target_type"], target["target_id"]
        )
        if last is None:
            return True

        last_date = datetime.fromisoformat(last["alerted_at"]).date()
        today = datetime.now().date()
        return (today - last_date).days >= ALERT_REPEAT_DAYS

    def get_due_targets(self, current_photo_id=None):
        rows = self.db.get_long_term_alert_targets(
            min_days=ALERT_AFTER_DAYS,
            min_hits=MIN_HIT_COUNT_FOR_ALERT,
        )

        result = []
        for row in rows:
            if current_photo_id is not None and row["last_photo_id"] != current_photo_id:
                continue
            if self._repeat_due(row):
                result.append(row)
        return result

    @staticmethod
    def _code(target):
        prefix = "UT" if target["target_type"] == "UNKNOWN" else "CU"
        return f"{prefix}{target['target_id']:06d}"

    def build_message(self, targets):
        if not targets:
            return None

        lines = [
            "⚠️ 냉장고 확인이 필요합니다.",
            "",
            f"장기간 확인되지 않은 식재료/내용물이 {len(targets)}개 있습니다.",
            "",
        ]

        for t in targets:
            code = self._code(t)
            if t["target_type"] == "CONTENT_UNKNOWN":
                lines.append(
                    f"• {code}: {t['storage_days']}일째 "
                    f"({t['container_class']} 내부 내용물 미확인)"
                )
            else:
                lines.append(
                    f"• {code}: {t['storage_days']}일째 (알 수 없는 식재료)"
                )

        lines += [
            "",
            "첨부된 냉장고 사진에서 표시된 위치를 확인한 후 관리해주세요.",
        ]
        return "\n".join(lines)

    def create_marked_image(self, image, targets, output_name="unknown_alert.jpg"):
        output = image.copy()

        for t in targets:
            x1, y1, x2, y2 = (
                int(t["bbox_x1"]), int(t["bbox_y1"]),
                int(t["bbox_x2"]), int(t["bbox_y2"])
            )
            code = self._code(t)
            label = f"{code} / {t['storage_days']} days"

            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 0, 255), 5)
            cv2.putText(
                output, label, (x1, max(35, y1 - 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 3
            )

        path = RESULT_DIR / output_name
        cv2.imwrite(str(path), output)
        return path

    def record_sent(self, targets):
        for t in targets:
            self.db.insert_alert_history(
                t["target_type"], t["target_id"],
                t["last_photo_id"], t["storage_days"]
            )
