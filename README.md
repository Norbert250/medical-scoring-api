# Medical Condition Scoring API

A standalone FastAPI service for calculating medical condition scores based on patient age and medical conditions.

## Features

- Calculate medical scores using RAF (Risk Adjustment Factor) methodology
- Age-based scoring (5-20 points)
- Condition-based scoring (0-80 points) using highest RAF score
- Total score range: 5-100 points

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure CSV data file exists:
```
data/2025 Midyear_Final ICD-10-CM Mappings.csv
```

## Running the API

```bash
python main.py
```

The API will be available at:
- **Base URL**: http://localhost:8001
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## API Endpoints

### POST /score
Calculate medical condition score.

**Request Body:**
```json
{
  "age": 45,
  "conditions": ["diabetes", "cancer", "arthritis"]
}
```

**Response:**
```json
{
  "score": 95.0
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "conditions_loaded": 15420
}
```

## Usage Examples

### Using curl:
```bash
curl -X POST "http://localhost:8001/score" \
-H "Content-Type: application/json" \
-d '{"age": 45, "conditions": ["diabetes", "cancer"]}'
```

### Using Python requests:
```python
import requests

response = requests.post(
    "http://localhost:8001/score",
    json={"age": 45, "conditions": ["diabetes", "cancer"]}
)
print(response.json())  # {"score": 95.0}
```

## Scoring Logic

- **Age Score**: 5-20 points based on age ranges
- **Condition Score**: 0-80 points (highest RAF score × 100, capped at 80)
- **Total Score**: Age + Condition = 5-100 points

The API finds the medical condition with the highest RAF score and uses only that condition for scoring.