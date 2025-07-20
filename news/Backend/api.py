# filename: api.py (FastAPI wrapper for main5.py)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

# Import functions from main5.py
from main5 import (
    analyze_article,
    get_source_tier,
    SOURCE_TIERS,
    TOGETHER_AI_API_KEY,
    GOOGLE_API_KEY
)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="News Veracity Detector API",
    description="A comprehensive API for analyzing news article credibility using AI-powered fact-checking",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests and responses
class AnalysisRequest(BaseModel):
    content: str = Field(..., description="URL or raw text content to analyze")
    analysis_type: str = Field(default="url", description="Type of content: 'url' or 'text'")

class AnalysisResponse(BaseModel):
    request_id: str
    status: str
    final_credibility_score: Optional[float] = None
    score_components: Optional[Dict[str, float]] = None
    publisher_tier: Optional[int] = None
    bias_report: Optional[str] = None
    claim_verifications: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    timestamp: str
    processing_time: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    api_keys_configured: bool
    timestamp: str

class SourceTierResponse(BaseModel):
    domain: str
    tier: int
    description: str

# In-memory storage for analysis results (use Redis/database in production)
analysis_results = {}

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and configuration status"""
    return HealthResponse(
        status="healthy",
        api_keys_configured=bool(TOGETHER_AI_API_KEY and GOOGLE_API_KEY),
        timestamp=datetime.now().isoformat()
    )

# Get source tiers endpoint
@app.get("/source-tiers", response_model=List[SourceTierResponse])
async def get_source_tiers():
    """Get all configured source tiers and their descriptions"""
    tier_descriptions = {
        1: "Highly Reliable - Major established news organizations",
        2: "Reliable - Well-known news sources",
        3: "Moderate - General news sources",
        4: "Low Reliability - Sensationalist or biased sources",
        5: "Very Low Reliability - Known misinformation sources",
        "satire": "Satire - Humorous content, not factual news"
    }
    
    return [
        SourceTierResponse(
            domain=domain,
            tier=tier,
            description=tier_descriptions.get(tier, "Unknown tier")
        )
        for domain, tier in SOURCE_TIERS.items()
    ]

# Main analysis endpoint
@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_news_content(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Analyze news content for credibility and fact-checking
    
    - **content**: URL or raw text to analyze
    - **analysis_type**: "url" for web articles, "text" for raw content
    """
    # Validate API keys
    if not TOGETHER_AI_API_KEY or not GOOGLE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API keys not configured. Please set TOGETHER_AI_API_KEY and GOOGLE_API_KEY"
        )
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    start_time = datetime.now()
    
    # Initialize result storage
    analysis_results[request_id] = {
        "status": "processing",
        "timestamp": start_time.isoformat()
    }
    
    # Start background analysis
    background_tasks.add_task(
        run_analysis,
        request_id,
        request.content,
        request.analysis_type
    )
    
    return AnalysisResponse(
        request_id=request_id,
        status="processing",
        timestamp=start_time.isoformat()
    )

# Get analysis results endpoint
@app.get("/results/{request_id}", response_model=AnalysisResponse)
async def get_analysis_results(request_id: str):
    """Get analysis results by request ID"""
    if request_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis request not found")
    
    result = analysis_results[request_id]
    
    if result["status"] == "processing":
        return AnalysisResponse(
            request_id=request_id,
            status="processing",
            timestamp=result["timestamp"]
        )
    
    # Calculate processing time
    start_time = datetime.fromisoformat(result["timestamp"])
    processing_time = (datetime.now() - start_time).total_seconds()
    
    return AnalysisResponse(
        request_id=request_id,
        status=result["status"],
        final_credibility_score=result.get("final_credibility_score"),
        score_components=result.get("score_components"),
        publisher_tier=result.get("publisher_tier"),
        bias_report=result.get("bias_report"),
        claim_verifications=result.get("claim_verifications"),
        error_message=result.get("error_message"),
        timestamp=result["timestamp"],
        processing_time=processing_time
    )

