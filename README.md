# Vietnamese National High School Exam Score Lookup & Ranking Platform

A high-performance, serverless platform designed to handle massive burst traffic during the national exam results announcement.

## Architecture
- **Frontend**: Vanilla JS, HTML, CSS (Deployed to Cloudflare Pages).
- **Backend**: Python FastAPI (Deployed to Vercel Serverless Functions).
- **Database**: PostgreSQL (Supabase).
- **Cache**: Redis (Upstash) for O(1) ranking and percentile lookups.
- **Scraper**: Async Python scraper using `aiohttp` and `SQLAlchemy`.

## Performance Optimization
- **Precomputed Ranks**: The scraper pre-calculates the exact rank and percentile for every possible score and stores them in Redis `HashSets`. This avoids expensive `COUNT` or `RANK()` queries in PostgreSQL during peak traffic.
- **Serverless Ready**: Fully stateless backend optimized for Vercel.
- **Minimal Frontend**: No heavy frameworks, ensuring instant load times and high Lighthouse scores.

## Project Structure
- `/frontend`: Static assets for the user interface.
- `/backend`: FastAPI service for candidate lookups.
- `/scraper`: Data ingestion and distribution engine.
- `/tests`: Unit and integration test suite.

## Setup & Deployment

### Local Development
1. Start PostgreSQL and Redis:
   ```bash
   docker-compose up -d
   ```
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   pip install -r scraper/requirements.txt
   ```
3. Initialize Database:
   - Run `backend/database.sql` and `backend/seed_provinces.sql` in your PostgreSQL instance.

### Environment Variables
Create a `.env` file based on `.env.example`:
- `DATABASE_URL`: Your Supabase/PostgreSQL connection string.
- `REDIS_URL`: Your Upstash/Redis connection string.

### Scraper Usage
To scrape data and update distributions:
```bash
python -m scraper.scraper
python -m scraper.engine
```

### Deployment
- **Frontend**: Connect your GitHub repo to **Cloudflare Pages**, point to the `frontend` directory.
- **Backend**: Connect to **Vercel**, point to the `backend` directory.
- **Database**: Run migrations on **Supabase**.
- **Redis**: Setup a Global database on **Upstash**.

## Features
- [x] High-concurrency async scraper.
- [x] Pre-computed ranking engine.
- [x] O(1) percentile lookup API.
- [x] Mobile-first, framework-less UI.
- [x] GitHub Actions CI pipeline.
