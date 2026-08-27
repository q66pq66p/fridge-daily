import sqlite3
from datetime import datetime
from pathlib import Path


from config import DB_PATH


class FridgeDatabase:

    def __init__(self, db_path=DB_PATH):

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

    def connect(self):

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # SQLite 외래키 활성화
        conn.execute("PRAGMA foreign_keys = ON")

        return conn

    # ========================================================
    # DB 초기화
    # ========================================================

    def initialize(self):

        with self.connect() as conn:

            # ------------------------------------------------
            # PHOTO
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS photo (

                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    image_path TEXT NOT NULL,

                    original_filename TEXT,

                    taken_at TEXT,

                    processed_at TEXT NOT NULL,

                    width INTEGER,

                    height INTEGER

                )
            """)

            # ------------------------------------------------
            # FRIDGE_OBJECT
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS fridge_object (

                    object_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    object_code TEXT UNIQUE,

                    object_type TEXT NOT NULL,

                    object_name TEXT,

                    status TEXT NOT NULL DEFAULT 'ACTIVE',

                    first_seen TEXT NOT NULL,

                    last_seen TEXT NOT NULL,

                    seen_count INTEGER NOT NULL DEFAULT 1,

                    observed_days INTEGER NOT NULL DEFAULT 1,

                    missing_count INTEGER NOT NULL DEFAULT 0,

                    last_missing_at TEXT,

                    persistence_score REAL NOT NULL DEFAULT 1,

                    last_confidence REAL,

                    user_confirmed INTEGER NOT NULL DEFAULT 0,

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL
                )
            """)

            # ------------------------------------------------
            # OBJECT_OBSERVATION
            # ------------------------------------------------

            conn.execute("""
                CREATE TABLE IF NOT EXISTS object_observation (

                    observation_id
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    object_id INTEGER NOT NULL,

                    photo_id INTEGER NOT NULL,

                    detected_class TEXT,

                    detected_category TEXT,

                    confidence REAL,

                    bbox_x1 INTEGER,
                    bbox_y1 INTEGER,
                    bbox_x2 INTEGER,
                    bbox_y2 INTEGER,

                    crop_path TEXT,

                    observed_at TEXT NOT NULL,

                    FOREIGN KEY(object_id)
                        REFERENCES fridge_object(object_id),

                    FOREIGN KEY(photo_id)
                        REFERENCES photo(photo_id)

                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS unknown_track (

                    track_id INTEGER PRIMARY KEY AUTOINCREMENT,

                    first_photo_id INTEGER NOT NULL,
                    last_photo_id INTEGER NOT NULL,

                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,

                    hit_count INTEGER NOT NULL DEFAULT 1,
                    miss_count INTEGER NOT NULL DEFAULT 0,

                    bbox_x1 INTEGER NOT NULL,
                    bbox_y1 INTEGER NOT NULL,
                    bbox_x2 INTEGER NOT NULL,
                    bbox_y2 INTEGER NOT NULL,

                    crop_path TEXT,

                    status TEXT NOT NULL DEFAULT 'CANDIDATE',

                    promoted_object_id INTEGER,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)            
            

            # ------------------------------------------------
            # CONTENT_UNKNOWN_TRACK
            # 용기는 인식했지만 내부 식재료는 알 수 없는 대상
            # ------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_unknown_track (
                    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_photo_id INTEGER NOT NULL,
                    last_photo_id INTEGER NOT NULL,
                    container_class TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    miss_count INTEGER NOT NULL DEFAULT 0,
                    bbox_x1 INTEGER NOT NULL,
                    bbox_y1 INTEGER NOT NULL,
                    bbox_x2 INTEGER NOT NULL,
                    bbox_y2 INTEGER NOT NULL,
                    crop_path TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # ------------------------------------------------
            # ALERT_HISTORY
            # UNKNOWN / CONTENT_UNKNOWN 공통 알림 이력
            # ------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    photo_id INTEGER,
                    storage_days INTEGER NOT NULL,
                    alerted_at TEXT NOT NULL
                )
            """)

            # ========================================================
            # 기존 DB Migration
            # ========================================================

            columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(fridge_object)"
                ).fetchall()
            }

            if "missing_count" not in columns:
                conn.execute("""
                    ALTER TABLE fridge_object
                    ADD COLUMN missing_count INTEGER NOT NULL DEFAULT 0
                """)

            if "last_missing_at" not in columns:
                conn.execute("""
                    ALTER TABLE fridge_object
                    ADD COLUMN last_missing_at TEXT
                """)

            if "observed_days" not in columns:
                conn.execute("""
                    ALTER TABLE fridge_object
                    ADD COLUMN observed_days INTEGER NOT NULL DEFAULT 1
                """)

            conn.commit()
            

            # 조회 성능용 인덱스
            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_object_status
                ON fridge_object(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_observation_object
                ON object_observation(object_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_observation_photo
                ON object_observation(photo_id)
            """)

            conn.commit()

    # ========================================================
    # 사진 등록
    # ========================================================

    def insert_photo(
        self,
        image_path,
        original_filename,
        width,
        height,
        taken_at=None
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        if taken_at is None:
            taken_at = now

        with self.connect() as conn:

            cursor = conn.execute("""
                INSERT INTO photo (
                    image_path,
                    original_filename,
                    taken_at,
                    processed_at,
                    width,
                    height
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(image_path),
                original_filename,
                taken_at,
                now,
                width,
                height
            ))

            return cursor.lastrowid

    # ========================================================
    # 신규 객체 등록
    # ========================================================

    def insert_object(
        self,
        object_type,
        object_name,
        confidence,
        observed_at=None
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        if observed_at is None:
            observed_at = now

        with self.connect() as conn:

            cursor = conn.execute("""
                INSERT INTO fridge_object (
                    object_type,
                    object_name,
                    status,
                    first_seen,
                    last_seen,
                    seen_count,
                    persistence_score,
                    last_confidence,
                    user_confirmed,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, 'ACTIVE',
                    ?, ?, 1, 1,
                    ?, 0, ?, ?
                )
            """, (
                object_type,
                object_name,
                observed_at,
                observed_at,
                confidence,
                now,
                now
            ))

            object_id = cursor.lastrowid

            object_code = f"OBJ{object_id:06d}"

            conn.execute("""
                UPDATE fridge_object
                SET object_code = ?
                WHERE object_id = ?
            """, (
                object_code,
                object_id
            ))

            return object_id, object_code

    # ========================================================
    # 관찰 이력 등록
    # ========================================================

    def insert_observation(
        self,
        object_id,
        photo_id,
        detected_class,
        detected_category,
        confidence,
        bbox,
        crop_path,
        observed_at=None
    ):

        if observed_at is None:

            observed_at = datetime.now().isoformat(
                timespec="seconds"
            )

        x1, y1, x2, y2 = bbox

        with self.connect() as conn:

            cursor = conn.execute("""
                INSERT INTO object_observation (
                    object_id,
                    photo_id,
                    detected_class,
                    detected_category,
                    confidence,
                    bbox_x1,
                    bbox_y1,
                    bbox_x2,
                    bbox_y2,
                    crop_path,
                    observed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                object_id,
                photo_id,
                detected_class,
                detected_category,
                confidence,
                x1,
                y1,
                x2,
                y2,
                str(crop_path),
                observed_at
            ))

            return cursor.lastrowid

    # ========================================================
    # 현재 객체 조회
    # ========================================================

    def get_active_objects(self):

        with self.connect() as conn:

            rows = conn.execute("""
                SELECT *
                FROM fridge_object
                WHERE status = 'ACTIVE'
                ORDER BY object_id
            """).fetchall()

            return rows
            
    # ========================================================
    # 객체의 마지막 관찰정보 조회
    # ========================================================

    def get_active_objects_with_last_observation(self):

        with self.connect() as conn:

            rows = conn.execute("""
                SELECT
                    fo.*,

                    oo.observation_id,
                    oo.photo_id AS last_photo_id,
                    oo.detected_class,
                    oo.detected_category,
                    oo.confidence AS observation_confidence,

                    oo.bbox_x1,
                    oo.bbox_y1,
                    oo.bbox_x2,
                    oo.bbox_y2,

                    oo.crop_path,
                    oo.observed_at

                FROM fridge_object fo

                LEFT JOIN object_observation oo
                    ON oo.observation_id = (
                        SELECT oo2.observation_id
                        FROM object_observation oo2
                        WHERE oo2.object_id = fo.object_id
                        ORDER BY
                            oo2.observed_at DESC,
                            oo2.observation_id DESC
                        LIMIT 1
                    )

                WHERE fo.status IN ('ACTIVE', 'MISSING')

                ORDER BY fo.object_id

            """).fetchall()

            return rows

    # ========================================================
    # 기존 객체 재발견 처리
    # ========================================================

    def update_object_seen(
        self,
        object_id,
        confidence,
        observed_at
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.connect() as conn:

            conn.execute("""
                UPDATE fridge_object

                SET
                    last_seen = ?,
                    seen_count = seen_count + 1,

                    persistence_score =
                        persistence_score + 1,

                    last_confidence = ?,

                    missing_count = 0,
                    last_missing_at = NULL,

                    status = 'ACTIVE',
                    updated_at = ?

                WHERE object_id = ?
            """, (
                observed_at,
                confidence,
                now,
                object_id
            ))

    # ========================================================
    # 객체 상태 변경
    # ========================================================

    def update_object_status(
        self,
        object_id,
        status
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.connect() as conn:

            conn.execute("""
                UPDATE fridge_object
                SET
                    status = ?,
                    updated_at = ?
                WHERE object_id = ?
            """, (
                status,
                now,
                object_id
            ))
            
            
    def mark_object_not_seen(
        self,
        object_id,
        observed_at,
        missing_threshold=3
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.connect() as conn:

            row = conn.execute("""
                SELECT missing_count
                FROM fridge_object
                WHERE object_id = ?
            """, (
                object_id,
            )).fetchone()

            if row is None:
                return

            missing_count = (
                row["missing_count"] + 1
            )

            if missing_count >= missing_threshold:
                status = "MISSING"
            else:
                status = "ACTIVE"

            conn.execute("""
                UPDATE fridge_object

                SET
                    missing_count = ?,
                    last_missing_at = ?,
                    status = ?,
                    updated_at = ?

                WHERE object_id = ?
            """, (
                missing_count,
                observed_at,
                status,
                now,
                object_id
            ))            
            

    def get_inventory_summary(self):

        with self.connect() as conn:

            rows = conn.execute("""
                SELECT
                    object_id,
                    object_code,
                    object_type,
                    object_name,
                    status,

                    first_seen,
                    last_seen,

                    seen_count,
                    missing_count,

                    CAST(
                        julianday('now', 'localtime')
                        - julianday(first_seen)
                        AS INTEGER
                    ) + 1 AS storage_days,

                    last_confidence

                FROM fridge_object

                WHERE status IN (
                    'ACTIVE',
                    'MISSING'
                )

                ORDER BY
                    storage_days DESC,
                    object_id
            """).fetchall()

            return rows            
                
    # ============================================================
    # UNKNOWN 후보 조회
    # ============================================================

    def get_unknown_candidates(self):

        with self.connect() as conn:

            return conn.execute("""
                SELECT *
                FROM unknown_track

                WHERE status = 'CANDIDATE'

                ORDER BY track_id
            """).fetchall()


    # ============================================================
    # UNKNOWN Track 생성
    # ============================================================

    def insert_unknown_track(
        self,
        photo_id,
        bbox,
        crop_path,
        observed_at
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        x1, y1, x2, y2 = bbox

        with self.connect() as conn:

            cursor = conn.execute("""
                INSERT INTO unknown_track (

                    first_photo_id,
                    last_photo_id,

                    first_seen,
                    last_seen,

                    hit_count,
                    miss_count,

                    bbox_x1,
                    bbox_y1,
                    bbox_x2,
                    bbox_y2,

                    crop_path,

                    status,

                    created_at,
                    updated_at
                )

                VALUES (
                    ?, ?,
                    ?, ?,
                    1, 0,
                    ?, ?, ?, ?,
                    ?,
                    'CANDIDATE',
                    ?, ?
                )
            """, (
                photo_id,
                photo_id,

                observed_at,
                observed_at,

                x1,
                y1,
                x2,
                y2,

                str(crop_path),

                now,
                now
            ))

            return cursor.lastrowid


    # ============================================================
    # 기존 UNKNOWN Track 재발견
    # ============================================================

    def update_unknown_track(
        self,
        track_id,
        photo_id,
        bbox,
        crop_path,
        observed_at
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        x1, y1, x2, y2 = bbox

        with self.connect() as conn:

            conn.execute("""
                UPDATE unknown_track

                SET
                    last_photo_id = ?,
                    last_seen = ?,

                    hit_count = hit_count + 1,
                    miss_count = 0,

                    bbox_x1 = ?,
                    bbox_y1 = ?,
                    bbox_x2 = ?,
                    bbox_y2 = ?,

                    crop_path = ?,
                    updated_at = ?

                WHERE track_id = ?
            """, (
                photo_id,
                observed_at,

                x1,
                y1,
                x2,
                y2,

                str(crop_path),
                now,

                track_id
            ))


    # ============================================================
    # UNKNOWN 후보 미관찰
    # ============================================================

    def mark_unknown_track_missing(
        self,
        track_id,
        expire_threshold=3
    ):

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.connect() as conn:

            row = conn.execute("""
                SELECT miss_count
                FROM unknown_track
                WHERE track_id = ?
            """, (
                track_id,
            )).fetchone()

            if row is None:
                return

            miss_count = row["miss_count"] + 1

            status = (
                "EXPIRED"
                if miss_count >= expire_threshold
                else "CANDIDATE"
            )

            conn.execute("""
                UPDATE unknown_track

                SET
                    miss_count = ?,
                    status = ?,
                    updated_at = ?

                WHERE track_id = ?
            """, (
                miss_count,
                status,
                now,
                track_id
            ))            

    # ============================================================
    # CONTENT_UNKNOWN
    # ============================================================

    def get_content_unknown_candidates(self):
        with self.connect() as conn:
            return conn.execute("""
                SELECT *
                FROM content_unknown_track
                WHERE status = 'ACTIVE'
                ORDER BY track_id
            """).fetchall()

    def insert_content_unknown_track(
        self, photo_id, container_class, bbox, crop_path, observed_at
    ):
        now = datetime.now().isoformat(timespec="seconds")
        x1, y1, x2, y2 = bbox
        with self.connect() as conn:
            cursor = conn.execute("""
                INSERT INTO content_unknown_track (
                    first_photo_id, last_photo_id, container_class,
                    first_seen, last_seen, hit_count, miss_count,
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                    crop_path, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (
                photo_id, photo_id, container_class,
                observed_at, observed_at,
                x1, y1, x2, y2, str(crop_path), now, now
            ))
            return cursor.lastrowid

    def update_content_unknown_track(
        self, track_id, photo_id, container_class, bbox, crop_path, observed_at
    ):
        now = datetime.now().isoformat(timespec="seconds")
        x1, y1, x2, y2 = bbox
        with self.connect() as conn:
            conn.execute("""
                UPDATE content_unknown_track
                SET last_photo_id=?, container_class=?, last_seen=?,
                    hit_count=hit_count+1, miss_count=0,
                    bbox_x1=?, bbox_y1=?, bbox_x2=?, bbox_y2=?,
                    crop_path=?, status='ACTIVE', updated_at=?
                WHERE track_id=?
            """, (
                photo_id, container_class, observed_at,
                x1, y1, x2, y2, str(crop_path), now, track_id
            ))

    def mark_content_unknown_missing(self, track_id, expire_threshold=3):
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            row = conn.execute("""
                SELECT miss_count FROM content_unknown_track WHERE track_id=?
            """, (track_id,)).fetchone()
            if row is None:
                return
            miss_count = row["miss_count"] + 1
            status = "EXPIRED" if miss_count >= expire_threshold else "ACTIVE"
            conn.execute("""
                UPDATE content_unknown_track
                SET miss_count=?, status=?, updated_at=?
                WHERE track_id=?
            """, (miss_count, status, now, track_id))

    # ============================================================
    # 장기보관 알림 대상 조회
    # ============================================================

    def get_long_term_alert_targets(self, min_days=7, min_hits=2):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT
                    'UNKNOWN' AS target_type,
                    track_id AS target_id,
                    last_photo_id,
                    NULL AS container_class,
                    first_seen, last_seen, hit_count,
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2, crop_path,
                    CAST(julianday('now','localtime') - julianday(first_seen)
                         AS INTEGER) + 1 AS storage_days
                FROM unknown_track
                WHERE status='CANDIDATE'
                  AND hit_count >= ?
                  AND (CAST(julianday('now','localtime') - julianday(first_seen)
                       AS INTEGER) + 1) >= ?

                UNION ALL

                SELECT
                    'CONTENT_UNKNOWN' AS target_type,
                    track_id AS target_id,
                    last_photo_id,
                    container_class,
                    first_seen, last_seen, hit_count,
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2, crop_path,
                    CAST(julianday('now','localtime') - julianday(first_seen)
                         AS INTEGER) + 1 AS storage_days
                FROM content_unknown_track
                WHERE status='ACTIVE'
                  AND hit_count >= ?
                  AND (CAST(julianday('now','localtime') - julianday(first_seen)
                       AS INTEGER) + 1) >= ?

                ORDER BY storage_days DESC, target_type, target_id
            """, (min_hits, min_days, min_hits, min_days)).fetchall()
            return rows

    def get_last_alert(self, target_type, target_id):
        with self.connect() as conn:
            return conn.execute("""
                SELECT * FROM alert_history
                WHERE target_type=? AND target_id=?
                ORDER BY alerted_at DESC, alert_id DESC
                LIMIT 1
            """, (target_type, target_id)).fetchone()

    def insert_alert_history(
        self, target_type, target_id, photo_id, storage_days, alerted_at=None
    ):
        alerted_at = alerted_at or datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cursor = conn.execute("""
                INSERT INTO alert_history (
                    target_type, target_id, photo_id, storage_days, alerted_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                target_type, target_id, photo_id, storage_days, alerted_at
            ))
            return cursor.lastrowid
