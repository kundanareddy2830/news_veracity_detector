# filename: main.py

import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
import urllib.parse

# We now import SOURCE_TIERS to use for building our trusted search query
from source_tiering import get_source_tier, SOURCE_TIERS
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    JsonCssExtractionStrategy # This will be used to parse Google Search results
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Load credentials from .env file
load_dotenv()

# --- Configurations ---
TOGETHER_AI_MODEL = "meta-llama/Llama-3-70b-chat-hf"
TOGETHER_AI_API_URL = "https://api.together.xyz/v1/chat/completions"
GOOGLE_FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


# --- Phase 1 & 2 Functions (Unchanged) ---
async def process_input(input_content: str):
    md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.5))
    config = CrawlerRunConfig(markdown_generator=md_generator)
    source_url = input_content if input_content.startswith('http') else 'raw_text_input'
    async with AsyncWebCrawler(verbose=False) as crawler: # Verbose off for cleaner output
        result = await crawler.arun(input_content, config=config)
    if result.success and result.markdown:
        tier = get_source_tier(source_url)
        core_text = result.markdown.fit_markdown 
        return {"tier": tier, "text": core_text, "error": None}
    return {"error": result.error_message, "tier": None, "text": None}

async def call_llm(api_key: str, prompt: str, is_json_output: bool = False):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    json_payload = {"model": TOGETHER_AI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0, "max_tokens": 2048}
    if is_json_output: json_payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=json_payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e: return f"LLM API Error: {e}"

async def extract_claims_and_bias(article_text: str):
    api_key = os.getenv("TOGETHER_AI_API_KEY")
    if not api_key: return {"claims": ["ERROR: API key not found."], "bias_report": "ERROR: API key not found."}
    claim_prompt = f"""Analyze the following news article. Identify and list every distinct factual claim... JSON object with a single key "claims"... Article:\n{article_text}"""
    bias_prompt = f"""Analyze the tone, sentiment, and rhetorical devices... bias rating from 1 (Neutral) to 5 (Highly Biased)... Article:\n{article_text}"""
    tasks = [call_llm(api_key, claim_prompt, is_json_output=True), call_llm(api_key, bias_prompt)]
    results = await asyncio.gather(*tasks)
    try: claims_data = json.loads(results[0])
    except (json.JSONDecodeError, TypeError): claims_data = {"claims": ["LLM did not return valid JSON."]}
    return {"claims": claims_data.get("claims", []), "bias_report": results[1]}


# --- NEW: Phase 3 Functions ---

async def query_fact_check_api(claims: list[str]):
    """
    Vector 1: Queries the Google Fact Check Tools API for each claim.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key: return {claim: "ERROR: GOOGLE_API_KEY not found." for claim in claims}
    results = {}
    async with httpx.AsyncClient() as client:
        for claim in claims:
            params = {"query": claim, "key": api_key, "languageCode": "en"}
            try:
                response = await client.get(GOOGLE_FACT_CHECK_API_URL, params=params)
                data = response.json()
                if data and "claims" in data:
                    review = data["claims"][0]["claimReview"][0]
                    rating = review.get("textualRating", "N/A")
                    publisher = review.get("publisher", {}).get("name", "N/A")
                    results[claim] = f"RATING: {rating} (Publisher: {publisher})"
                else:
                    results[claim] = "No fact-check found."
            except Exception:
                results[claim] = "API query failed."
    return results

async def find_trusted_corroboration(claim: str):
    """
    Vector 2: Uses Crawl4AI to search Google for a claim, restricted to Tier 1 & 2 news sites.
    This method cleverly avoids needing a separate Search API key.
    """
    # Build a search query restricted to trusted domains from our tiering file
    trusted_domains = [domain for domain, tier in SOURCE_TIERS.items() if tier in [1, 2]]
    quoted_claim = f'"{claim}" '
    sites = ' OR '.join([f'site:{domain}' for domain in trusted_domains])
    search_query = quoted_claim + sites
    search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}"

    # Define a schema to extract search results directly from the Google page
    schema = {"name": "GoogleResults", "baseSelector": "div.g", "fields": [
            {"name": "title", "selector": "h3", "type": "text"},
            {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"} ]}
    config = CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema))

    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(search_url, config=config)
    
    if result.success and result.extracted_content:
        try: return json.loads(result.extracted_content)
        except json.JSONDecodeError: return []
    return []


# --- Main Workflow (Updated for Phase 3) ---
async def analyze_article(user_input: str):
    """
    The main function that orchestrates all three phases of analysis.
    """
    print("--- Starting Full Analysis (Phase 1, 2, & 3) ---")
    input_to_crawl = f"raw://{user_input}" if not user_input.strip().startswith('http') else user_input.strip()

    # Phase 1
    phase1_output = await process_input(input_to_crawl)
    if phase1_output["error"]:
        print(f"\n--- Report ---\nError in Phase 1: {phase1_output['error']}")
        return

    # Phase 2
    print("Phase 1 Complete. Deconstructing content with LLM...")
    phase2_output = await extract_claims_and_bias(phase1_output["text"])
    claims = phase2_output.get("claims", [])
    if not claims or "ERROR" in claims[0]:
        print(f"\n--- Report ---\nError in Phase 2: Could not extract claims.")
        return

    # Phase 3
    print(f"Phase 2 Complete. Triangulating {len(claims)} claims against external evidence...")
    # Create a list of all verification tasks to run them concurrently for speed
    fact_check_task = query_fact_check_api(claims)
    corroboration_tasks = [find_trusted_corroboration(claim) for claim in claims]
    
    # Use asyncio.gather to run all network-bound tasks at the same time
    all_evidence_results = await asyncio.gather(fact_check_task, *corroboration_tasks)
    
    fact_check_data = all_evidence_results[0]
    corroboration_data = all_evidence_results[1:]

    # --- Final Report ---
    print("\n\n--- Final Analysis Report ---")
    print("="*40)
    print(f"Publisher Credibility Tier: {phase1_output['tier']}")
    print("\n--- Bias & Framing Report ---")
    print(phase2_output["bias_report"])
    
    print("\n--- Claim-by-Claim Verification ---")
    if not claims:
        print("No factual claims were extracted for verification.")
    else:
        for i, claim in enumerate(claims):
            print(f"\n▶ Claim #{i+1}: \"{claim}\"")
            print(f"  ┃")
            print(f"  ┣━ Fact-Check DB: {fact_check_data.get(claim, 'N/A')}")
            print(f"  ┗━ Trusted Corroboration:")
            corroborations = corroboration_data[i]
            if corroborations:
                for c in corroborations[:3]: # Show top 3 results
                    print(f"     • {c.get('title', 'No Title')}")
                    print(f"       ({c.get('link', '#')})")
            else:
                print("     - No corroboration found in Tier 1 & 2 sources.")

    print("\n" + "="*40)
    print("--- Analysis Complete ---")

if __name__ == "__main__":
    url_to_check = "https://timesofindia.indiatimes.com/technology/tech-tips/rise-in-covid-19-cases-7-essential-medical-gadgets-for-home-use/articleshow/121653588.cms"
    asyncio.run(analyze_article(url_to_check))