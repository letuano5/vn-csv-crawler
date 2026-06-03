"""
Validate & extract metadata từ file xlsx/csv đã tải về.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas chưa cài — validation sẽ bị giới hạn")

# Cột bị coi là "generic" (vô nghĩa) khi tên khớp pattern này
_GENERIC_COL_RE = re.compile(
    r"^(unnamed[:\s_]*\d*|col\d+|\d+|column\d*)$", re.IGNORECASE
)


@dataclass
class FileMetadata:
    filepath: Path
    valid: bool = False
    filetype: str = ""
    n_rows: int = 0
    n_cols: int = 0
    columns: list[str] = field(default_factory=list)
    sample_values: dict = field(default_factory=dict)  # col → [val1, val2, ...]
    encoding: str = ""
    error: str = ""
    file_size_kb: float = 0.0
    quality_score: float = 0.0


def _is_generic_col(name: str) -> bool:
    """Return True if the column name looks auto-generated / meaningless."""
    return bool(_GENERIC_COL_RE.match(name.strip()))


def _compute_quality_score(df) -> float:
    """
    Compute a 0–1 quality score for a DataFrame.

    score = (non_null_ratio * 0.4) + (has_header_score * 0.3) + (numeric_col_ratio * 0.3)

    where:
      non_null_ratio    = fraction of non-null cells
      has_header_score  = 1.0 if column names look meaningful, 0.0 if all generic
      numeric_col_ratio = fraction of columns with at least one numeric value
    """
    import pandas as pd

    total_cells = df.size or 1
    non_null_ratio = df.notna().sum().sum() / total_cells

    cols = [str(c) for c in df.columns]
    generic_count = sum(1 for c in cols if _is_generic_col(c))
    has_header_score = 0.0 if generic_count == len(cols) else 1.0

    numeric_cols = sum(
        1 for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
        or pd.to_numeric(df[col], errors="coerce").notna().any()
    )
    numeric_col_ratio = numeric_cols / len(df.columns) if df.columns.size > 0 else 0.0

    return (non_null_ratio * 0.4) + (has_header_score * 0.3) + (numeric_col_ratio * 0.3)


def validate_file(filepath: Path) -> FileMetadata:
    """
    Đọc file, kiểm tra tính hợp lệ, trả về FileMetadata.

    Điều kiện hợp lệ:
    - Đọc được (không corrupt)
    - Có ít nhất 2 cột và 10 dòng data
    - Không phải toàn NaN (>60% NaN → reject)
    - Tên cột không phải toàn generic
    - Có ít nhất 1 cột numeric
    """
    meta = FileMetadata(filepath=filepath)
    meta.file_size_kb = filepath.stat().st_size / 1024
    ext = filepath.suffix.lower().lstrip(".")
    meta.filetype = ext

    if not HAS_PANDAS:
        meta.valid = True  # skip nếu không có pandas
        meta.error = "pandas not available, skipped validation"
        return meta

    try:
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(filepath, nrows=1000)
        elif ext == "csv":
            df, enc = _read_csv_smart(filepath)
            meta.encoding = enc
        else:
            meta.error = f"Extension không hỗ trợ: {ext}"
            return meta

    except Exception as e:
        meta.error = f"Không đọc được file: {e}"
        return meta

    # ── Shape checks ──────────────────────────────────────────────────────────
    if df.shape[0] < 10:
        meta.error = f"Quá ít dòng: {df.shape[0]} (cần ≥10)"
        return meta
    if df.shape[1] < 2:
        meta.error = f"Quá ít cột: {df.shape[1]} (cần ≥2)"
        return meta

    # ── NaN checks ────────────────────────────────────────────────────────────
    if df.isnull().values.all():
        meta.error = "File toàn NaN"
        return meta

    nan_ratio = df.isnull().sum().sum() / (df.size or 1)
    if nan_ratio > 0.60:
        meta.error = f"Quá nhiều NaN: {nan_ratio:.0%} (ngưỡng 60%)"
        return meta

    # ── Generic column names check ────────────────────────────────────────────
    col_names = [str(c) for c in df.columns]
    if all(_is_generic_col(c) for c in col_names):
        meta.error = "Tất cả tên cột đều generic (Unnamed, col0, 0, 1, ...)"
        return meta

    # ── Numeric columns check ─────────────────────────────────────────────────
    has_numeric = any(
        pd.api.types.is_numeric_dtype(df[col])
        or pd.to_numeric(df[col], errors="coerce").notna().any()
        for col in df.columns
    )
    if not has_numeric:
        meta.error = "Không có cột numeric — file thuần text"
        return meta

    # ── Fill metadata ─────────────────────────────────────────────────────────
    meta.valid = True
    meta.n_rows = len(df)
    meta.n_cols = len(df.columns)
    meta.columns = col_names
    meta.quality_score = _compute_quality_score(df)

    for col in df.columns[:10]:
        vals = df[col].dropna().head(3).tolist()
        meta.sample_values[str(col)] = [str(v)[:100] for v in vals]

    return meta


def _read_csv_smart(filepath: Path) -> tuple:
    """Thử nhiều encoding phổ biến, trả về (DataFrame, encoding_used)."""
    import pandas as pd

    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
    separators = [",", ";", "\t", "|"]

    for enc in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(filepath, encoding=enc, sep=sep, nrows=1000,
                                 on_bad_lines="skip", low_memory=False)
                if df.shape[1] >= 2:
                    return df, enc
            except Exception:
                continue

    df = pd.read_csv(filepath, encoding="utf-8", errors="replace", nrows=1000)
    return df, "utf-8-replace"


def validate_batch(filepaths: list[Path]) -> list[FileMetadata]:
    """Validate nhiều file, log tóm tắt."""
    results = [validate_file(fp) for fp in filepaths]
    valid = sum(1 for r in results if r.valid)
    logger.info(f"Validation: {valid}/{len(results)} files hợp lệ")
    return results
