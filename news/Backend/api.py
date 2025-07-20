# filename: api.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any
import asyncio
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

# Import the core analysis function from final_main.py
from final_main import analyze_article

# Load environment variables to check for them
load_dotenv()

# --- FastAPI App Initialization ---
app = FastAPI(
    title="News Authenticity Engine API",
    description="An API to analyze news articles for credibility, bias, and factual accuracy.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for the API ---
class ArticleInput(BaseModel):
    input_content: str = Field(..., example="https://www.bbc.com/news/world-us-canada-64949178")

class AnalysisTask(BaseModel):
    request_id: str
    status: str
    message: str

# --- In-memory storage for async results (for production, use Redis or a database) ---
analysis_results: Dict[str, Dict[str, Any]] = {}

# --- Background Task Runner ---
async def run_analysis_in_background(request_id: str, user_input: str):
    """The function that the background task will run."""
    try:
        # Call the main analysis function and get the result
        result_data = await analyze_article(user_input)
        analysis_results[request_id] = {
            "status": "completed",
            "data": result_data
        }
    except Exception as e:
        print(f"Background analysis failed for {request_id}: {e}")
        analysis_results[request_id] = {
            "status": "error",
            "data": {"error_message": str(e)}
        }

# --- API Endpoints ---
@app.post("/analyze", response_model=AnalysisTask)
async def analyze_article_endpoint(item: ArticleInput, background_tasks: BackgroundTasks):
    """
    Accepts an article for analysis and processes it in the background.
    """
    if not all([os.getenv("TOGETHER_AI_API_KEY"), os.getenv("GOOGLE_API_KEY"), os.getenv("OPENAI_API_KEY")]):
        raise HTTPException(status_code=500, detail="Server configuration error: API keys are not set.")

    request_id = str(uuid.uuid4())
    analysis_results[request_id] = {"status": "processing"}
    
    background_tasks.add_task(run_analysis_in_background, request_id, item.input_content)
    
    return AnalysisTask(
        request_id=request_id,
        status="processing",
        message="Analysis has started. Check the /results/{request_id} endpoint for status."
    )

@app.get("/results/{request_id}")
async def get_analysis_result(request_id: str):
    """
    Retrieves the result of a background analysis task.
    """
    result = analysis_results.get(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request ID not found.")
    return result

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "News Authenticity Engine API is running. See /docs for details."}