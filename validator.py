"""
Validate & extract metadata từ file xlsx/csv đã tải về.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas chưa cài — validation sẽ bị giới hạn")


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


def validate_file(filepath: Path) -> FileMetadata:
    """
    Đọc file, kiểm tra tính hợp lệ, trả về FileMetadata.

    Điều kiện hợp lệ:
    - Đọc được (không corrupt)
    - Có ít nhất 2 cột và 5 dòng data
    - Không phải toàn NaN
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
            # Thử detect encoding
            df, enc = _read_csv_smart(filepath)
            meta.encoding = enc
        else:
            meta.error = f"Extension không hỗ trợ: {ext}"
            return meta

    except Exception as e:
        meta.error = f"Không đọc được file: {e}"
        return meta

    # Kiểm tra shape
    if df.shape[0] < 5:
        meta.error = f"Quá ít dòng: {df.shape[0]}"
        return meta
    if df.shape[1] < 2:
        meta.error = f"Quá ít cột: {df.shape[1]}"
        return meta

    # Kiểm tra empty
    if df.isnull().all(axis=None).all() if hasattr(df.isnull().all(axis=None), 'all') else df.isnull().values.all():
        meta.error = "File toàn NaN"
        return meta

    # Fill metadata
    meta.valid = True
    meta.n_rows = len(df)
    meta.n_cols = len(df.columns)
    meta.columns = [str(c) for c in df.columns]

    # Sample values (3 giá trị đầu mỗi cột, bỏ NaN)
    for col in df.columns[:10]:  # giới hạn 10 cột để tránh quá dài
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

    # Fallback
    df = pd.read_csv(filepath, encoding="utf-8", errors="replace", nrows=1000)
    return df, "utf-8-replace"


def validate_batch(filepaths: list[Path]) -> list[FileMetadata]:
    """Validate nhiều file, log tóm tắt."""
    results = [validate_file(fp) for fp in filepaths]
    valid = sum(1 for r in results if r.valid)
    logger.info(f"Validation: {valid}/{len(results)} files hợp lệ")
    return results
