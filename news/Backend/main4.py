# filename: main.py

import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
import urllib.parse
import re

from source_tiering import get_source_tier, SOURCE_TIERS
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    JsonCssExtractionStrategy
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

load_dotenv()

# --- Configurations ---
TOGETHER_AI_MODEL = "meta-llama/Llama-3-70b-chat-hf"
TOGETHER_AI_API_URL = "https://api.together.xyz/v1/chat/completions"
GOOGLE_FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
CHARACTER_LIMIT_FOR_CHUNKING = 15000

# --- Phase 1 & 3 Functions (Unchanged) ---
# ... (process_input, call_llm, batch_query_fact_checks, batch_find_trusted_corroboration functions are unchanged) ...
async def process_input(input_content: str):
    md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.5))
    config = CrawlerRunConfig(markdown_generator=md_generator)
    source_url = input_content if input_content.startswith('http') else 'raw_text_input'
    async with AsyncWebCrawler(verbose=False) as crawler:
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
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=json_payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e: return f"LLM_API_ERROR: {e.response.status_code} - {e.response.text}"
        except Exception as e: return f"LLM_API_ERROR: {e}"

async def batch_query_fact_checks(claims: list[str]):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key: return {claim: "ERROR: GOOGLE_API_KEY not found." for claim in claims}
    results = {}
    async with httpx.AsyncClient() as client:
        tasks = [client.get(GOOGLE_FACT_CHECK_API_URL, params={"query": claim, "key": api_key, "languageCode": "en"}) for claim in claims]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, response in enumerate(responses):
            claim = claims[i]
            if isinstance(response, Exception): results[claim] = "API query failed."
            else:
                data = response.json()
                if data and "claims" in data:
                    review = data["claims"][0]["claimReview"][0]
                    rating, publisher = review.get("textualRating", "N/A"), review.get("publisher", {}).get("name", "N/A")
                    results[claim] = f"RATING: {rating} (Publisher: {publisher})"
                else: results[claim] = "No fact-check found."
    return results

