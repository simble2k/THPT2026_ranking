import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, engine
from .models import ExamScore, Province
from .redis_client import redis_client

# Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scraper")

class ExamScraper:
    def __init__(self, base_url: str, concurrency: int = 10):
        self.base_url = base_url
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_score(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        url = self.base_url.format(sbd=candidate_id)
        async with self.semaphore:
            for attempt in range(settings.SCRAPE_RETRY_LIMIT):
                try:
                    async with self.session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and "result" in data:
                                return self.parse_data(candidate_id, data["result"])
                            return None
                        elif response.status == 404:
                            return None
                        else:
                            logger.warning(f"Status {response.status} for {candidate_id}")
                except Exception as e:
                    logger.error(
                        f"Attempt {attempt + 1} failed for {candidate_id}: {e}"
                    )
                    await asyncio.sleep(1)
            return None

    def parse_data(self, candidate_id: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        # Example parsing logic based on VnExpress structure
        # Adjusted to match our ExamScore model
        mapping = {
            "toan": "math",
            "ngu_van": "literature",
            "ngoai_ngu": "foreign_language",
            "vat_li": "physics",
            "hoa_hoc": "chemistry",
            "sinh_hoc": "biology",
            "lich_su": "history",
            "dia_li": "geography",
            "gdcd": "civic_education"
        }
        
        parsed = {"candidate_id": candidate_id, "province_code": candidate_id[:2]}
        for key, field in mapping.items():
            val = raw_data.get(key)
            try:
                parsed[field] = float(val) if val is not None and val != "" else None
            except ValueError:
                parsed[field] = None
        return parsed

    async def save_to_db(self, scores: List[Dict[str, Any]]):
        async with AsyncSessionLocal() as session:
            for score_data in scores:
                score = ExamScore(**score_data)
                # Use merge to handle existing records (resumable/idempotent)
                await session.merge(score)
            await session.commit()

    async def update_redis_distributions(self, scores: List[Dict[str, Any]]):
        # Placeholder for distribution update logic
        # Will be implemented in Phase 4
        pass

    async def run(self, province_codes: List[str], range_start: int = 1, range_end: int = 999999, max_consecutive_misses: int = 100):
        for p_code in province_codes:
            logger.info(f"Scraping province {p_code}")
            batch = []
            consecutive_misses = 0
            
            for i in range(range_start, range_end + 1):
                candidate_id = f"{p_code}{i:06d}"
                score = await self.fetch_score(candidate_id)
                
                if score:
                    batch.append(score)
                    consecutive_misses = 0 # Reset misses on success
                else:
                    consecutive_misses += 1
                
                if len(batch) >= 100:
                    await self.save_to_db(batch)
                    logger.info(f"Saved batch of {len(batch)} for {p_code}")
                    batch = []
                
                # Termination Heuristic: If we hit many consecutive 404s, move to next province
                if consecutive_misses >= max_consecutive_misses:
                    logger.info(f"Hit {consecutive_misses} consecutive misses for province {p_code}. Moving on.")
                    break

            if batch:
                await self.save_to_db(batch)

async def main():
    # Example usage
    # VnExpress template: https://diemthi.vnexpress.net/index/get-score?sbd={sbd}&year=2025
    # For testing, we might want to use a mock server or just test with a few IDs
    base_url = "https://diemthi.vnexpress.net/index/get-score?sbd={sbd}&year=2025"
    async with ExamScraper(base_url, concurrency=settings.SCRAPE_CONCURRENCY) as scraper:
        # Test with Hà Nội (01)
        await scraper.run(["01"], range_start=1, range_end=100)

if __name__ == "__main__":
    asyncio.run(main())
