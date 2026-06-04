"""
Async downloader: tải file xlsx/csv, validate, dedup theo content hash.
"""

import asyncio
import hashlib
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ─── Junk URL/filename patterns ───────────────────────────────────────────────
JUNK_URL_PATTERNS: list[str] = [
    "/template/", "/form/", "/sample/", "/example/",
    "/demo/", "/test/", "/dummy/", "login", "register",
    "signup", "captcha",
]

JUNK_FILENAME_PATTERNS: list[str] = [
    "template", "sample", "form", "test", "dummy",
]

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
    query: str = ""


@dataclass
class FileDownloader:
    """
    Args:
        output_dir:  thư mục gốc lưu file
        timeout:     timeout mỗi request (giây)
        max_retries: số lần retry khi lỗi mạng
        concurrency: số download song song
        proxies:     list proxy URL (http://user:pwd@ip:port), rotate random
    """
    output_dir: Path = Path("output/files")
    timeout: float = 30.0
    max_retries: int = 3
    concurrency: int = 5
    proxies: list[str] = field(default_factory=list)

    # Internal state
    _seen_hashes: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _pick_proxy(self) -> str | None:
        """Chọn random 1 proxy URL từ danh sách."""
        return random.choice(self.proxies) if self.proxies else None
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

    def _is_junk_url(self, url: str) -> tuple[bool, str]:
        """
        Return (is_junk, reason) based on URL/filename pattern checks.

        Rejects URLs that match known junk patterns (templates, login pages,
        demo/test files) or have unsupported file extensions.
        """
        url_lower = url.lower()
        for pattern in JUNK_URL_PATTERNS:
            if pattern in url_lower:
                return True, f"URL contains junk pattern '{pattern}'"

        filename = urlparse(url).path.rsplit("/", 1)[-1].lower()
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        for pattern in JUNK_FILENAME_PATTERNS:
            if pattern in stem:
                return True, f"Filename contains junk pattern '{pattern}'"

        ext = urlparse(url).path.rsplit(".", 1)[-1].lower()
        if ext not in ("xlsx", "xls", "csv"):
            return True, f"Extension not allowed: .{ext}"

        return False, ""

    def _is_duplicate(self, content: bytes) -> tuple[bool, str]:
        h = hashlib.sha256(content).hexdigest()
        if h in self._seen_hashes:
            return True, h
        self._seen_hashes.add(h)
        return False, h

    # ── core download ─────────────────────────────────────────────────────────

    async def download_one(
        self, url: str, topic: str = "", domain: str = "", query: str = ""
    ) -> DownloadResult:
        """Tải 1 file, validate, lưu disk. Trả về DownloadResult."""
        # ── Junk URL filter (no network) ──────────────────────────────────────
        is_junk, reason = self._is_junk_url(url)
        if is_junk:
            logger.debug(f"REJECT junk URL {url}: {reason}")
            return DownloadResult(url=url, success=False, error=f"Junk URL: {reason}")

        ext = urlparse(url).path.rsplit(".", 1)[-1].lower()

        proxy = self._pick_proxy()

        # ── HEAD pre-check (optional: avoid downloading bad content-type) ─────
        try:
            async with httpx.AsyncClient(
                timeout=5.0, follow_redirects=True, headers=HEADERS,
                proxy=proxy,
            ) as head_client:
                head_resp = await head_client.head(url)
                ct = head_resp.headers.get("content-type", "").split(";")[0].strip()
                if ct and ct not in ALLOWED_CONTENT_TYPES:
                    logger.debug(f"REJECT HEAD content-type={ct} for {url}")
                    return DownloadResult(
                        url=url, success=False,
                        error=f"HEAD Content-Type rejected: {ct}",
                    )
        except Exception:
            pass  # HEAD unavailable or failed — proceed to GET

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=HEADERS,
                    proxy=proxy,
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
                    file_size=total, topic=topic, domain=domain, query=query,
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
                    url=sr.url, topic=sr.topic, domain=sr.domain, query=sr.query
                )

        results = await asyncio.gather(*[_one(r) for r in search_results])

        ok  = sum(1 for r in results if r.success)
        dup = sum(1 for r in results if "Duplicate" in r.error)
        fail = len(results) - ok - dup
        logger.info(f"Download done — ok={ok}, duplicate={dup}, failed={fail}")
        return list(results)
