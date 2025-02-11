from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import openai
import os
import logging
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis
import traceback
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")

# Test OpenAI API connection
try:
    logger.info("Testing OpenAI API connection...")
    test_response = openai.ChatCompletion.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    logger.info("OpenAI API connection successful")
except Exception as e:
    logger.error(f"Failed to connect to OpenAI API: {str(e)}")
    logger.error(traceback.format_exc())
    raise

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
origins = [
    "https://frontend-portfolio-aomn.onrender.com",
    "https://deerk-portfolio.onrender.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.options("/{path:path}")
async def options_route(request: Request):
    return JSONResponse(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize Redis
redis_client = redis.Redis(
    host=os.getenv("RENDER_REDIS_HOST", "localhost"),
    port=int(os.getenv("RENDER_REDIS_PORT", 6379)),
    password=os.getenv("RENDER_REDIS_PASSWORD", ""),
    decode_responses=True
)

class JobDescription(BaseModel):
    title: str
    description: str

class InterviewRequest(BaseModel):
    job_desc: JobDescription

class InterviewResponse(BaseModel):
    answers: List[Dict[str, str]]  # List of {"question": "...", "answer": "..."}

class InterviewQuestion(BaseModel):
    question: str
    answer: str

SYSTEM_PROMPT = """You are an experienced technical interviewer conducting interviews for various tech positions. 
Your goal is to assess candidates' technical knowledge, problem-solving abilities, and communication skills.
Ask relevant technical questions based on the job title and description provided. Focus on both technical depth and soft skills.
Provide constructive feedback that helps candidates improve."""

@app.get("/")
async def root():
    return {"message": "Mock Interviewer API is running"}

@app.post("/generate-questions")
@limiter.limit("5/minute")
async def generate_questions(request: Request, interview_request: InterviewRequest):
    """Generate relevant interview questions based on the job title and description."""
    try:
        job_desc = interview_request.job_desc
        logger.info(f"Generating questions for job title: {job_desc.title}")
        
        # Check cache first
        cache_key = f"questions:{hash(job_desc.title + job_desc.description)}"
        cached_questions = redis_client.get(cache_key)
        if cached_questions:
            logger.info("Returning cached questions")
            return {"questions": eval(cached_questions)}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""Generate exactly 5 relevant interview questions for:
            Job Title: {job_desc.title}
            Job Description: {job_desc.description}
            
            Focus on both technical skills and soft skills. Make the questions specific to the role.
            
            Format each question on a new line, numbered from 1-5."""}
        ]

        logger.info("Making OpenAI API call")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini-2024-07-18",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        # Only include lines that start with a number followed by a period
        questions = [q.strip() for q in response.choices[0].message.content.split("\n") 
                    if q.strip() and q.strip()[0].isdigit() and ". " in q.strip()[:10]]
        
        # Ensure we have exactly 5 questions
        if len(questions) != 5:
            logger.error(f"Generated {len(questions)} questions instead of 5")
            raise HTTPException(status_code=500, detail="Failed to generate the correct number of questions")
            
        logger.info(f"Generated {len(questions)} questions")
        
        # Cache the results
        redis_client.setex(cache_key, 3600, str(questions))  # Cache for 1 hour

        return {"questions": questions}

    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-responses")
@limiter.limit("5/minute")
async def analyze_responses(request: Request, responses: InterviewResponse):
    """Analyze all responses and provide comprehensive feedback."""
    try:
        logger.info("Analyzing interview responses")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""Analyze these interview responses:

{chr(10).join([f'Q: {resp["question"]}{chr(10)}A: {resp["answer"]}{chr(10)}' for resp in responses.answers])}

Provide comprehensive feedback including:
1. Technical Depth (Score out of 10)
2. Communication Clarity (Score out of 10)
3. Overall Performance (Score out of 10)
4. Strengths
5. Areas for Improvement
6. Specific Recommendations

Format the response as JSON with these keys:
technical_score, communication_score, overall_score, strengths, improvements, recommendations"""}
        ]

        logger.info("Making OpenAI API call for analysis")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini-2024-07-18",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        feedback = response.choices[0].message.content
        logger.info("Successfully generated feedback")

        try:
            # Clean up markdown formatting if present
            if feedback.startswith("```"):
                feedback = feedback.split("\n", 1)[1]  # Remove first line with ```json
                feedback = feedback.rsplit("\n", 1)[0]  # Remove last line with ```
            
            # Parse the JSON
            feedback_json = json.loads(feedback)
            
            # Convert arrays to strings if they're not already arrays
            for key in ['strengths', 'improvements', 'recommendations']:
                if isinstance(feedback_json[key], str):
                    feedback_json[key] = [feedback_json[key]]
            
            return {"feedback": json.dumps(feedback_json)}
        except Exception as e:
            logger.error(f"Error parsing feedback: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Error analyzing responses: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
