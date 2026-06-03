# vn-csv-crawler

Pipeline tự động tìm, tải và phân loại file **xlsx/csv dữ liệu tài chính Việt Nam**,
dùng **SearXNG** (self-hosted) làm search engine.

```
output/
  files/
    macro_economy/       ← file phân loại theo sub-category
    banking_credit/
    stock_market/
    corporate_finance/
    fiscal_budget/
    forex_rates/
    investment_fund/
    debt_bond/
  catalog.db             ← SQLite metadata
  catalog.jsonl          ← export cho training pipeline
  crawler.log
```

---

## Kiến trúc pipeline

```
build_queries()
    │  sinh query filetype:xlsx/csv × 8 sub-categories × trusted domains
    ▼
SearXNGClient.search_batch()
    │  gọi SearXNG JSON API, rate-limit 15s/query
    ▼
FileDownloader.download_one()
    │  junk filter → HEAD check → GET stream → dedup SHA-256
    ▼
validate_file()
    │  shape / NaN / column / numeric check → quality_score
    ▼
classify_file()
    │  keyword heuristic → LLM fallback (nếu confidence < 0.2)
    ▼
CatalogDB.insert()
    │  lưu SQLite, topic + sub_category + quality_score
    ▼
export_jsonl()           ← output/catalog.jsonl
```

---

## Cài đặt

### 1. SearXNG (Docker)

```bash
# Dùng docker-compose có sẵn
docker compose up -d

# Hoặc chạy thủ công
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -v $(pwd)/settings.yml:/etc/searxng/settings.yml \
  searxng/searxng:latest

# Kiểm tra
curl "http://localhost:8080/search?q=test&format=json" | head -c 200
```

`settings.yml` phải có `json` trong `search.formats` — pipeline dùng JSON API.

### 2. Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

**requirements.txt:**
```
httpx       # HTTP client async (downloader + LLM call)
pandas      # đọc và validate xlsx/csv
openpyxl    # backend pandas cho .xlsx
aiofiles    # I/O async
aiohttp     # HTTP async
```

---

## Chạy pipeline

```bash
# Xem query sẽ sinh ra — không tải file
python3 main.py --dry-run --limit 10

# Chỉ một sub-category, 30 queries
python3 main.py --topics stock_market --limit 30

# Nhiều sub-categories
python3 main.py --topics macro_economy banking_credit forex_rates

# Toàn bộ 8 sub-categories
python3 main.py

# Tăng delay nếu bị rate-limit (default 15.0s)
python3 main.py --delay 30.0

# Resume từ lần trước (bỏ qua query đã check)
python3 main.py --resume

# SearXNG trên host khác
python3 main.py --searxng http://192.168.1.10:8080
```

### Tất cả CLI arguments

| Argument | Default | Mô tả |
|---|---|---|
| `--topics` | tất cả | lọc sub-category (xem danh sách bên dưới) |
| `--limit` | không giới hạn | số query tối đa (dùng để test) |
| `--delay` | `15.0` | giây nghỉ bắt buộc giữa 2 search request |
| `--resume` | `false` | bỏ qua query đã xử lý trong lần trước |
| `--searxng` | `http://localhost:8080` | URL SearXNG instance |
| `--dry-run` | `false` | chỉ in query, không tải file |
| `--lang` | `vi` | ngôn ngữ keyword |

### LLM fallback (tuỳ chọn)

