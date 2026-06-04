"""
Main pipeline — chạy thủ công để crawl xlsx/csv đa lĩnh vực.

Usage:
    python main.py                        # chạy với default settings
    python main.py --topics finance health --limit 20
    python main.py --resume               # tiếp tục từ lần trước (skip query đã check)
"""

import argparse
import asyncio
import logging
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ── Setup logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/crawler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ── Imports ───────────────────────────────────────────────────────────────────
from queries import build_queries, get_quick_queries, TOPICS
from searxng_client import SearXNGClient, load_proxies
from downloader import FileDownloader
from validator import validate_file
from classifier import classify_file
from catalog import CatalogDB


# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_SEARXNG_URL = "http://localhost:8080"
OUTPUT_DIR          = Path("output/files")
CATALOG_DB          = Path("output/catalog.db")
JSONL_EXPORT        = Path("output/catalog.jsonl")
QUERY_CHECKPOINT    = Path("output/checked_queries.txt")


async def run_pipeline(
    topics: list[str] | None = None,
    limit_queries: int | None = None,
    searxng_url: str = DEFAULT_SEARXNG_URL,
    resume: bool = False,
    dry_run: bool = False,
    lang: str = "vi",
    delay: float = 5.0,
    min_quality: float = 0.5,
    proxy_file: str | None = None,
):
    """
    Full pipeline:
      1. Build queries
      2. Search với SearXNG → list file URL
      3. Download
      4. Validate
      5. Classify
      6. Lưu catalog
      7. Export JSONL
    """
    logger.info("=" * 60)
    logger.info("XLSX/CSV Crawler Pipeline")
    logger.info("=" * 60)

    pipeline_chunk_size = 50

    # ── 1. Build queries ──────────────────────────────────────────────────────
    if topics:
        invalid = [t for t in topics if t not in TOPICS]
        if invalid:
            logger.warning(f"Topic không hợp lệ (bỏ qua): {invalid}")
        topics = [t for t in topics if t in TOPICS]

    queries = build_queries(
        topics=topics,
        filetypes=["filetype:xlsx", "filetype:csv"],
        lang="vi",
        max_per_topic=1000,
    )

    if limit_queries:
        random.shuffle(queries)
        queries = queries[:limit_queries]

    logger.info(f"Queries prepared: {len(queries)}")

    checked_queries: set[str] = set()
    if resume and QUERY_CHECKPOINT.exists():
        checked_queries = {
            line.strip()
            for line in QUERY_CHECKPOINT.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        before = len(queries)
        queries = [q for q in queries if q["query"] not in checked_queries]
        logger.info(
            f"Resume(query-checkpoint): skipped {before - len(queries)} query(s), "
            f"remaining {len(queries)}"
        )

    if dry_run:
        logger.info("[DRY RUN] 5 query mẫu:")
        for q in queries[:5]:
            logger.info(f"  [{q['topic']}] {q['query']}")
        return

    # ── 2. Search ─────────────────────────────────────────────────────────────
    proxies = load_proxies(proxy_file) if proxy_file else []
    searxng = SearXNGClient(
        base_url=searxng_url,
        engines=["google"],
        language="vi",
        max_results=10,
        proxies=proxies,
    )
    logger.info(f"Searching via SearXNG @ {searxng_url} (chunked pipeline) ...")

    # ── 3. Download ───────────────────────────────────────────────────────────
    downloader = FileDownloader(output_dir=OUTPUT_DIR, concurrency=5)

    # ── 4–6. Validate → Classify → Catalog ───────────────────────────────────
    db = CatalogDB(CATALOG_DB)

    found_total = 0
    downloaded_total = 0
    validated_total = 0
    saved = 0

    total_queries = len(queries)
    for i in range(0, total_queries, pipeline_chunk_size):
        chunk_no = i // pipeline_chunk_size + 1
        chunk = queries[i:i + pipeline_chunk_size]
        logger.info(
            f"Chunk {chunk_no}: search {len(chunk)} queries "
            f"({min(i + len(chunk), total_queries)}/{total_queries})"
        )

        search_results = await searxng.search_batch(
            chunk,
            concurrency=1,
            delay=delay,
            chunk_size=len(chunk),
            chunk_pause=0.0,
        )
        found_total += len(search_results)

        if not search_results:
            logger.info(f"Chunk {chunk_no}: no downloadable URL")
        else:
            dl_results = await downloader.download_batch(search_results)
            successful = [r for r in dl_results if r.success]
            downloaded_total += len(successful)
            logger.info(f"Chunk {chunk_no}: downloaded {len(successful)}/{len(dl_results)} file(s)")

            for dl in successful:
                # Validate
                meta = validate_file(dl.filepath)
                if not meta.valid:
                    logger.debug(f"  INVALID {dl.filepath.name}: {meta.error}")
                    continue

                # Quality gate
                if meta.quality_score < min_quality:
                    logger.debug(
                        f"  LOW QUALITY {dl.filepath.name}: "
                        f"score={meta.quality_score:.2f} < {min_quality}"
                    )
                    continue
                validated_total += 1

                # Classify
                cls = await classify_file(
                    meta, use_llm_threshold=0.2, source_domain=dl.domain
                )
                logger.info(
                    f"  {dl.filepath.name} → [{cls.topic}] "
                    f"conf={cls.confidence:.2f} score={meta.quality_score:.2f} ({cls.method})"
                )

                # Save
                if db.insert(dl, meta, cls):
                    saved += 1

        # Checkpoint theo query đã được xử lý search xong.
        with QUERY_CHECKPOINT.open("a", encoding="utf-8") as f:
            for q in chunk:
                f.write(q["query"] + "\n")

    logger.info(f"Catalog: {saved} new records saved")

    # ── 7. Export JSONL ───────────────────────────────────────────────────────
    n = db.export_jsonl(JSONL_EXPORT)

    # ── Summary ───────────────────────────────────────────────────────────────
    stats = db.stats()
    db.close()

    logger.info("")
    logger.info("─── SUMMARY ─────────────────────────────────")
    logger.info(f"URLs found from search   : {found_total}")
    logger.info(f"Files downloaded         : {downloaded_total}")
    logger.info(f"Files validated          : {validated_total}")
    logger.info(f"Total files in catalog : {stats['total_files']}")
    logger.info(f"JSONL export           : {JSONL_EXPORT} ({n} records)")
    logger.info("By sub-category:")
    for row in stats["by_category"]:
        logger.info(
            f"  {row['sub_category']:<20} {row['cnt']:>4} files  "
            f"{row['total_rows'] or 0:>8,} rows  "
            f"{(row['total_mb'] or 0):.1f} MB"
        )
    logger.info("─────────────────────────────────────────────")


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Crawl xlsx/csv files đa lĩnh vực qua SearXNG"
    )
    p.add_argument(
        "--topics", nargs="+",
        choices=list(TOPICS.keys()),
        help="Lọc theo topic (mặc định: tất cả)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Giới hạn số query (để test nhanh, vd --limit 20)",
    )
    p.add_argument(
        "--searxng", default=DEFAULT_SEARXNG_URL,
        help=f"URL SearXNG instance (default: {DEFAULT_SEARXNG_URL})",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Bỏ qua query đã check trong lần trước (query checkpoint)",
    )
    p.add_argument(
        "--lang", default="vi", choices=["vi"],
        help="Ngôn ngữ keyword: vi (bắt buộc)",
    )
    p.add_argument(
        "--delay", type=float, default=15.0,
        help="Delay (giây) giữa các search request (default: 5.0)",
    )
    p.add_argument(
        "--min-quality", type=float, default=0.5,
        help="Ngưỡng quality_score tối thiểu để lưu file (0.0–1.0, default: 0.5)",
    )
    p.add_argument(
        "--proxy-file", default=None,
        help="Đường dẫn file proxy (format: ip:port:user:password, mỗi dòng 1 proxy)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Chỉ in query, không tải file",
    )
    return p.parse_args()


if __name__ == "__main__":
    Path("output").mkdir(exist_ok=True)
    args = parse_args()
    asyncio.run(run_pipeline(
        topics=args.topics,
        limit_queries=args.limit,
        searxng_url=args.searxng,
        resume=args.resume,
        dry_run=args.dry_run,
        lang=args.lang,
        delay=args.delay,
        min_quality=args.min_quality,
        proxy_file=args.proxy_file,
    ))
