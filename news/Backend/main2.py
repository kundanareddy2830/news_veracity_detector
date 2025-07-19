# filename: main.py

import asyncio
import os
import json
import httpx
from dotenv import load_dotenv

from source_tiering import get_source_tier
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# --- NEW: Load environment variables from .env file ---
load_dotenv()

# --- NEW: LLM Configuration ---
# As recommended by the strategy, we'll use a powerful instruction-tuned model.
TOGETHER_AI_MODEL = "meta-llama/Llama-3-70b-chat-hf"
TOGETHER_AI_API_URL = "https://api.together.xyz/v1/chat/completions"


async def process_input(input_content: str):
    """
    This single function processes content from either a URL or raw HTML string
    [cite_start]by leveraging Crawl4AI's prefix handling. [cite: 749, 755]
    """
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.5) # Using PruningContentFilter for a clean core text. [cite: 538, 539, 608, 838, 1080]
    )
    config = CrawlerRunConfig(markdown_generator=md_generator)
    source_url = input_content if input_content.startswith('http') else 'raw_text_input'
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(input_content, config=config)

    if result.success and result.markdown:
        tier = get_source_tier(source_url)
        # [cite_start]'fit_markdown' provides the cleaned text, which is ideal for LLM analysis. [cite: 556, 560, 837, 1098]
        core_text = result.markdown.fit_markdown 
        return {"tier": tier, "text": core_text, "error": None}
    else:
        return {"error": result.error_message, "tier": None, "text": None}

# --- NEW: Function to call the LLM Provider ---
async def call_llm(api_key: str, prompt: str, is_json_output: bool = False):
    """
    A reusable function to make API calls to the Together AI endpoint.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    json_payload = {
        "model": TOGETHER_AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "top_p": 0.7,
        "max_tokens": 2048
    }
    
    if is_json_output:
        json_payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=json_payload)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            return f"LLM API Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"An unexpected error occurred during LLM call: {str(e)}"

# --- NEW: Function for Claim and Bias Extraction ---
async def extract_claims_and_bias(article_text: str):
    """
    Orchestrates the two required LLM calls for claim extraction and bias analysis.
    """
    api_key = os.getenv("TOGETHER_AI_API_KEY")
    if not api_key:
        return {
            "claims": "ERROR: TOGETHER_AI_API_KEY not found in .env file.",
            "bias_report": "ERROR: API key not found."
        }
        
    # 1. Instruction-Based Claim Extraction
    claim_prompt = f"""Analyze the following news article. Identify and list every distinct factual claim that can be independently verified. Ignore opinions, predictions, and subjective statements. Present the output as a JSON object with a single key "claims" which holds an array of strings.

    Article:
    {article_text}
    """
    
    # 2. Bias and Framing Analysis
    bias_prompt = f"""Analyze the tone, sentiment, and rhetorical devices in this article. Is the framing neutral, or does it use loaded language, logical fallacies, or emotional appeals to persuade the reader? Identify specific examples. Conclude with a bias rating from 1 (Neutral) to 5 (Highly Biased).

    Article:
    {article_text}
    """

    # Run both API calls concurrently
    claims_task = call_llm(api_key, claim_prompt, is_json_output=True)
    bias_task = call_llm(api_key, bias_prompt)
    
    results = await asyncio.gather(claims_task, bias_task)
    
    # Parse results with error handling
    try:
        claims_data = json.loads(results[0])
    except (json.JSONDecodeError, TypeError):
        claims_data = {"claims": ["LLM did not return valid JSON for claims.", f"Raw response: {results[0]}"]}
        
    bias_data = results[1]

    return {
        "claims": claims_data.get("claims", []),
        "bias_report": bias_data
    }


async def analyze_article(user_input: str):
    """
    Handles both URL and raw text input, calls the unified processing
    pipeline, and prints the result.
    """
    print("--- Starting Analysis (Phase 1 & 2) ---")
    
    input_to_crawl = ""
    is_url = user_input.strip().startswith('http')

    if is_url:
        print("Input Type: URL")
        input_to_crawl = user_input.strip()
    else:
        print("Input Type: Raw HTML Text")
        input_to_crawl = f"raw://{user_input}"

    # --- Phase 1: Ingestion ---
    phase1_output = await process_input(input_to_crawl)
    
    if phase1_output["error"]:
        print(f"\n--- Analysis Report ---\nAn error occurred during ingestion: {phase1_output['error']}")
        return

    # --- NEW: Phase 2: Deconstruction ---
    print("\nExtracting claims and analyzing bias using LLM...")
    phase2_output = await extract_claims_and_bias(phase1_output["text"])
    
    # --- Final Report ---
    print("\n--- Analysis Report ---")
    print(f"Publisher Credibility Tier: {phase1_output['tier']}")
    
    print("\n--- Bias & Framing Report ---")
    print(phase2_output["bias_report"])
    
    print("\n--- Extracted Factual Claims ---")
    if phase2_output["claims"]:
        for i, claim in enumerate(phase2_output["claims"], 1):
            print(f"{i}. {claim}")
    else:
        print("No factual claims were extracted.")

    print("\n--- Analysis Complete ---")


if __name__ == "__main__":
    # --- CHOOSE ONE EXAMPLE TO RUN ---

    # Example 1: Analyze an article from a URL
    url_to_check = "https://www.npr.org/2024/08/28/g-s1-19832/workers-killed-injured-delta-air-lines-atlanta"
    asyncio.run(analyze_article(url_to_check))

    # Example 2: Analyze an article from a raw HTML string
    # raw_html_content = """
    # <html><body><main>
    # <h1>New Study Confirms Widgets Increase Efficiency by 300%</h1>
    # <p>In a landmark study published today by the Institute of Fictional Science, researchers found that using advanced "Quantum Widgets" in the workplace led to a threefold increase in overall employee efficiency. Dr. Evelyn Reed, the lead author, stated, "The data is undeniable; these widgets have revolutionized productivity." The study involved 10,000 participants over a two-year period, making it the largest of its kind.</p>
    # </main></body></html>
    # """
    # asyncio.run(analyze_article(raw_html_content))