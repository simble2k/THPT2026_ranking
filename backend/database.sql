-- Create provinces table
CREATE TABLE IF NOT EXISTS provinces (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL
);

-- Create exam_scores table
CREATE TABLE IF NOT EXISTS exam_scores (
    candidate_id VARCHAR(20) PRIMARY KEY,
    province_code VARCHAR(10) REFERENCES provinces(code),
    math DECIMAL(4, 2),
    literature DECIMAL(4, 2),
    foreign_language DECIMAL(4, 2),
    physics DECIMAL(4, 2),
    chemistry DECIMAL(4, 2),
    biology DECIMAL(4, 2),
    history DECIMAL(4, 2),
    geography DECIMAL(4, 2),
    civic_education DECIMAL(4, 2)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_exam_scores_province ON exam_scores(province_code);
