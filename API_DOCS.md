# AscendAI API Documentation

The FastAPI application exposes lead generation and assessment endpoints.

## Quick Start

### 1. Install dependencies
```bash
uv sync
```

### 2. Set environment variables
```bash
export DATABASE_URL="postgresql://user:pass@localhost/dbname"  # or sqlite:///leads.db
export SERPER_API_KEY="your_serper_api_key"
export AWS_DEFAULT_REGION="us-east-1"
# AWS credentials (via boto3): AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or IAM role
```

### 3. Run the API server
```bash
uv run uvicorn src.ascendai.api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: **http://localhost:8000**

## API Endpoints

### Health Check
- **GET** `/health` — Check API status

### Lead Generation
- **POST** `/leads/generate` — Generate new leads using AI search
  - Request body: `{ "search_queries": ["..."], "limit": 10 }`
  - Returns: List of generated leads

### Lead Assessment
- **POST** `/leads/assess` — Assess leads using web research and LLM
  - Request body: `{ "lead_ids": [1, 2, 3], "limit": 5 }`
  - Returns: Assessment results with scores and factors

### Lead Retrieval
- **GET** `/leads` — List all leads with filtering
  - Query params: `status`, `limit`, `offset`
  - Returns: Paginated leads

- **GET** `/leads/{lead_id}` — Get a single lead with details
  - Returns: Lead details with assessment

### Statistics
- **GET** `/stats` — Get database statistics
  - Returns: Total leads, assessed count, average scores

## Interactive Documentation

Visit **http://localhost:8000/docs** for Swagger UI with interactive testing.

## Example Usage

### Generate leads
```bash
curl -X POST http://localhost:8000/leads/generate \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

### Assess leads
```bash
curl -X POST http://localhost:8000/leads/assess \
  -H "Content-Type: application/json" \
  -d '{"limit": 3}'
```

### List leads
```bash
curl http://localhost:8000/leads?status=assessed&limit=10
```

### Get stats
```bash
curl http://localhost:8000/stats
```

## Assessment Factors

Each lead is assessed on:
- **tech_stack**: Shopify, WooCommerce, WordPress, Custom, Unknown
- **business_age_months**: Integer estimate
- **merchant_category**: Subscription, Services, E-commerce, SaaS, Other
- **company_scale**: SMB, Medium, Enterprise
- **integration_readiness_score**: 0-1 (how ready for payment integration)
- **transaction_intent_score**: 0-1 (likelihood to process transactions)
- **digital_maturity_score**: 0-1 (tech sophistication)
- **web_presence_quality**: 0-1 (website and online visibility)
- **fraud_risk_pattern_score**: 0-1 (fraud risk level)
- **traffic_check**: 0-1 (website traffic estimate)
- **brand_search_volume**: 0-1 (brand search visibility)
- **lead_score**: 0-100 (overall PayU fit)

## Architecture

- **`lead_generation.py`** — Searches web using Serper API, identifies potential PayU customers
- **`lead_assessor.py`** — Performs factor-by-factor web research and LLM-based assessment
- **`api.py`** — FastAPI application exposing both modules
- **`llm.py`** — Bedrock LLM integration for AI analysis
- **`models/lead.py`** — SQLAlchemy Lead model

## Notes

- Assessments use Serper API for web search and AWS Bedrock for LLM analysis
- Search queries are optimized for SEO/relevance
- Missing assessment data is filled using LLM estimation
- All leads and assessments are persisted to the configured database
