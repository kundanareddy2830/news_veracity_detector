# filename: main.py (Definitive, Working Version)

import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
import urllib.parse
import re
from typing import List

from pydantic import BaseModel, Field

from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    BrowserConfig,
    LLMExtractionStrategy,
    LLMConfig,
    LXMLWebScrapingStrategy,
    JsonCssExtractionStrategy
)

# --- Load Environment & Configurations ---
load_dotenv()

# --- API Keys ---
TOGETHER_AI_API_KEY = os.getenv("TOGETHER_AI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-3.5-turbo"  # or "gpt-4o" if you have access

# --- Final Model Strategy: Use one, reliable model for all tasks ---
LLM_PROVIDER_STRING = "together_ai/meta-llama/Llama-3-8b-chat-hf"

# --- Constants ---
GOOGLE_FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
CONCURRENCY_LIMIT = 2

# --- Source Tiering ---
SOURCE_TIERS = {
    "reuters.com": 1, "apnews.com": 1, "bbc.com": 1, "wsj.com": 1, "nytimes.com": 2,
    "washingtonpost.com": 2, "theguardian.com": 2, "cnn.com": 3, "foxnews.com": 3,
    "nbcnews.com": 3, "timesofindia.indiatimes.com": 3, "dailymail.co.uk": 4,
    "nypost.com": 4, "huffpost.com": 4, "infowars.com": 5, "breitbart.com": 5,
    "theonion.com": "satire"
}

def get_source_tier(url: str):
    if not url.startswith('http'): return 3
    domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return SOURCE_TIERS.get(domain, 3)

# --- Pydantic Schemas for Structured LLM Output ---
class DeconstructionResult(BaseModel):
    bias_report: str = Field(description="A 2-3 sentence analysis of the article's tone, framing, and potential bias. Conclude with 'Bias rating: [1-5]'.")
    claims: List[str] = Field(description="A list of up to 7 of the most significant, verifiable factual claims from the article.")

# --- ANALYSIS PIPELINE ---

### PHASE 1: INGESTION
async def phase1_ingest_content(crawler: AsyncWebCrawler, input_content: str):
    print("Phase 1: Ingesting and cleaning content...")
    config = CrawlerRunConfig(
        css_selector="[data-testid='ArticleBody'], div._s30J, article, .post-content, .article-body, #main-content, .main, [role='main']",
        scraping_strategy=LXMLWebScrapingStrategy()
    )
    result = await crawler.arun(input_content, config=config)
    if result.success and result.cleaned_html:
        return {"tier": get_source_tier(input_content), "html_content": result.cleaned_html, "error": None}
    return {"error": result.error_message or "Could not extract main article content.", "tier": None, "html_content": None}

### PHASE 2: DECONSTRUCTION
async def phase2_deconstruct_article(crawler: AsyncWebCrawler, html_content: str):
    print(f"Phase 2: Extracting claims and analyzing bias (Model: {LLM_PROVIDER_STRING})...")
    extraction_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=LLM_PROVIDER_STRING, api_token=TOGETHER_AI_API_KEY),
        schema=DeconstructionResult.model_json_schema(),
        instruction="Analyze the article content to identify bias and extract key factual claims according to the provided schema.",
        input_format="html",
        apply_chunking=True,
        chunk_token_threshold=8000
    )
    config = CrawlerRunConfig(extraction_strategy=extraction_strategy)
    result = await crawler.arun(f"raw://{html_content}", config=config)
    if result.success and result.extracted_content:
        try:
            data = json.loads(result.extracted_content)
            if isinstance(data, list) and data:
                consolidated_claims = []
                bias_report = data[0].get('bias_report', "Bias analysis failed.")
                for chunk_result in data: consolidated_claims.extend(chunk_result.get('claims', []))
                return {"bias_report": bias_report, "claims": sorted(list(set(consolidated_claims)))}
            elif isinstance(data, dict):
                return {"bias_report": data.get("bias_report"), "claims": sorted(list(set(data.get("claims", []))))}
        except (json.JSONDecodeError, TypeError):
            return {"error": "Could not decode claims/bias object from LLM."}
    return {"error": f"LLMExtractionStrategy failed. Details: {result.error_message}"}

### PHASE 3: EVIDENCE GATHERING
async def phase3_gather_evidence(crawler: AsyncWebCrawler, claims: list[str]):
    print(f"Phase 3: Gathering evidence for {len(claims)} claims...")
    fact_check_task = batch_query_fact_checks(claims)
    corroboration_task = batch_find_trusted_corroboration(crawler, claims)
    fact_check_data, corroboration_data = await asyncio.gather(fact_check_task, corroboration_task)
    return {"fact_checks": fact_check_data, "corroborations": corroboration_data}

