"""
Lưu metadata vào SQLite + export JSONL cho training pipeline.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    filepath        TEXT,
    content_hash    TEXT,
    filetype        TEXT,
    file_size_kb    REAL,
    n_rows          INTEGER,
    n_cols          INTEGER,
    columns_json    TEXT,       -- JSON array tên cột
    sample_json     TEXT,       -- JSON object col→[vals]
    topic           TEXT,       -- parent category (always "finance")
    sub_category    TEXT,       -- one of the 8 finance sub-categories
    confidence      REAL,
    quality_score   REAL,
    classify_method TEXT,
    domain          TEXT,
    query           TEXT,
    crawled_at      TEXT,
    valid           INTEGER     -- 0/1
);

CREATE INDEX IF NOT EXISTS idx_sub_category ON files(sub_category);
CREATE INDEX IF NOT EXISTS idx_hash         ON files(content_hash);
"""

# Columns added after initial schema — applied via ALTER TABLE if missing.
_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("sub_category",  "TEXT"),
    ("quality_score", "REAL"),
]


class CatalogDB:
    """
    SQLite catalog cho tất cả file đã crawl.

    Args:
        db_path: đường dẫn file .db (tạo mới nếu chưa có)
    """

    def __init__(self, db_path: Path = Path("output/catalog.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()
        logger.info(f"CatalogDB opened: {db_path}")

    def _migrate(self) -> None:
        """Add new columns to an existing DB if they are missing."""
        for col, coldef in _MIGRATION_COLUMNS:
            try:
                self._conn.execute(f"ALTER TABLE files ADD COLUMN {col} {coldef}")
                logger.debug(f"Migration: added column {col} {coldef}")
            except sqlite3.OperationalError:
                pass  # column already exists

    def insert(
        self,
        download_result,   # DownloadResult
        file_meta,         # FileMetadata
        classify_result,   # ClassificationResult
    ) -> bool:
        """
        Lưu 1 record. Trả về True nếu insert, False nếu URL đã tồn tại.
        """
        try:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO files
                  (url, filepath, content_hash, filetype, file_size_kb,
                   n_rows, n_cols, columns_json, sample_json,
                   topic, sub_category, confidence, quality_score, classify_method,
                   domain, query, crawled_at, valid)
                VALUES
                  (?,?,?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?,?)
                """,
                (
                    download_result.url,
                    str(file_meta.filepath) if file_meta.filepath else None,
                    download_result.content_hash,
                    download_result.filetype,
                    file_meta.file_size_kb,
                    file_meta.n_rows,
                    file_meta.n_cols,
                    json.dumps(file_meta.columns, ensure_ascii=False),
                    json.dumps(file_meta.sample_values, ensure_ascii=False),
                    "finance",                  # parent topic
                    classify_result.topic,      # sub_category
                    classify_result.confidence,
                    file_meta.quality_score,
                    classify_result.method,
                    download_result.domain,
                    "",
                    datetime.utcnow().isoformat(),
                    int(file_meta.valid),
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def stats(self) -> dict:
        """Thống kê nhanh về catalog, grouped by sub_category."""
        cur = self._conn.execute("""
            SELECT sub_category, COUNT(*) as cnt,
                   SUM(n_rows) as total_rows,
                   SUM(file_size_kb)/1024 as total_mb
            FROM files WHERE valid=1
            GROUP BY sub_category ORDER BY cnt DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        total = self._conn.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]
        return {"total_files": total, "by_category": rows}

    def export_jsonl(self, output_path: Path, valid_only: bool = True) -> int:
        """
        Export toàn bộ catalog ra JSONL để dùng trong training pipeline.
        Mỗi dòng là 1 JSON record.

        Returns:
            số record đã xuất.
        """
        where = "WHERE valid=1" if valid_only else ""
        cur = self._conn.execute(f"SELECT * FROM files {where}")
        rows = cur.fetchall()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for row in rows:
                record = dict(row)
                try:
                    record["columns"] = json.loads(record.pop("columns_json", "[]"))
                    record["sample_values"] = json.loads(record.pop("sample_json", "{}"))
                except Exception:
                    pass
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(rows)} records → {output_path}")
        return len(rows)

    def close(self):
        self._conn.close()
