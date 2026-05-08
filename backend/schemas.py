from typing import List, Optional

from pydantic import BaseModel


class ScoreResponse(BaseModel):
    math: Optional[float]
    literature: Optional[float]
    foreign_language: Optional[float]
    physics: Optional[float]
    chemistry: Optional[float]
    biology: Optional[float]
    history: Optional[float]
    geography: Optional[float]
    civic_education: Optional[float]


class RankInfo(BaseModel):
    score: float
    rank: int
    total_candidates: int
    percentile: float


class BlockInfo(BaseModel):
    block: str
    score: float
    nationwide: RankInfo
    regional: RankInfo
    provincial: RankInfo


class CandidateResponse(BaseModel):
    candidate_id: str
    province_name: str
    region_name: str
    scores: ScoreResponse
    blocks: List[BlockInfo]