Khi heuristic classifier có confidence < 0.2, pipeline tự động gọi **Claude Haiku**
để classify chính xác hơn. Cần set API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 main.py
```

---

## 8 Finance Sub-categories

### Danh sách topic hợp lệ cho `--topics`

| Topic | Phạm vi dữ liệu |
|---|---|
| `macro_economy` | GDP, lạm phát, CPI, cán cân thương mại, tài khoản vốn |
| `banking_credit` | Tín dụng, lãi suất, nợ xấu, NHNN, thanh khoản ngân hàng |
| `stock_market` | VNIndex, HNX, UPCOM, cổ phiếu, IPO, room ngoại |
| `corporate_finance` | Báo cáo tài chính, ROE, ROA, EBITDA, dòng tiền |
| `fiscal_budget` | Ngân sách nhà nước, thuế, nợ công, bội chi, Bộ Tài chính |
| `forex_rates` | Tỷ giá USD/VND, dự trữ ngoại hối, can thiệp tỷ giá |
| `investment_fund` | Quỹ đầu tư, ETF, FDI, NAV, ODA, chứng chỉ quỹ |
| `debt_bond` | Trái phiếu DN, trái phiếu Chính phủ, yield curve, coupon |

### Trusted finance domains

Queries có thêm `site:` filter cho các domain uy tín sau:

```
data.worldbank.org   imf.org              afi.org
ssi.com.vn           vndirect.com.vn      cafef.vn
finance.vietstock.vn sbv.gov.vn           mof.gov.vn
gso.gov.vn           cophieu68.vn         investing.com
fiingroup.vn
```

File từ trusted domain được **boost confidence 1.4×** khi classify.

---

## Bộ lọc file (downloader)

Trước khi download, pipeline từ chối URL theo 3 bước:

### Bước 1 — Junk URL patterns (không tốn network)

| Điều kiện | Ví dụ bị từ chối |
|---|---|
| Path chứa `/template/`, `/form/`, `/sample/` | `.../forms/mau-bieu.xlsx` |
| Path chứa `/demo/`, `/test/`, `/dummy/` | `.../demo/sample.csv` |
| URL chứa `login`, `register`, `signup`, `captcha` | `.../login?file=data.csv` |
| Tên file chứa `template`, `sample`, `test` | `test_data.xlsx` |
| Extension không phải `.xlsx`, `.xls`, `.csv` | `report.html` |

### Bước 2 — HEAD request (kiểm tra Content-Type)

Gửi HEAD request (timeout 5s) trước khi stream file:

| Content-Type | Kết quả |
|---|---|
| `application/vnd.openxmlformats-...` | ✅ cho phép |
| `application/vnd.ms-excel` | ✅ cho phép |
| `text/csv` | ✅ cho phép |
| `application/octet-stream` | ✅ cho phép |
| `text/html`, `application/json`... | ❌ từ chối |

> HEAD request thất bại (timeout, server không hỗ trợ) → bỏ qua, tiếp tục download.

### Bước 3 — Content-Type từ GET response

Kiểm tra lại khi nhận response thực tế (đã có từ trước, giữ nguyên).

---

## Validation chất lượng file

Sau khi tải về, file phải vượt qua các gate sau:

| Gate | Ngưỡng | Lý do |
|---|---|---|
| Số dòng | ≥ 10 | tránh file stub / header-only |
| Số cột | ≥ 2 | tránh file 1 cột |
| Tỉ lệ NaN | ≤ 60% | tránh file gần trống |
| Tên cột | ít nhất 1 tên có nghĩa | loại `Unnamed: 0`, `col1`, `0`, `1`... |
| Cột numeric | ít nhất 1 | loại file thuần text |

### quality_score (0.0 – 1.0)

Mỗi file hợp lệ được chấm điểm:

```
quality_score = (non_null_ratio   × 0.4)
              + (has_header_score × 0.3)
              + (numeric_col_ratio × 0.3)
```

| Thành phần | Trọng số | Ý nghĩa |
|---|---|---|
| `non_null_ratio` | 40% | tỉ lệ ô có dữ liệu |
| `has_header_score` | 30% | 1.0 nếu ≥1 tên cột có nghĩa, 0.0 nếu toàn generic |
| `numeric_col_ratio` | 30% | tỉ lệ cột chứa dữ liệu số |

Ví dụ điểm thực tế:
```
File ngân sách Bộ Tài chính:   95% filled, header VN, 70% cột số  → 0.89
File ETF NAV hàng ngày:        88% filled, header EN, 80% cột số  → 0.87
File junk / mẫu biểu:          30% filled, Unnamed cols, 10% số   → 0.15
```

---

## Catalog SQLite

### Schema

```sql
CREATE TABLE files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    filepath        TEXT,
    content_hash    TEXT,            -- SHA-256 dedup
    filetype        TEXT,            -- xlsx / xls / csv
    file_size_kb    REAL,
    n_rows          INTEGER,
    n_cols          INTEGER,
    columns_json    TEXT,            -- JSON array tên cột
    sample_json     TEXT,            -- JSON {col: [val1, val2, ...]}
    topic           TEXT,            -- luôn = "finance"
    sub_category    TEXT,            -- một trong 8 sub-categories
    confidence      REAL,            -- classifier confidence 0.0–1.0
    quality_score   REAL,            -- validator quality 0.0–1.0
    classify_method TEXT,            -- "keyword" | "llm"
    domain          TEXT,
    query           TEXT,
    crawled_at      TEXT,
    valid           INTEGER          -- 0 / 1
);
```

> **Migration tự động:** DB cũ chưa có `sub_category` / `quality_score` sẽ được
> `ALTER TABLE ADD COLUMN` khi khởi động — không cần xóa DB.

### Query catalog thủ công

```bash
# Thống kê theo sub-category
sqlite3 output/catalog.db "
  SELECT sub_category, COUNT(*) as files,
         ROUND(AVG(quality_score), 2) as avg_quality,
         SUM(n_rows) as total_rows
  FROM files WHERE valid=1
  GROUP BY sub_category ORDER BY files DESC;