async def batch_query_fact_checks(claims: list[str]):
    print("-> Querying Google Fact Check API...")
    results = {}
    async with httpx.AsyncClient() as client:
        tasks = [client.get(GOOGLE_FACT_CHECK_API_URL, params={"query": claim, "key": GOOGLE_API_KEY, "languageCode": "en"}) for claim in claims]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, response in enumerate(responses):
            claim = claims[i]
            if isinstance(response, httpx.Response) and response.status_code == 200 and "claims" in response.json():
                review = response.json()["claims"][0]["claimReview"][0]
                results[claim] = f"RATING: {review.get('textualRating', 'N/A')} (Publisher: {review.get('publisher', {}).get('name', 'N/A')})"
            else: results[claim] = "No fact-check found."
    return results

async def batch_find_trusted_corroboration(crawler: AsyncWebCrawler, claims: list[str]):
    print("-> Finding corroboration via targeted Google Search...")
    trusted_domains = [domain for domain, tier in SOURCE_TIERS.items() if tier in [1, 2]]
    search_urls = []
    for claim in claims:
        sites_query = ' OR '.join([f'site:{domain}' for domain in trusted_domains])
        search_query = f'"{claim}" {sites_query}'
        search_urls.append(f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}")
    
    schema = {"name": "GoogleResults", "baseSelector": "div.g", "fields": [{"name": "title", "selector": "h3", "type": "text"}, {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"}, {"name": "snippet", "selector": "div[data-sncf='2']", "type": "text"}]}
    config = CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema), page_timeout=20000)
    
    results = await crawler.arun_many(urls=search_urls, config=config)
    
    final_corroborations = {}
    for i, result in enumerate(results):
        claim = claims[i]
        if result.success and result.extracted_content:
            try:
                final_corroborations[claim] = json.loads(result.extracted_content)[:2]
            except (json.JSONDecodeError, TypeError): final_corroborations[claim] = []
        else: final_corroborations[claim] = []
    return final_corroborations

### PHASE 4: SYNTHESIS & SCORING (OpenAI version)
async def call_llm_for_synthesis(api_key: str, prompt: str, is_json_output: bool = False):
    # Commented out Together AI code
    # headers = {"Authorization": f"Bearer {api_key}"}
    # json_payload = {"model": LLM_PROVIDER_STRING, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0, "max_tokens": 4096}
    # if is_json_output: json_payload["response_format"] = {"type": "json_object"}
    # async with httpx.AsyncClient(timeout=180.0) as client:
    #     try:
    #         response = await client.post("https://api.together.xyz/v1/chat/completions", headers=headers, json=json_payload)
    #         response.raise_for_status()
    #         return response.json()["choices"][0]["message"]["content"]
    #     except httpx.HTTPStatusError as e: return json.dumps({"error": f"LLM API Error: {e.response.status_code} - {e.response.text}"})
    #     except Exception as e: return json.dumps({"error": f"An unexpected error occurred: {e}"})

    # OpenAI version
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a meticulous fact-checking analyst."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 2048
    }
    if is_json_output:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e: return json.dumps({"error": f"OpenAI API Error: {e.response.status_code} - {e.response.text}"})
        except Exception as e: return json.dumps({"error": f"An unexpected error occurred: {e}"})

