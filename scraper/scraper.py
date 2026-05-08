import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .config import settings
from .database import AsyncSessionLocal
from .engine import BLOCKS, DistributionEngine
from .models import ExamScore, Province
from .redis_client import redis_client

# Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("scraper.log")],
)
logger = logging.getLogger("scraper")

CHECKPOINT_FILE = Path("scraper_checkpoint.json")


class CheckpointManager:
    @staticmethod
    def load() -> Dict[str, Any]:
        if CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
        return {"province_idx": 0, "last_id_offset": 1}

    @staticmethod
    def save(province_idx: int, last_id_offset: int):
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(
                {"province_idx": province_idx, "last_id_offset": last_id_offset}, f
            )


class StatsTracker:
    def __init__(self):
        self.start_time = time.time()
        self.total_scraped = 0
        self.total_valid = 0
        self.total_misses = 0
        self.total_errors = 0

    def log_stats(self, province: str):
        elapsed = time.time() - self.start_time
        rate = self.total_scraped / elapsed if elapsed > 0 else 0
        logger.info(
            f"Stats [{province}]: Scraped={self.total_scraped}, "
            f"Valid={self.total_valid}, Misses={self.total_misses}, "
            f"Errors={self.total_errors}, Rate={rate:.2f} req/s"
        )


class ExamScraper:
    def __init__(self, base_url: str, concurrency: int = 10, max_misses: int = 100):
        self.base_url = base_url
        self.concurrency = concurrency
        self.max_misses = max_misses
        self.session: Optional[aiohttp.ClientSession] = None
        self.provinces_cache: Dict[str, str] = {}
        self.stats = StatsTracker()
        self.subject_mapping = {
            "toán": "math",
            "ngữ văn": "literature",
            "ngoại ngữ": "foreign_language",
            "vật lý": "physics",
            "vật lí": "physics",
            "hóa học": "chemistry",
            "sinh học": "biology",
            "lịch sử": "history",
            "địa lý": "geography",
            "địa lí": "geography",
            "gdcd": "civic_education",
            "giáo dục công dân": "civic_education",
            "giáo dục kinh tế và pháp luật": "civic_education",
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)
        await self._load_provinces()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _load_provinces(self):
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            try:
                result = await session.execute(select(Province))
                for p in result.scalars().all():
                    self.provinces_cache[p.code] = p.region
            except Exception as e:
                logger.error(f"Failed to load provinces from DB: {e}")
                self.provinces_cache = {f"{i:02d}": "North" for i in range(1, 65)}

    async def fetch_score(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        url = self.base_url.format(sbd=candidate_id)
        base_delay = 1.0
        self.stats.total_scraped += 1

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://diemthi.vnexpress.net/",
        }

        for attempt in range(settings.SCRAPE_RETRY_LIMIT):
            try:
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        text = await response.text()
                        if (
                            "This Content Is Not Available" in text
                            or "Không tìm thấy" in text
                        ):
                            self.stats.total_misses += 1
                            return None

                        parsed = self.parse_html(candidate_id, text)
                        if parsed:
                            self.stats.total_valid += 1
                            return parsed

                        parsed = self._fallback_parse(candidate_id, text)
                        if parsed:
                            self.stats.total_valid += 1
                            logger.info(f"Self-healed parsing for {candidate_id}")
                            return parsed

                        self.stats.total_errors += 1
                        logger.warning(
                            f"Failed to parse 200 OK content for {candidate_id}"
                        )
                        return None
                    elif response.status == 404:
                        self.stats.total_misses += 1
                        return None
                    elif response.status == 429:
                        self.stats.total_errors += 1
                        logger.warning("Rate limited (429). Increasing delay.")
                        await asyncio.sleep(20 * (attempt + 1))
                    else:
                        self.stats.total_errors += 1
                        logger.warning(
                            f"Status {response.status} for {candidate_id}. Retrying..."
                        )
            except Exception as e:
                self.stats.total_errors += 1
                if attempt == settings.SCRAPE_RETRY_LIMIT - 1:
                    logger.critical(f"PERMANENT FAILURE for {candidate_id}: {e}")
                    raise
                logger.error(f"Attempt {attempt + 1} failed for {candidate_id}: {e}")

            delay = min(base_delay * (2**attempt) + random.uniform(0, 5), 60.0)
            await asyncio.sleep(delay)

        return None

    def parse_html(self, candidate_id: str, html: str) -> Optional[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", class_="e-table")
            if not table:
                return None

            parsed = {"candidate_id": candidate_id, "province_code": candidate_id[:2]}
            for field in [
                "math",
                "literature",
                "foreign_language",
                "physics",
                "chemistry",
                "biology",
                "history",
                "geography",
                "civic_education",
            ]:
                parsed[field] = None

            found_any = False
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) == 2:
                    subject_name = cols[0].text.strip().lower()
                    score_val = cols[1].text.strip()

                    field = self.subject_mapping.get(subject_name)
                    if field:
                        try:
                            score = float(score_val)
                            if 0 <= score <= 10:
                                parsed[field] = score
                                found_any = True
                        except ValueError:
                            pass

            return parsed if found_any else None
        except Exception as e:
            logger.error(f"HTML parsing error for {candidate_id}: {e}")
            return None

    def _fallback_parse(self, candidate_id: str, html: str) -> Optional[Dict[str, Any]]:
        import re

        parsed = {"candidate_id": candidate_id, "province_code": candidate_id[:2]}
        found_any = False

        for subject_name, field in self.subject_mapping.items():
            pattern = rf"(?i){subject_name}.*?([\d\.]+)"
            match = re.search(pattern, html)
            if match:
                try:
                    score = float(match.group(1))
                    if 0 <= score <= 10:
                        parsed[field] = score
                        found_any = True
                except ValueError:
                    pass

        return parsed if found_any else None

    async def save_to_db(self, scores: List[Dict[str, Any]]):
        if not scores:
            return
        async with AsyncSessionLocal() as session:
            try:
                for score_data in scores:
                    score = ExamScore(**score_data)
                    await session.merge(score)
                await session.commit()
            except Exception as e:
                logger.error(f"Database save error: {e}")
                await session.rollback()

    async def update_redis_distributions(self, scores: List[Dict[str, Any]]):
        if not scores:
            return

        engine = DistributionEngine()
        try:
            pipeline = redis_client.client.pipeline(transaction=False)

            for score_data in scores:
                score_obj = ExamScore(**score_data)
                p_code = score_obj.province_code
                region = self.provinces_cache.get(p_code, "North")

                for block in BLOCKS:
                    total_score = engine.calculate_block_score(score_obj, block)
                    if total_score >= 0:
                        score_str = f"{total_score:.2f}"
                        pipeline.hincrby(f"dist:{block}:nationwide", score_str, 1)
                        pipeline.hincrby(f"dist:{block}:region_{region}", score_str, 1)
                        pipeline.hincrby(f"dist:{block}:prov_{p_code}", score_str, 1)

            await pipeline.execute()
        except Exception as e:
            logger.error(f"Redis distribution update error: {e}")

    async def run(self, province_codes: List[str]):
        checkpoint = CheckpointManager.load()
        start_prov_idx = checkpoint.get("province_idx", 0)

        for idx in range(start_prov_idx, len(province_codes)):
            p_code = province_codes[idx]
            logger.info(f"--- Starting scrape for province {p_code} ---")

            consecutive_misses = 0
            i = checkpoint.get("last_id_offset", 1) if idx == start_prov_idx else 1

            while consecutive_misses < self.max_misses:
                batch_tasks = []
                for offset in range(self.concurrency):
                    candidate_id = f"{p_code}{i + offset:06d}"
                    batch_tasks.append(self.fetch_score(candidate_id))

                try:
                    results = await asyncio.gather(*batch_tasks)
                except Exception as e:
                    logger.error(f"Batch execution error: {e}")
                    await asyncio.sleep(5)
                    continue

                valid_scores = [res for res in results if res is not None]

                # Mandatory sleep to prevent IP blocking
                sleep_time = random.uniform(1.0, 3.0)
                await asyncio.sleep(sleep_time)

                if valid_scores:
                    await self.save_to_db(valid_scores)
                    await self.update_redis_distributions(valid_scores)
                    logger.info(
                        f"[{p_code}] Saved batch of {len(valid_scores)}. "
                        f"Reached ID {i + self.concurrency - 1}"
                    )
                    consecutive_misses = 0
                else:
                    consecutive_misses += len(batch_tasks)

                self.stats.log_stats(p_code)
                i += self.concurrency
                CheckpointManager.save(idx, i)

            logger.info(
                f"Hit {consecutive_misses} consecutive misses. "
                f"Province {p_code} exhausted."
            )
            CheckpointManager.save(idx + 1, 1)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="THPT Exam Score Ingestion Agent")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Start scraping scores")
    scrape_parser.add_argument(
        "--provinces", type=str, help="Comma-separated province codes (e.g., 01,02)"
    )
    scrape_parser.add_argument(
        "--concurrency", type=int, default=settings.SCRAPE_CONCURRENCY
    )
    scrape_parser.add_argument(
        "--max-misses", type=int, default=settings.SCRAPE_MAX_MISSES
    )

    # Refresh command
    subparsers.add_parser("refresh", help="Refresh ranks from Redis distributions")

    # Rebuild command
    subparsers.add_parser("rebuild", help="Rebuild all distributions from Database")

    args = parser.parse_args()

    # Final confirmed URL pattern for 2025
    base_url = "https://diemthi.vnexpress.net/index/detail/sbd/{sbd}/year/2025"

    if args.command == "scrape":
        if args.provinces:
            province_codes = [p.strip() for p in args.provinces.split(",")]
        else:
            # Default all provinces 01-64
            province_codes = [f"{i:02d}" for i in range(1, 65)]

        async with ExamScraper(
            base_url, concurrency=args.concurrency, max_misses=args.max_misses
        ) as scraper:

            async def periodic_refresh():
                engine = DistributionEngine()
                while True:
                    await asyncio.sleep(300)
                    try:
                        await engine.refresh_ranks_from_redis()
                        logger.info("Background rank refresh complete")
                    except Exception as e:
                        logger.error(f"Background rank refresh failed: {e}")

            refresh_task = asyncio.create_task(periodic_refresh())
            try:
                await scraper.run(province_codes)
            finally:
                refresh_task.cancel()
                engine = DistributionEngine()
                await engine.refresh_ranks_from_redis()

    elif args.command == "refresh":
        engine = DistributionEngine()
        await engine.refresh_ranks_from_redis()

    elif args.command == "rebuild":
        engine = DistributionEngine()
        await engine.update_all_distributions()

    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraper stopped by user.")
