"""
Async downloader: tải file xlsx/csv, validate, dedup theo content hash.
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DatasetCrawler/1.0; "
        "+https://github.com/your-repo)"
    ),
    "Accept": "*/*",
}

ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",   # xls
    "text/csv",
    "application/csv",
    "application/octet-stream",   # generic — kiểm tra ext
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB — bỏ file quá lớn


@dataclass
class DownloadResult:
    url: str
    success: bool
    filepath: Path | None = None
    content_hash: str = ""
    filetype: str = ""
    file_size: int = 0
    error: str = ""
    topic: str = ""
    domain: str = ""


@dataclass
class FileDownloader:
    """
    Args:
        output_dir:  thư mục gốc lưu file
        timeout:     timeout mỗi request (giây)
        max_retries: số lần retry khi lỗi mạng
        concurrency: số download song song
    """
    output_dir: Path = Path("output/files")
    timeout: float = 30.0
    max_retries: int = 3
    concurrency: int = 5

    # Internal state
    _seen_hashes: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._seen_hashes = set()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _safe_filename(self, url: str) -> str:
        """Tạo tên file an toàn từ URL."""
        path = urlparse(url).path
        name = path.rsplit("/", 1)[-1]
        name = re.sub(r"[^\w.\-]", "_", name)[:120]
        return name or "file"

    def _topic_dir(self, topic: str) -> Path:
        d = self.output_dir / (topic or "misc")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _is_duplicate(self, content: bytes) -> tuple[bool, str]:
        h = hashlib.sha256(content).hexdigest()
        if h in self._seen_hashes:
            return True, h
        self._seen_hashes.add(h)
        return False, h

    # ── core download ─────────────────────────────────────────────────────────

    async def download_one(
        self, url: str, topic: str = "", domain: str = ""
    ) -> DownloadResult:
        """Tải 1 file, validate, lưu disk. Trả về DownloadResult."""
        ext = urlparse(url).path.rsplit(".", 1)[-1].lower()
        if ext not in ("xlsx", "xls", "csv"):
            return DownloadResult(url=url, success=False,
                                  error="URL không có extension xlsx/csv/xls")

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=HEADERS,
                ) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()

                        # Kiểm tra content-type
                        ct = resp.headers.get("content-type", "").split(";")[0].strip()
                        if ct and ct not in ALLOWED_CONTENT_TYPES:
                            return DownloadResult(url=url, success=False,
                                                  error=f"Content-type không hợp lệ: {ct}")

                        # Đọc có giới hạn size
                        chunks = []
                        total = 0
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            total += len(chunk)
                            if total > MAX_FILE_SIZE:
                                return DownloadResult(url=url, success=False,
                                                      error="File vượt giới hạn 50MB")
                            chunks.append(chunk)
                        content = b"".join(chunks)

                # Dedup
                is_dup, content_hash = self._is_duplicate(content)
                if is_dup:
                    return DownloadResult(url=url, success=False,
                                          error="Duplicate (content hash trùng)",
                                          content_hash=content_hash)

                # Lưu file
                filename = self._safe_filename(url)
                # Thêm hash ngắn để tránh trùng tên
                stem, suffix = filename.rsplit(".", 1) if "." in filename else (filename, ext)
                final_name = f"{stem}_{content_hash[:8]}.{suffix}"
                filepath = self._topic_dir(topic) / final_name
                filepath.write_bytes(content)

                logger.info(f"✓ {filepath.name} ({total/1024:.1f} KB) [{topic}]")
                return DownloadResult(
                    url=url, success=True, filepath=filepath,
                    content_hash=content_hash, filetype=ext,
                    file_size=total, topic=topic, domain=domain,
                )

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404, 410):
                    return DownloadResult(url=url, success=False,
                                          error=f"HTTP {e.response.status_code}")
                if attempt == self.max_retries:
                    return DownloadResult(url=url, success=False, error=str(e))
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPError as e:
                if attempt == self.max_retries:
                    return DownloadResult(url=url, success=False, error=str(e))
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                return DownloadResult(url=url, success=False, error=str(e))

        return DownloadResult(url=url, success=False, error="Max retries exceeded")

    # ── batch download ────────────────────────────────────────────────────────

    async def download_batch(
        self, search_results: list
    ) -> list[DownloadResult]:
        """
        Tải toàn bộ danh sách SearchResult song song.
        search_results: list SearchResult từ searxng_client
        """
        sem = asyncio.Semaphore(self.concurrency)

        async def _one(sr):
            async with sem:
                return await self.download_one(
                    url=sr.url, topic=sr.topic, domain=sr.domain
                )

        results = await asyncio.gather(*[_one(r) for r in search_results])

        ok  = sum(1 for r in results if r.success)
        dup = sum(1 for r in results if "Duplicate" in r.error)
        fail = len(results) - ok - dup
        logger.info(f"Download done — ok={ok}, duplicate={dup}, failed={fail}")
        return list(results)