"

# Top file chất lượng cao nhất
sqlite3 output/catalog.db "
  SELECT sub_category, quality_score, n_rows, filepath
  FROM files WHERE valid=1
  ORDER BY quality_score DESC LIMIT 20;
"

# File từ trusted domain
sqlite3 output/catalog.db "
  SELECT url, sub_category, quality_score
  FROM files WHERE domain LIKE '%sbv.gov.vn%' OR domain LIKE '%mof.gov.vn%';
"
```

### Dùng trong Python

```python
from catalog import CatalogDB
from pathlib import Path

db = CatalogDB(Path("output/catalog.db"))

# Thống kê
stats = db.stats()
print(stats["total_files"])
for row in stats["by_category"]:
    print(f"{row['sub_category']:<20} {row['cnt']:>4} files  "
          f"{row['total_rows'] or 0:>8,} rows  {row['total_mb'] or 0:.1f} MB")

# Export JSONL
db.export_jsonl(Path("output/catalog.jsonl"))
db.close()
```

### Format JSONL export

```json
{
  "url": "https://sbv.gov.vn/data/interest_rates_2024.xlsx",
  "filepath": "output/files/banking_credit/interest_rates_a1b2c3d4.xlsx",
  "filetype": "xlsx",
  "n_rows": 840,
  "n_cols": 6,
  "columns": ["Ngân hàng", "Kỳ hạn", "Lãi suất huy động", "Lãi suất cho vay", "Tháng", "Năm"],
  "sample_values": {"Ngân hàng": ["Vietcombank", "BIDV", "Techcombank"]},
  "topic": "finance",
  "sub_category": "banking_credit",
  "confidence": 0.91,
  "quality_score": 0.88,
  "classify_method": "keyword",
  "domain": "sbv.gov.vn",
  "crawled_at": "2024-11-15T08:32:11"
}
```

---

## Cấu trúc code

```
vn-csv-crawler/
├── main.py              ← entrypoint, CLI, pipeline orchestration
├── queries.py           ← sinh query filetype:xlsx/csv × 8 sub-categories
├── searxng_client.py    ← gọi SearXNG JSON API, rate-limit, retry
├── downloader.py        ← junk filter, HEAD check, async download, dedup SHA-256
├── validator.py         ← đọc file, quality gates, quality_score
├── classifier.py        ← keyword heuristic + LLM fallback, domain boost
├── catalog.py           ← SQLite CRUD + migration + JSONL export
├── requirements.txt
├── docker-compose.yml
└── settings.yml         ← SearXNG config
```

---

## Tuning & Troubleshooting

| Vấn đề | Giải pháp |
|---|---|
| SearXNG bị Google block (429) | Tăng `--delay 30` hoặc dùng proxy |
| Tải chậm | Tăng `concurrency` trong `FileDownloader` (default 5) |
| Quá nhiều file rác lọt qua | Lọc theo `quality_score` trong catalog; điều chỉnh ngưỡng trong `validate_file` |
| Classifier ra sai sub-category | Set `ANTHROPIC_API_KEY` để bật LLM fallback |
| DB cũ không có cột mới | Migration chạy tự động khi `CatalogDB()` khởi động |
| Muốn thêm trusted domain | Thêm vào `TRUSTED_FINANCE_DOMAINS` trong `queries.py` và `TRUSTED_DOMAINS` trong `classifier.py` |
| Resume không hoạt động | Kiểm tra file `output/checked_queries.txt` có tồn tại không |
