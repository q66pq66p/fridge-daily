import sys
from pathlib import Path

# 프로젝트 루트를 Python module path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import CONTENT_UNKNOWN_CLASSES
from src.database import FridgeDatabase

def main():
    db=FridgeDatabase(); db.initialize()
    marks=",".join("?" for _ in CONTENT_UNKNOWN_CLASSES)
    with db.connect() as conn:
        rows=conn.execute(
            f"""SELECT track_id, container_class FROM content_unknown_track
                WHERE status='ACTIVE' AND container_class NOT IN ({marks})
                ORDER BY track_id""",
            tuple(sorted(CONTENT_UNKNOWN_CLASSES))
        ).fetchall()
        print(f"정리 대상 CONTENT_UNKNOWN: {len(rows)}개")
        for r in rows:
            print(f"CU{r['track_id']:06d} {r['container_class']} -> EXCLUDED")
        if rows:
            ids=[r["track_id"] for r in rows]
            q=",".join("?" for _ in ids)
            conn.execute(
                f"""UPDATE content_unknown_track SET status='EXCLUDED',
                    updated_at=datetime('now','localtime')
                    WHERE track_id IN ({q})""", ids)
        print("정리 완료")

if __name__=="__main__":
    main()
