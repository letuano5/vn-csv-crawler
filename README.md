# xlsx-csv-crawler

Pipeline tự động tìm và tải file **xlsx/csv đa lĩnh vực** từ web,
dùng **SearXNG** (self-hosted) làm search engine.

```
output/
  files/
    finance/        ← file sắp xếp theo lĩnh vực
    health/
    education/
    ...
  catalog.db        ← SQLite metadata
  catalog.jsonl     ← export cho training pipeline
  crawler.log
```

---

## 1. Cài SearXNG (Docker — cách nhanh nhất)

```bash
# Tạo thư mục config
mkdir -p searxng-config

# Tạo settings.yml tối thiểu
cat > searxng-config/settings.yml << 'EOF'
use_default_settings: true

server:
  secret_key: "thay-bang-random-string-bat-ky"
  bind_address: "0.0.0.0:8080"

search:
  safe_search: 0
  formats:
    - html
    - json          # BẮT BUỘC — pipeline dùng JSON API

engines:
  - name: google
    engine: google
    shortcut: g
  - name: bing
    engine: bing
    shortcut: b
  - name: duckduckgo
    engine: duckduckgo
    shortcut: d
EOF

# Chạy SearXNG
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -v $(pwd)/searxng-config:/etc/searxng \
  searxng/searxng:latest

# Kiểm tra đang chạy
curl "http://localhost:8080/search?q=test&format=json" | head -c 200
```

> **Lưu ý**: SearXNG mặc định có rate limit từ Google/Bing.
> Nếu bị block, tăng `delay` trong `main.py` hoặc dùng proxy.

---

## 2. Cài Python dependencies

```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 3. Chạy pipeline

```bash
# Test nhanh — 10 query, không tải file
python main.py --dry-run --limit 10

# Chạy thật — tất cả lĩnh vực
python main.py

# Chỉ một số lĩnh vực
python main.py --topics finance health education

# Giới hạn query (để test)
python main.py --limit 30

# Tiếp tục lần trước (bỏ qua URL đã tải)
python main.py --resume

# SearXNG trên server khác
python main.py --searxng http://192.168.1.10:8080
```

---

## 4. Classifier lĩnh vực

Mặc định dùng **keyword heuristic** (nhanh, không cần API).

Nếu muốn dùng **Claude API** để classify chính xác hơn
(chỉ gọi khi confidence heuristic thấp):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python main.py
```

---

## 5. Dùng catalog

```python
from crawler.catalog import CatalogDB
from pathlib import Path

db = CatalogDB(Path("output/catalog.db"))

# Thống kê
print(db.stats())

# Export JSONL cho training
db.export_jsonl(Path("output/catalog.jsonl"))
db.close()
```

Format mỗi dòng JSONL:
```json
{
  "url": "https://data.worldbank.org/...",
  "filepath": "output/files/finance/gdp_data_a1b2c3d4.xlsx",
  "filetype": "xlsx",
  "n_rows": 1240,
  "n_cols": 8,
  "columns": ["Country", "Year", "GDP", "..."],
  "sample_values": {"Country": ["Vietnam", "Thailand"], "...": []},
  "topic": "finance",
  "confidence": 0.87,
  "domain": "data.worldbank.org",
  "crawled_at": "2025-01-15T08:32:11"
}
```

---

## 6. Cấu trúc code

```
xlsx-crawler/
  main.py                 ← entrypoint, CLI
  requirements.txt
  crawler/
    queries.py            ← sinh query filetype:xlsx/csv theo lĩnh vực
    searxng_client.py     ← gọi SearXNG JSON API
    downloader.py         ← async download + dedup + retry
    validator.py          ← đọc file, kiểm tra hợp lệ
    classifier.py         ← classify lĩnh vực (heuristic + LLM)
    catalog.py            ← SQLite + export JSONL
```

---

## 7. Tips & Tuning

| Vấn đề | Giải pháp |
|--------|-----------|
| SearXNG bị Google block | Tăng `delay` lên 3-5s, dùng ít engine hơn |
| Tải chậm | Tăng `concurrency` trong `FileDownloader` |
| Nhiều file rác | Tăng ngưỡng `n_rows` trong `validator.py` |
| Classify sai | Set `ANTHROPIC_API_KEY` để dùng LLM |
| Muốn thêm domain | Thêm vào `DOMAINS` trong `queries.py` |

---

## 8. Nguồn data tốt để thêm vào query

- `site:data.gov` — Open data US government
- `site:data.europa.eu` — EU open data
- `site:data.go.id` — Indonesia
- `site:data.gov.sg` — Singapore
- `site:kaggle.com/datasets` — Kaggle
- `site:zenodo.org` — Academic datasets
- `site:figshare.com` — Research data
- `site:worldbank.org` — World Bank
- `site:who.int` — World Health Organization