async def phase4_synthesize_and_score(claims: list[str], all_evidence: dict):
    print(f"Phase 4: Synthesizing evidence (Model: {OPENAI_MODEL})...")
    verdict_map = {"Well-Supported": 1.0, "Partially Supported": 0.75, "Lacks Evidence": 0.5, "Disputed": 0.25, "Actively Refuted": 0.0}
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def analyze_single_claim(claim):
        async with semaphore:
            fact_check_result = all_evidence["fact_checks"].get(claim, "N/A")
            corroboration_results = all_evidence["corroborations"].get(claim, [])
            prompt = f"""
You are a meticulous fact-checking analyst. Analyze the claim against the provided evidence and produce a JSON object with your findings.
**Claim to Verify:** "{claim}"
**Evidence Provided:**
1. **Fact-Check Database Result:** "{fact_check_result}"
2. **Corroborating Search Results from Trusted Sources:** {json.dumps(corroboration_results)}
**Your Task:**
Produce a JSON object with the exact following structure:
{{
  "claim": "{claim}",
  "evidence_summary": "A brief, one-sentence summary of what the combined evidence indicates.",
  "rationale": "A 1-2 sentence explanation of your reasoning. Explicitly state how the evidence supports or refutes the claim.",
  "verdict": "Your final verdict. Must be one of: 'Well-Supported', 'Partially Supported', 'Lacks Evidence', 'Disputed', or 'Actively Refuted'."
}}
"""
            response_json_str = await call_llm_for_synthesis(OPENAI_API_KEY, prompt, is_json_output=True)
            try:
                analysis_result = json.loads(response_json_str)
                analysis_result["evidence_snippets"] = corroboration_results
                return analysis_result
            except (json.JSONDecodeError, TypeError): return {"claim": claim, "rationale": "LLM failed to return valid JSON.", "verdict": "Error", "evidence_snippets": corroboration_results}
            finally: await asyncio.sleep(1)

    tasks = [analyze_single_claim(claim) for claim in claims]
    analysis_results = await asyncio.gather(*tasks)
    claim_scores = [verdict_map.get(res.get('verdict'), 0.0) for res in analysis_results]
    return analysis_results, claim_scores

def calculate_final_score(source_tier: int, bias_report: str, claim_scores: list[float]):
    tier_score_map = {1: 100, 2: 90, 3: 75, 4: 40, 5: 10, "satire": 0}
    source_score = tier_score_map.get(source_tier, 60)
    evidence_score = (sum(claim_scores) / len(claim_scores) * 100) if claim_scores else 0
    bias_rating_match = re.search(r'Bias rating:\s*(\d)', bias_report, re.IGNORECASE)
    bias_rating = int(bias_rating_match.group(1)) if bias_rating_match else 3
    bias_score = max(0, 100 - (bias_rating - 1) * 25)
    final_score = (source_score * 0.30) + (evidence_score * 0.50) + (bias_score * 0.20)
    return {"final_score": round(final_score, 2), "components": {"Source": source_score, "Evidence": round(evidence_score, 2), "Bias": bias_score}}

### MAIN WORKFLOW ORCHESTRATOR
async def analyze_article(user_input: str):
    browser_config = BrowserConfig(headless=True, verbose=False)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        if user_input.strip().startswith('http'):
            ingestion_result = await phase1_ingest_content(crawler, user_input)
            if ingestion_result["error"]: print(f"ANALYSIS FAILED in Phase 1: {ingestion_result['error']}"); return
        else:
            print("Phase 1: Bypassed. Using raw text input.")
            ingestion_result = {"tier": 3, "html_content": user_input, "error": None}

        deconstruction_result = await phase2_deconstruct_article(crawler, ingestion_result["html_content"])
        if "error" in deconstruction_result: print(f"ANALYSIS FAILED in Phase 2: {deconstruction_result['error']}"); return
        
        claims = deconstruction_result["claims"]
        if not claims: print("ANALYSIS CONCLUDED: No factual claims were extracted for verification."); return

        all_evidence = await phase3_gather_evidence(crawler, claims)
        final_analysis, claim_scores = await phase4_synthesize_and_score(claims, all_evidence)
        final_score_data = calculate_final_score(ingestion_result["tier"], deconstruction_result["bias_report"], claim_scores)
        
        final_report = {
            "final_credibility_score": final_score_data["final_score"],
            "score_components": final_score_data["components"],
            "publisher_tier": ingestion_result["tier"],
            "bias_report": deconstruction_result["bias_report"],
            "claim_verifications": final_analysis
        }

        print("\n\n--- FINAL ANALYSIS REPORT ---")
        print("="*60)
        print(json.dumps(final_report, indent=2))
        print("\n" + "="*60)
        print("--- Analysis Complete ---")

if __name__ == "__main__":
    if not all([TOGETHER_AI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY]):
        print("FATAL ERROR: Please set TOGETHER_AI_API_KEY, GOOGLE_API_KEY, and OPENAI_API_KEY in your .env file.")
    else:
        # --- Option 1: Analyze a news article from a URL ---
        url_to_analyze = "https://timesofindia.indiatimes.com/technology/top-10-useful-gadgets-for-home-use/articleshow/121653588.cms"
        asyncio.run(analyze_article(user_input=url_to_analyze))

        # --- Option 2: Analyze raw article text ---
        # raw_text_to_analyze = "Your article text here."
        # asyncio.run(analyze_article(user_input=raw_text_to_analyze))