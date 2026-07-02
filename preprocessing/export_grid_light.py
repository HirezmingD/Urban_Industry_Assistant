"""Export land_grid_L0 rows to grid_light.geojson (streaming)."""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("db/uia.db")
OUT_PATH = Path("static/grid_light.geojson")
BATCH_SIZE = 5000


def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 先查总数
    total = cursor.execute("SELECT COUNT(*) FROM land_grid_L0").fetchone()[0]
    print(f"Total rows: {total}")

    cursor.execute(
        "SELECT grid_id, min_lng, min_lat, max_lng, max_lat, land_type "
        "FROM land_grid_L0 ORDER BY grid_id"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[\n')
        first = True
        while True:
            rows = cursor.fetchmany(BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                polygon = [[
                    [row["min_lng"], row["min_lat"]],
                    [row["max_lng"], row["min_lat"]],
                    [row["max_lng"], row["max_lat"]],
                    [row["min_lng"], row["max_lat"]],
                    [row["min_lng"], row["min_lat"]],
                ]]
                feature = {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": polygon},
                    "properties": {"land_type": row["land_type"] or ""},
                }
                if not first:
                    f.write(",\n")
                first = False
                json.dump(feature, f, ensure_ascii=False, separators=(",", ":"))
                written += 1
            print(f"  written {written}/{total} ...")

        f.write("\n]}\n")

    conn.close()

    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\nDone: {OUT_PATH} ({written} features, {size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
