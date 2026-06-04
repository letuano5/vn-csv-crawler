"""
SearXNG search client — gọi instance self-hosted để lấy URL file.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    domain: str = ""
    filetype: str = ""
    query: str = ""
    topic: str = ""

    def __post_init__(self):
        parsed = urlparse(self.url)
        self.domain = parsed.netloc
        ext = parsed.path.rsplit(".", 1)[-1].lower()
        self.filetype = ext if ext in ("xlsx", "xls", "csv") else ""


@dataclass
class SearXNGClient:
    """
    Client gọi SearXNG JSON API.

    Args:
        base_url:   URL instance SearXNG, vd "http://localhost:8080"
        engines:    danh sách engine SearXNG muốn dùng
        language:   ngôn ngữ kết quả (en / vi / all)
        timeout:    timeout mỗi request (giây)
        max_results: số kết quả tối đa mỗi query
    """
    base_url: str = "http://localhost:8080"
    engines: list[str] = field(default_factory=lambda: ["google"])
    language: str = "vi"
    timeout: float = 15.0
    max_results: int = 10
    max_retries: int = 4
    retry_statuses: tuple[int, ...] = (429, 503)
    backoff_base: float = 1.0
    backoff_cap: float = 20.0
    jitter_ratio: float = 0.35

    def _retry_sleep_seconds(self, attempt: int) -> float:
        """Exponential backoff có jitter để tránh burst đồng bộ."""
        base = min(self.backoff_cap, self.backoff_base * (2 ** (attempt - 1)))
        jitter = base * self.jitter_ratio * random.random()
        return base + jitter

    async def search(self, query: str, topic: str = "") -> list[SearchResult]:
        """Gọi SearXNG, trả về list SearchResult chỉ chứa xlsx/csv/xls."""
        params = {
            "q":        query,
            "format":   "json",
            "engines":  ",".join(self.engines),
            "language": self.language,
        }
        url = f"{self.base_url}/search?{urlencode(params)}"

        data: dict = {}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base_url,
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = await client.get(url, headers=headers)

                    if resp.status_code in self.retry_statuses:
                        if attempt == self.max_retries:
                            logger.warning(
                                "SearXNG retry exhausted for '%s' (status=%s)",
                                query,
                                resp.status_code,
                            )
                            return []

                        sleep_s = self._retry_sleep_seconds(attempt)
                        logger.warning(
                            "SearXNG throttled for '%s' (status=%s), retry %s/%s in %.2fs",
                            query,
                            resp.status_code,
                            attempt,
                            self.max_retries,
                            sleep_s,
                        )
                        await asyncio.sleep(sleep_s)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    break

                except httpx.HTTPError as e:
                    if attempt == self.max_retries:
                        logger.warning(f"SearXNG request failed for '{query}': {e}")
                        return []

                    sleep_s = self._retry_sleep_seconds(attempt)
                    logger.warning(
                        "SearXNG transient error for '%s': %s, retry %s/%s in %.2fs",
                        query,
                        e,
                        attempt,
                        self.max_retries,
                        sleep_s,
                    )
                    await asyncio.sleep(sleep_s)
                except Exception as e:
                    logger.error(f"Unexpected error searching '{query}': {e}")
                    return []

        results = []
        for item in data.get("results", [])[:self.max_results]:
            item_url = item.get("url", "")
            # Chỉ giữ URL trỏ thẳng đến file
            if not any(item_url.lower().endswith(ext) for ext in (".xlsx", ".xls", ".csv")):
                # Fallback: kiểm tra content-type hint trong snippet
                snippet = item.get("content", "").lower()
                if not any(ext in item_url.lower() for ext in ("xlsx", "xls", "csv")):
                    if "spreadsheet" not in snippet and "csv" not in snippet:
                        continue

            results.append(SearchResult(
                url=item_url,
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                query=query,
                topic=topic,
            ))

        logger.info(f"Query '{query}' → {len(results)} file URLs found")
        return results

    async def search_batch(
        self,
        queries: list[dict],
        concurrency: int = 1,
        delay: float = 5.0,
        chunk_size: int = 200,
        chunk_pause: float = 8.0,
    ) -> list[SearchResult]:
        """
        Tìm kiếm nhiều query song song với rate-limit nhẹ.

        Args:
            queries:     list dict từ queries.build_queries()
            concurrency: số query chạy song song (bị ép về 1)
            delay:       giây nghỉ bắt buộc giữa 2 query liên tiếp (>=15s)
            chunk_size:  số query xử lý mỗi chunk để tránh dồn hàng nghìn task cùng lúc
            chunk_pause: giây nghỉ giữa các chunk lớn
        """
        # Yêu cầu vận hành: luôn chạy tuần tự và giữ tối thiểu 15s giữa hai query.
        concurrency = 1
        delay = max(delay, 5.0)

        sem = asyncio.Semaphore(concurrency)
        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()

        async def _one(q: dict):
            async with sem:
                results = await self.search(q["query"], topic=q.get("topic", ""))
                await asyncio.sleep(delay)
                return results

        total = len(queries)
        if total == 0:
            return []

        for idx in range(0, total, chunk_size):
            chunk_no = idx // chunk_size + 1
            chunk = queries[idx:idx + chunk_size]

            logger.info(
                "SearXNG chunk %s: processing %s queries (%s/%s)",
                chunk_no,
                len(chunk),
                min(idx + len(chunk), total),
                total,
            )

            tasks = [_one(q) for q in chunk]
            batches = await asyncio.gather(*tasks, return_exceptions=True)

            for batch in batches:
                if isinstance(batch, Exception):
                    continue
                for r in batch:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)

            if idx + chunk_size < total and chunk_pause > 0:
                pause_s = chunk_pause + (chunk_pause * 0.25 * random.random())
                logger.info(
                    "SearXNG chunk %s done, sleeping %.2fs before next chunk",
                    chunk_no,
                    pause_s,
                )
                await asyncio.sleep(pause_s)

        logger.info(f"Batch search done: {len(all_results)} unique file URLs")
        return all_results