async def batch_find_trusted_corroboration(claims: list[str]):
    """
    Vector 2: Uses a single Crawl4AI instance and arun_many to efficiently search for all claims.
    """
    print(f"Starting batch corroboration search for {len(claims)} claims...")
    trusted_domains = [domain for domain, tier in SOURCE_TIERS.items() if tier in [1, 2]]
    
    search_urls = []
    for claim in claims:
        quoted_claim = f'"{claim}" '
        sites = ' OR '.join([f'site:{domain}' for domain in trusted_domains])
        search_query = quoted_claim + sites
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}"
        search_urls.append(search_url)

    schema = {"name": "GoogleResults", "baseSelector": "div.g", "fields": [{"name": "title", "selector": "h3", "type": "text"}, {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"}]}
    config = CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema))

    # Instantiate the crawler ONCE
    async with AsyncWebCrawler() as crawler:
        # Use arun_many to process all URLs in a managed pool
        results = await crawler.arun_many(urls=search_urls, config=config)
    
    # Process the list of results
    final_corroborations = []
    for result in results:
        if result.success and result.extracted_content:
            try:
                final_corroborations.append(json.loads(result.extracted_content))
            except json.JSONDecodeError:
                final_corroborations.append([])
        else:
            final_corroborations.append([]) # Append an empty list for failed crawls
            
    return final_corroborations

def chunk_text(text: str, chunk_size: int = 15000, overlap: int = 500):
    if len(text) <= chunk_size: return [text]
    chunks = []; start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# --- UPDATED: Phase 2 function with robust parsing ---
async def extract_claims_and_bias(article_text: str):
    api_key = os.getenv("TOGETHER_AI_API_KEY")
    if not api_key: return {"claims": ["ERROR: API key not found."], "bias_report": "ERROR: API key not found."}

    bias_prompt = f"""Analyze the tone, sentiment... bias rating from 1 (Neutral) to 5 (Highly Biased)... Article:\n{article_text[:CHARACTER_LIMIT_FOR_CHUNKING]}"""
    bias_task = call_llm(api_key, bias_prompt)

    claim_prompt_template = """Analyze... Present the output as a JSON object with a single key "claims"... Article Text:\n{}"""
    
    all_claims = []
    
    if len(article_text) > CHARACTER_LIMIT_FOR_CHUNKING:
        print(f"Article text is long ({len(article_text)} chars), splitting into chunks...")
        text_chunks = chunk_text(article_text)
        claim_tasks = [call_llm(api_key, claim_prompt_template.format(chunk), is_json_output=True) for chunk in text_chunks]
        all_tasks = [bias_task] + claim_tasks
        results = await asyncio.gather(*all_tasks)
        
        bias_report, claim_results = results[0], results[1:]
        
        for res in claim_results:
            if "LLM_API_ERROR" in res: continue
            try:
                data = json.loads(res)
                # --- NEW ROBUST PARSING LOGIC ---
                claims_list = data.get('claims', [])
                if isinstance(claims_list, list):
                    for item in claims_list:
                        if isinstance(item, str):
                            all_claims.append(item)
                        elif isinstance(item, dict):
                            # If item is a dict, extract the first string value found
                            for value in item.values():
                                if isinstance(value, str):
                                    all_claims.append(value)
                                    break 
                # --- END NEW LOGIC ---
            except (json.JSONDecodeError, TypeError): continue
    else:
        claim_prompt = claim_prompt_template.format(article_text)
        claim_task = call_llm(api_key, claim_prompt, is_json_output=True)
        bias_report, claim_result = await asyncio.gather(bias_task, claim_task)
        if "LLM_API_ERROR" in claim_result: all_claims.append(claim_result)
        else:
            try:
                data = json.loads(claim_result)
                # --- NEW ROBUST PARSING LOGIC (for non-chunked text too) ---
                claims_list = data.get('claims', [])
                if isinstance(claims_list, list):
                    for item in claims_list:
                        if isinstance(item, str):
                            all_claims.append(item)
                        elif isinstance(item, dict):
                            for value in item.values():
                                if isinstance(value, str):
                                    all_claims.append(value)
                                    break
                # --- END NEW LOGIC ---
            except (json.JSONDecodeError, TypeError): all_claims.append("LLM did not return valid JSON.")

    # Now the set() operation will be safe as all_claims only contains strings
    final_claims = sorted(list(set(all_claims)))
    return {"claims": final_claims, "bias_report": bias_report}

# --- Main Workflow (no changes needed) ---
async def analyze_article(user_input: str):
    # This main function is now ready for the final Phase 4 implementation.
    # For now, it will run the fixed Phase 2 and working Phase 3.
    print("--- Starting Full Analysis ---")
    input_to_crawl = f"raw://{user_input}" if not user_input.strip().startswith('http') else user_input.strip()
    phase1 = await process_input(input_to_crawl)
    if phase1["error"]: print(f"\nReport Error in Phase 1: {phase1['error']}"); return
    
    print("Phase 1 Complete. Deconstructing content...")
    phase2 = await extract_claims_and_bias(phase1["text"])
    claims = phase2.get("claims", [])
    if not claims or ("ERROR" in claims[0] if claims else False): print(f"\nReport Error in Phase 2: {claims[0] if claims else 'Could not extract claims.'}"); return

    print(f"Phase 2 Complete. Triangulating {len(claims)} claims...")
    fact_check_task = batch_query_fact_checks(claims)
    corroboration_task = batch_find_trusted_corroboration(claims)
    results = await asyncio.gather(fact_check_task, corroboration_task)
    fact_check_data, corroboration_data = results[0], results[1]

    print("\n\n--- Analysis Report (Phases 1-3) ---")
    print("="*40)
    print(f"Publisher Credibility Tier: {phase1['tier']}")
    print("\n--- Bias & Framing Report ---")
    print(phase2["bias_report"])
    print("\n--- Claim-by-Claim Verification ---")
    for i, claim in enumerate(claims):
        print(f"\n▶ Claim #{i+1}: \"{claim}\"")
        print(f"  ┣━ Fact-Check DB: {fact_check_data.get(claim, 'N/A')}")
        print(f"  ┗━ Trusted Corroboration:")
        corroborations = corroboration_data[i] if i < len(corroboration_data) else []
        if corroborations:
            for c in corroborations[:3]: print(f"     • {c.get('title', 'N/A')} ({c.get('link', '#')})")
        else: print("     - No corroboration found in Tier 1 & 2 sources.")
    print("\n" + "="*40)
    print("--- Analysis Complete ---")

if __name__ == "__main__":
    url_to_check = "https://timesofindia.indiatimes.com/technology/top-10-useful-gadgets-for-home-use/articleshow/121653588.cms"
    asyncio.run(analyze_article(url_to_check))