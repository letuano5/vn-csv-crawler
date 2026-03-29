"""
Lưu metadata vào SQLite + export JSONL cho training pipeline.
"""

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE NOT NULL,
    filepath      TEXT,
    content_hash  TEXT,
    filetype      TEXT,
    file_size_kb  REAL,
    n_rows        INTEGER,
    n_cols        INTEGER,
    columns_json  TEXT,       -- JSON array tên cột
    sample_json   TEXT,       -- JSON object col→[vals]
    topic         TEXT,
    confidence    REAL,
    classify_method TEXT,
    domain        TEXT,
    query         TEXT,
    crawled_at    TEXT,
    valid         INTEGER     -- 0/1
);

CREATE INDEX IF NOT EXISTS idx_topic ON files(topic);
CREATE INDEX IF NOT EXISTS idx_hash  ON files(content_hash);
"""


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
        self._conn.commit()
        logger.info(f"CatalogDB opened: {db_path}")

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
                   topic, confidence, classify_method,
                   domain, query, crawled_at, valid)
                VALUES
                  (?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?,?)
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
                    classify_result.topic,
                    classify_result.confidence,
                    classify_result.method,
                    download_result.domain,
                    "",  # query — filled separately if needed
                    datetime.utcnow().isoformat(),
                    int(file_meta.valid),
                ),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def stats(self) -> dict:
        """Thống kê nhanh về catalog."""
        cur = self._conn.execute("""
            SELECT topic, COUNT(*) as cnt,
                   SUM(n_rows) as total_rows,
                   SUM(file_size_kb)/1024 as total_mb
            FROM files WHERE valid=1
            GROUP BY topic ORDER BY cnt DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        total = self._conn.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]
        return {"total_files": total, "by_topic": rows}

    def export_jsonl(self, output_path: Path, valid_only: bool = True) -> int:
        """
        Export toàn bộ catalog ra JSONL để dùng trong training pipeline.
        Mỗi dòng là 1 JSON record.
        Trả về số record đã xuất.
        """
        where = "WHERE valid=1" if valid_only else ""
        cur = self._conn.execute(f"SELECT * FROM files {where}")
        rows = cur.fetchall()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for row in rows:
                record = dict(row)
                # Parse lại JSON string
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
