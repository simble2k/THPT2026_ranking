from scraper.engine import DistributionEngine
from scraper.models import ExamScore


def test_calculate_block_score():
    engine = DistributionEngine()

    # Mock ExamScore
    score = ExamScore(math=8.0, physics=9.0, chemistry=10.0, literature=7.0)

    # A00: Math + Physics + Chemistry = 8 + 9 + 10 = 27
    assert engine.calculate_block_score(score, "A00") == 27.0

    # D01: Math + Literature + Foreign Language (None) = -1
    assert engine.calculate_block_score(score, "D01") == -1.0


def test_rank_calculation_logic():
    # This is more of a conceptual test as the actual logic is in
    # update_all_distributions
    # but we can verify the sorting and rank assignment logic if we extract it.
    pass
