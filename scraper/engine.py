import asyncio
import logging
from typing import Dict

from sqlalchemy import select

from .database import AsyncSessionLocal
from .models import ExamScore, Province
from .redis_client import redis_client

logger = logging.getLogger("engine")

BLOCKS = {
    "A00": ["math", "physics", "chemistry"],
    "A01": ["math", "physics", "foreign_language"],
    "B00": ["math", "chemistry", "biology"],
    "C00": ["literature", "history", "geography"],
    "D01": ["math", "literature", "foreign_language"],
}

class DistributionEngine:
    @staticmethod
    def calculate_block_score(score: ExamScore, block: str) -> float:
        subjects = BLOCKS.get(block, [])
        total = 0.0
        for sub in subjects:
            val = getattr(score, sub)
            if val is None:
                return -1.0 # Incomplete block
            total += float(val)
        return round(total, 2)

    async def update_all_distributions(self, batch_size: int = 10000):
        """
        Memory-safe recalculation: Processes records in chunks to avoid OOM.
        """
        async with AsyncSessionLocal() as session:
            # Structure: data[block][scope][score] = count
            distributions = {
                block: {"nationwide": {}, "regions": {}, "provinces": {}}
                for block in BLOCKS
            }

            offset = 0
            while True:
                # 1. Fetch scores and provinces in batches
                stmt = select(ExamScore, Province).join(
                    Province, ExamScore.province_code == Province.code
                ).offset(offset).limit(batch_size)
                
                result = await session.execute(stmt)
                batch = result.all()
                
                if not batch:
                    break
                
                logger.info(f"Processing batch from offset {offset}...")

                for score_obj, province_obj in batch:
                    for block in BLOCKS:
                        total_score = self.calculate_block_score(score_obj, block)
                        if total_score < 0:
                            continue
                        
                        score_str = f"{total_score:.2f}"
                        
                        # Nationwide
                        dist_nat = distributions[block]["nationwide"]
                        dist_nat[score_str] = dist_nat.get(score_str, 0) + 1
                        
                        # Regional
                        reg_name = province_obj.region
                        if reg_name not in distributions[block]["regions"]:
                            distributions[block]["regions"][reg_name] = {}
                        dist_reg = distributions[block]["regions"][reg_name]
                        dist_reg[score_str] = dist_reg.get(score_str, 0) + 1
                        
                        # Provincial
                        p_code = province_obj.code
                        if p_code not in distributions[block]["provinces"]:
                            distributions[block]["provinces"][p_code] = {}
                        dist_prov = distributions[block]["provinces"][p_code]
                        dist_prov[score_str] = dist_prov.get(score_str, 0) + 1
                
                offset += batch_size

            # 2. Calculate and Save to Redis
            for block, scopes in distributions.items():
                logger.info(f"Saving distributions for block {block}...")
                # Nationwide
                await self._save_distribution(block, "nationwide", scopes["nationwide"])
                
                # Regional
                for region, counts in scopes["regions"].items():
                    await self._save_distribution(block, f"region_{region}", counts)
                
                # Provincial
                for p_code, counts in scopes["provinces"].items():
                    await self._save_distribution(block, f"prov_{p_code}", counts)

    async def _save_distribution(self, block: str, scope: str, counts: Dict[str, int]):
        if not counts:
            return

        # dist:{block}:{scope} -> {score: count}
        dist_key = f"dist:{block}:{scope}"
        await redis_client.client.hmset(dist_key, counts)

        # Precompute Ranks and Percentiles
        # Sort scores descending
        sorted_scores = sorted(counts.keys(), key=float, reverse=True)
        
        total_students = sum(counts.values())
        current_rank = 1
        
        rank_data = {}
        pct_data = {}
        
        for s_str in sorted_scores:
            cnt = counts[s_str]
            rank_data[s_str] = current_rank
            
            # Percentile = (Number of people with score < current_score) / Total * 100
            # or simpler: 100 - (rank / total * 100)
            percentile = 100.0 - (current_rank / total_students * 100.0)
            pct_data[s_str] = f"{percentile:.2f}"
            
            current_rank += cnt
            
        rank_key = f"rank:{block}:{scope}"
        pct_key = f"pct:{block}:{scope}"
        total_key = f"total:{block}:{scope}"
        
        await redis_client.client.hmset(rank_key, rank_data)
        await redis_client.client.hmset(pct_key, pct_data)
        await redis_client.client.set(total_key, total_students)
        
        logger.info(f"Updated Redis for {block}:{scope}")

async def main():
    engine = DistributionEngine()
    await engine.update_all_distributions()

if __name__ == "__main__":
    asyncio.run(main())
