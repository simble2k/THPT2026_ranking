from core.database import Base
from sqlalchemy import Column, ForeignKey, Numeric, String


class Province(Base):
    __tablename__ = "provinces"

    code = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False)


class ExamScore(Base):
    __tablename__ = "exam_scores"

    candidate_id = Column(String(20), primary_key=True)
    province_code = Column(String(10), ForeignKey("provinces.code"))
    math = Column(Numeric(4, 2))
    literature = Column(Numeric(4, 2))
    foreign_language = Column(Numeric(4, 2))
    physics = Column(Numeric(4, 2))
    chemistry = Column(Numeric(4, 2))
    biology = Column(Numeric(4, 2))
    history = Column(Numeric(4, 2))
    geography = Column(Numeric(4, 2))
    civic_education = Column(Numeric(4, 2))
