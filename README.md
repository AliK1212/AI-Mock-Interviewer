# AI Mock Interviewer

An advanced AI-powered mock interviewer that conducts technical interviews based on job descriptions and provides detailed feedback on responses.

## Features

### 1. Dynamic Question Generation
- Job description-based question generation
- Role-specific technical questions
- Soft skills assessment
- Industry-aware questioning

### 2. Response Analysis
- Technical accuracy evaluation
- Communication clarity assessment
- Detailed feedback generation
- Improvement recommendations

### 3. Performance Features
- Redis caching for frequently requested job descriptions
- Rate limiting (5 requests/minute)
- Job-specific cache keys

## Technical Stack

### Backend
- FastAPI (0.104.1)
- Python 3.9
- OpenAI GPT-4
- Redis for caching
- Docker containerization

## Setup

1. **Environment Setup**
   Create a `.env` file with:
   ```
   OPENAI_API_KEY=your_api_key_here
   REDIS_HOST=redis
   REDIS_PORT=6379
   ```

2. **Installation**
   ```bash
   pip install -r requirements.txt
   ```

3. **Docker Setup**
   ```bash
   docker-compose up --build
   ```

## API Endpoints

### 1. Generate Interview Questions
```http
POST /generate-questions
Content-Type: application/json

{
    "text": "job description text",
    "role": "optional role",
    "company": "optional company"
}
```

### 2. Analyze Response
```http
POST /analyze-response
Content-Type: application/json

{
    "question": "interview question",
    "answer": "candidate's answer"
}
```

## Response Format

### Questions Generation
```json
{
    "questions": [
        "question 1",
        "question 2",
        "..."
    ]
}
```

### Response Analysis
```json
{
    "feedback": "detailed feedback text",
    "scores": {
        "technical_accuracy": 85,
        "communication": 90,
        "overall": 87
    }
}
```

## Architecture

```
mock-interviewer-api/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
└── README.md           # Documentation
```

## Rate Limiting

- 5 requests per minute per IP address
- Cached results valid for 1 hour
- Separate cache keys for different job descriptions
