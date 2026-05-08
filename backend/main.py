import asyncio

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.database import get_db
from .core.redis_client import RedisClient, get_redis
from .models import ExamScore, Province
from .schemas import BlockInfo, CandidateResponse, RankInfo, ScoreResponse

app = FastAPI(title="THPT Score Lookup API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BLOCKS = {
    "A00": ["math", "physics", "chemistry"],
    "A01": ["math", "physics", "foreign_language"],
    "B00": ["math", "chemistry", "biology"],
    "C00": ["literature", "history", "geography"],
    "D01": ["math", "literature", "foreign_language"],
}


async def fetch_scope_rank(
    redis: RedisClient, block: str, scope: str, score: float
) -> RankInfo:
    score_str = f"{score:.2f}"
    # Gather all 3 lookups concurrently to minimize round-trip latency
    rank, percentile, total = await asyncio.gather(
        redis.hget(f"rank:{block}:{scope}", score_str),
        redis.hget(f"pct:{block}:{scope}", score_str),
        redis.get(f"total:{block}:{scope}"),
    )

    return RankInfo(
        score=score,
        rank=int(rank) if rank else 0,
        total_candidates=int(total) if total else 0,
        percentile=float(percentile) if percentile else 0.0,
    )


@app.get("/api/candidate/{candidate_id}", response_model=CandidateResponse)
async def get_candidate_scores(
    candidate_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    # Set Cache-Control for edge delivery (1 day)
    response.headers["Cache-Control"] = (
        "public, s-maxage=86400, stale-while-revalidate=3600"
    )

    # 1. Fetch scores and province
    stmt = (
        select(ExamScore, Province)
        .join(Province, ExamScore.province_code == Province.code)
        .where(ExamScore.candidate_id == candidate_id)
    )
    result = await db.execute(stmt)
    data = result.first()

    if not data:
        raise HTTPException(status_code=404, detail="Candidate not found")

    score_obj, province_obj = data

    # 2. Prepare scores
    scores_dict = {
        field: getattr(score_obj, field) for field in ScoreResponse.__fields__
    }

    # 3. Compute blocks
    blocks_info = []
    # Collect all rank lookup tasks across all blocks and scopes
    all_rank_tasks = []
    active_blocks = []

    for block, subjects in BLOCKS.items():
        total_score = 0.0
        valid = True
        for sub in subjects:
            val = getattr(score_obj, sub)
            if val is None:
                valid = False
                break
            total_score += float(val)

        if valid:
            total_score = round(total_score, 2)
            active_blocks.append((block, total_score))

            # Queue 3 scopes for this block
            all_rank_tasks.append(
                fetch_scope_rank(redis, block, "nationwide", total_score)
            )
            all_rank_tasks.append(
                fetch_scope_rank(
                    redis, block, f"region_{province_obj.region}", total_score
                )
            )
            all_rank_tasks.append(
                fetch_scope_rank(redis, block, f"prov_{province_obj.code}", total_score)
            )

    # Resolve all Redis calls in a single batch of concurrent tasks
    all_ranks = await asyncio.gather(*all_rank_tasks)

    # Reconstruct blocks_info
    for i, (block, total_score) in enumerate(active_blocks):
        blocks_info.append(
            BlockInfo(
                block=block,
                score=total_score,
                nationwide=all_ranks[i * 3],
                regional=all_ranks[i * 3 + 1],
                provincial=all_ranks[i * 3 + 2],
            )
        )

    return CandidateResponse(
        candidate_id=candidate_id,
        province_name=province_obj.name,
        region_name=province_obj.region,
        scores=ScoreResponse(**scores_dict),
        blocks=blocks_info,
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
