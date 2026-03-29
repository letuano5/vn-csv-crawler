#!/usr/bin/env python3
"""Quick test để check SearXNG connection"""
import asyncio
import httpx
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_searxng(base_url="http://localhost:8080"):
    """Test kết nối SearXNG server"""
    params = {
        "q": "test",
        "format": "json",
        "engines": "google",
    }
    from urllib.parse import urlencode
    url = f"{base_url}/search?{urlencode(params)}"
    
    logger.info(f"Testing connection to: {url}")
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": base_url,

        "X-Forwarded-For": "127.0.0.1",
        "X-Real-IP": "127.0.0.1",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            logger.info(f"Response status: {resp.status_code}")
            logger.info(f"Response body (first 500 chars): {resp.text[:500]}")
            return True
    except Exception as e:
        logger.error(f"Connection failed: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_searxng())
    print()
    if result:
        print("✅ SearXNG is reachable")
    else:
        print("❌ SearXNG not reachable — start it first:")
        print("   docker run -d -p 8080:8080 searxng/searxng")
