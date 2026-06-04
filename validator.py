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

# ─── Pattern: tên cột generic (vô nghĩa) ─────────────────────────────────────
_GENERIC_COL_RE = re.compile(
    r"^(unnamed[:\s_]*\d*|col\d+|\d+|column\d*)$", re.IGNORECASE
)

# ─── Pattern: cột đầu là tiêu đề phụ lục / biểu mẫu ─────────────────────────
# Bắt: "Phụ lục 1", "PHỤ LỤC I", "Mẫu số B01", "Biểu mẫu", "Appendix A"...
_APPENDIX_COL_RE = re.compile(
    r"^(ph[uụ]\s*l[uụ]c|phu\s*luc|ph\.\s*l\.?|"
    r"m[aẫ]u\s*s[oố]|bi[eê]u\s*m[aẫ]u|bi[eê]u\s*s[oố]|"
    r"appendix|annex|template\s*(no|number|\d))",
    re.IGNORECASE,
)

# ─── Pattern: keyword thời gian trong tên cột ────────────────────────────────
_TIME_COL_RE = re.compile(
    r"(n[aă]m|year|th[aá]ng|month|qu[yý]|quarter|ng[aà]y|date|"
    r"k[yỳ]|period|th[oờ]i\s*gian|time|as_of|fiscal|dt\b)",
    re.IGNORECASE,
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


def _is_explicit_appendix(col0: str) -> bool:
    """Return True nếu tên cột đầu khớp pattern phụ lục / biểu mẫu rõ ràng."""
    return bool(_APPENDIX_COL_RE.match(col0.strip()))


def _is_merged_cell_header(cols: list[str]) -> bool:
    """
    Return True nếu DataFrame có vẻ được đọc với merged-cell title làm header:
    cột đầu dài + >= 60% cột còn lại là Unnamed.

    Đây KHÔNG phải là junk chắc chắn — có thể là file thật với title ở row 0.
    Caller nên thử re-read với header=1 hoặc header=2.
    """
    if len(cols) <= 2:
        return False
    col0 = cols[0].strip()
    if len(col0) <= 15 or _is_generic_col(col0):
        return False
    unnamed_count = sum(1 for c in cols[1:] if _is_generic_col(c))
    return (unnamed_count / len(cols[1:])) >= 0.60


def _has_time_dimension(df) -> bool:
    """
    Trả về True nếu file có chiều thời gian — dấu hiệu của dataset thực,
    không phải danh sách tra cứu hay phụ lục tĩnh.

    Kiểm tra:
    - Tên cột chứa keyword thời gian (năm, year, tháng, quý, date...)
    - Hoặc có cột với >= 3 giá trị trông như năm (2000–2035)
    """
    for col in df.columns:
        if _TIME_COL_RE.search(str(col)):
            return True

    for col in df.columns:
        try:
            nums = pd.to_numeric(df[col], errors="coerce").dropna()
            year_like = nums[(nums >= 2000) & (nums <= 2035)]
            if len(year_like) >= 3:
                return True
        except Exception:
            pass

    return False


def _compute_quality_score(df) -> float:
    """
    Tính quality score 0–1 cho DataFrame.

    score = (non_null_ratio    × 0.30)
          + (header_ratio      × 0.30)   ← tỉ lệ cột có tên có nghĩa
          + (numeric_col_ratio × 0.20)
          + (time_score        × 0.20)   ← có chiều thời gian không?

    Khác với phiên bản cũ:
    - header_score giờ là TỈ LỆ (không phải 0/1) — bắt file
      có 1 cột tên thật nhưng 10 cột Unnamed
    - thêm time_score để ưu tiên dataset dạng time-series
    """
    total_cells = df.size or 1
    non_null_ratio = df.notna().sum().sum() / total_cells

    cols = [str(c) for c in df.columns]
    meaningful = sum(1 for c in cols if not _is_generic_col(c))
    header_ratio = meaningful / len(cols) if cols else 0.0

    numeric_cols = sum(
        1 for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
        or pd.to_numeric(df[col], errors="coerce").notna().any()
    )
    numeric_col_ratio = numeric_cols / len(df.columns) if df.columns.size > 0 else 0.0

    time_score = 1.0 if _has_time_dimension(df) else 0.0

    return (
        (non_null_ratio    * 0.30)
        + (header_ratio    * 0.30)
        + (numeric_col_ratio * 0.20)
        + (time_score      * 0.20)
    )


def _try_fix_header(filepath: Path, df):
    """
    Nếu DataFrame có vấn đề header (merged-cell title hoặc toàn Unnamed),
    quét tối đa 20 row đầu để tìm row thực sự là header.

    Tiêu chí: row có >= 3 giá trị non-NaN, và kết quả có nhiều cột
    có-nghĩa hơn lần đọc mặc định.

    Trả về DataFrame tốt hơn nếu tìm được, ngược lại trả về df gốc.
    """
    col_names = [str(c) for c in df.columns]
    if not _is_merged_cell_header(col_names) and not all(_is_generic_col(c) for c in col_names):
        return df  # không cần fix

    meaningful_orig = sum(1 for c in col_names if not _is_generic_col(c))

    try:
        df_raw = pd.read_excel(filepath, header=None, nrows=20)
        for i, row in df_raw.iterrows():
            if row.notna().sum() < 3:
                continue
            try:
                df_alt = pd.read_excel(filepath, header=int(i), nrows=1000)
                alt_cols = [str(c) for c in df_alt.columns]
                meaningful_alt = sum(1 for c in alt_cols if not _is_generic_col(c))
                if meaningful_alt > meaningful_orig:
                    return df_alt
            except Exception:
                continue
    except Exception:
        pass

    return df


def validate_file(filepath: Path) -> FileMetadata:
    """
    Đọc file, kiểm tra tính hợp lệ, trả về FileMetadata.

    Điều kiện hợp lệ:
    - Đọc được (không corrupt)
    - Có ít nhất 2 cột và 20 dòng data
    - Không phải toàn NaN (>60% NaN → reject)
    - Tên cột không phải toàn generic
    - Có ít nhất 1 cột numeric
    - Không phải bảng phụ lục / merged-cell header (xem _detect_junk_table)
    """
    meta = FileMetadata(filepath=filepath)
    meta.file_size_kb = filepath.stat().st_size / 1024
    ext = filepath.suffix.lower().lstrip(".")
    meta.filetype = ext

    if not HAS_PANDAS:
        meta.valid = True
        meta.error = "pandas not available, skipped validation"
        return meta

    try:
        if ext in ("xlsx", "xls"):
            df = pd.read_excel(filepath, nrows=1000)
            df = _try_fix_header(filepath, df)
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
    if df.shape[0] < 20:
        meta.error = f"Quá ít dòng: {df.shape[0]} (cần ≥20)"
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
    col_names = [str(c) for c in df.columns]  # may have changed after header retry
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

    # ── Junk table detection ──────────────────────────────────────────────────
    col_names = [str(c) for c in df.columns]
    if _is_explicit_appendix(col_names[0] if col_names else ""):
        meta.error = f"Bảng phụ lục/biểu mẫu: cột đầu = '{col_names[0][:60]}'"
        return meta
    # Nếu vẫn còn merged-cell header sau retry → reject
    if _is_merged_cell_header(col_names):
        meta.error = (
            f"Merged-cell header không giải được: '{col_names[0][:60]}'"
        )
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
