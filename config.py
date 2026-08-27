from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IMAGE_DIR = BASE_DIR / "images"
RESULT_DIR = BASE_DIR / "results"
UNKNOWN_DIR = DATA_DIR / "unknown"
CONTENT_UNKNOWN_DIR = DATA_DIR / "content_unknown"
DB_PATH = DATA_DIR / "fridge.db"

UNKNOWN_MATCH_THRESHOLD = 0.68
UNKNOWN_EXPIRE_THRESHOLD = 3

# 장기보관 알림 정책
ALERT_AFTER_DAYS = 0
ALERT_REPEAT_DAYS = 1
MIN_HIT_COUNT_FOR_ALERT = 1

for path in (
    DATA_DIR, IMAGE_DIR, RESULT_DIR,
    UNKNOWN_DIR, CONTENT_UNKNOWN_DIR
):
    path.mkdir(parents=True, exist_ok=True)

CONTENT_UNKNOWN_CLASSES = {
    "food storage container", "plastic food container", "glass food container",
    "lunch box", "cooking pot", "bowl", "plastic food bag", "plastic bag",
    "ziplock bag", "vinyl bag", "food pouch", "sealed pouch", "vacuum bag",
}
CONTENT_UNKNOWN_MIN_CONFIDENCE = 0.18