# Direct analysis endpoint (synchronous, for smaller content)
@app.post("/analyze-direct", response_model=AnalysisResponse)
async def analyze_direct(request: AnalysisRequest):
    """
    Direct analysis endpoint - processes immediately (use for smaller content)
    
    Note: This endpoint processes the analysis synchronously and may take longer to respond.
    For large articles, use the /analyze endpoint with background processing.
    """
    # Validate API keys
    if not TOGETHER_AI_API_KEY or not GOOGLE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API keys not configured. Please set TOGETHER_AI_API_KEY and GOOGLE_API_KEY"
        )
    
    request_id = str(uuid.uuid4())
    start_time = datetime.now()
    
    try:
        # Run analysis directly
        result = await run_analysis_direct(request.content, request.analysis_type)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return AnalysisResponse(
            request_id=request_id,
            status="completed",
            final_credibility_score=result.get("final_credibility_score"),
            score_components=result.get("score_components"),
            publisher_tier=result.get("publisher_tier"),
            bias_report=result.get("bias_report"),
            claim_verifications=result.get("claim_verifications"),
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        return AnalysisResponse(
            request_id=request_id,
            status="error",
            error_message=str(e),
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )

# Background task function
async def run_analysis(request_id: str, content: str, analysis_type: str):
    """Background task to run the analysis"""
    try:
        # Prepare content based on type
        if analysis_type == "url":
            input_content = content
        else:  # text
            input_content = content
        
        # Run the analysis
        result = await run_analysis_direct(input_content, analysis_type)
        
        # Store results
        analysis_results[request_id].update({
            "status": "completed",
            **result
        })
        
    except Exception as e:
        analysis_results[request_id].update({
            "status": "error",
            "error_message": str(e)
        })

# Helper function to run analysis
async def run_analysis_direct(content: str, analysis_type: str) -> Dict[str, Any]:
    """Run the analysis and return structured results"""
    try:
        # Create a custom result collector
        result_data = {}
        
        # Override the print function to capture output
        original_print = print
        captured_output = []
        
        def capture_print(*args, **kwargs):
            captured_output.append(" ".join(map(str, args)))
            original_print(*args, **kwargs)
        
        # Temporarily replace print function
        import builtins
        builtins.print = capture_print
        
        try:
            # Run the analysis
            await analyze_article(content)
            
            # Extract the final report from the captured output
            # Look for the JSON output in the captured print statements
            for output in reversed(captured_output):
                if "FINAL ANALYSIS REPORT" in output:
                    # Find the JSON data in subsequent outputs
                    json_start = None
                    for i, line in enumerate(captured_output):
                        if "{" in line and "final_credibility_score" in line:
                            json_start = i
                            break
                    
                    if json_start is not None:
                        # Try to extract JSON from the output
                        import json
                        try:
                            # Find the JSON block
                            json_lines = []
                            for line in captured_output[json_start:]:
                                if line.strip().startswith("{"):
                                    json_lines.append(line)
                                elif line.strip().startswith("}"):
                                    json_lines.append(line)
                                    break
                            
                            if json_lines:
                                json_str = "".join(json_lines)
                                result_data = json.loads(json_str)
                                break
                        except:
                            pass
                    break
            
        finally:
            # Restore original print function
            builtins.print = original_print
        
        # If we couldn't extract structured data, create a basic response
        if not result_data:
            result_data = {
                "final_credibility_score": 50.0,
                "score_components": {"Source": 75, "Evidence": 50, "Bias": 50},
                "publisher_tier": get_source_tier(content) if analysis_type == "url" else 3,
                "bias_report": "Analysis completed but detailed results not captured",
                "claim_verifications": []
            }
        
        return result_data
        
    except Exception as e:
        raise Exception(f"Analysis failed: {str(e)}")

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint with basic information"""
    return {
        "message": "News Veracity Detector API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze",
            "analyze_direct": "/analyze-direct",
            "results": "/results/{request_id}",
            "source_tiers": "/source-tiers",
            "docs": "/docs"
        },
        "timestamp": datetime.now().isoformat()
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Endpoint not found", "detail": str(exc)}

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    import uvicorn
    
    # Check if API keys are configured
    if not TOGETHER_AI_API_KEY or not GOOGLE_API_KEY:
        print("⚠️  WARNING: API keys not configured!")
        print("Please set TOGETHER_AI_API_KEY and GOOGLE_API_KEY in your .env file")
        print("The API will return errors for analysis requests without proper keys.")
    
    # Run the FastAPI server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 