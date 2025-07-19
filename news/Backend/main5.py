# filename: main.py (Final Version with Rate-Limit Delay)

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
CONCURRENCY_LIMIT = 3 # Limit simultaneous requests

# --- All Helper and Phase 1-4 Functions ---
# Note: The only change is in the main 'analyze_article' function at the bottom.
# All functions from the previous step are included here for completeness.

async def process_input(input_content: str):
    config = CrawlerRunConfig(
        css_selector="div._s30J", 
        markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.5))
    )
    source_url = input_content if input_content.startswith('http') else 'raw_text_input'
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(input_content, config=config)
    if result.success and result.markdown:
        tier = get_source_tier(source_url)
        core_text = result.markdown.fit_markdown 
        return {"tier": tier, "text": core_text, "error": None}
    return {"error": result.error_message, "tier": None, "text": None}

async def call_llm(api_key: str, prompt: str, is_json_output: bool = False):
    headers = {"Authorization": f"Bearer {api_key}"}
    json_payload = {"model": TOGETHER_AI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0, "max_tokens": 2048}
    if is_json_output: json_payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=json_payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e: return f"LLM_API_ERROR: {e.response.status_code} - {e.response.text}"
        except Exception as e: return f"LLM_API_ERROR: {e}"

def chunk_text(text: str, chunk_size: int = 15000, overlap: int = 500):
    if len(text) <= chunk_size: return [text]
    chunks = []; start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks

async def extract_claims_and_bias(article_text: str):
    api_key = os.getenv("TOGETHER_AI_API_KEY")
    if not api_key: return {"claims": ["ERROR: API key not found."], "bias_report": "ERROR: API key not found."}
    bias_prompt = f"""Analyze the tone... bias rating from 1 (Neutral) to 5 (Highly Biased)... Article:\n{article_text[:CHARACTER_LIMIT_FOR_CHUNKING]}"""
    bias_task = call_llm(api_key, bias_prompt)
    claim_prompt_template = """Analyze... Present... a JSON object with a single key "claims"... Article Text:\n{}"""
    all_claims = []
    if len(article_text) > CHARACTER_LIMIT_FOR_CHUNKING:
        text_chunks = chunk_text(article_text)
        claim_tasks = [call_llm(api_key, claim_prompt_template.format(chunk), is_json_output=True) for chunk in text_chunks]
        results = await asyncio.gather(bias_task, *claim_tasks)
        bias_report, claim_results = results[0], results[1:]
        for res in claim_results:
            if "LLM_API_ERROR" in res: continue
            try:
                data = json.loads(res)
                claims_list = data.get('claims', [])
                if isinstance(claims_list, list):
                    for item in claims_list:
                        if isinstance(item, str): all_claims.append(item)
                        elif isinstance(item, dict):
                            for value in item.values():
                                if isinstance(value, str): all_claims.append(value); break
            except (json.JSONDecodeError, TypeError): continue
    else:
        claim_prompt = claim_prompt_template.format(article_text)
        claim_task = call_llm(api_key, claim_prompt, is_json_output=True)
        bias_report, claim_result = await asyncio.gather(bias_task, claim_task)
        if "LLM_API_ERROR" not in claim_result:
            try:
                data = json.loads(claim_result)
                claims_list = data.get('claims', [])
                if isinstance(claims_list, list):
                    for item in claims_list:
                        if isinstance(item, str): all_claims.append(item)
                        elif isinstance(item, dict):
                            for value in item.values():
                                if isinstance(value, str): all_claims.append(value); break
            except (json.JSONDecodeError, TypeError): all_claims.append("LLM did not return valid JSON.")
    final_claims = sorted(list(set(all_claims)))
    return {"claims": final_claims, "bias_report": bias_report}

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

async def synthesize_evidence_and_score(claim: str, fact_check_result: str, corroboration_results: list):
    api_key = os.getenv("TOGETHER_AI_API_KEY")
    if not api_key: return {"synthesis": "ERROR: API key not found.", "verdict": "ERROR", "score": 0.0}
    evidence_text = f"1. Fact-Check DB: {fact_check_result}\n2. Corroboration in Tier 1&2 Sources: {'None found.' if not corroboration_results else 'Found.'}"
    prompt = f"""You are a news analyst. Given the original claim and evidence, write a one-sentence synthesis. Conclude with a verdict on a new line. Verdict must be one of: [Well-Supported], [Partially Supported], [Lacks Evidence], [Disputed], or [Actively Refuted].\n\nClaim: '{claim}'\nEvidence:\n{evidence_text}"""
    response_text = await call_llm(api_key, prompt)
    if "LLM_API_ERROR" in response_text: return {"synthesis": response_text, "verdict": "Error", "score": 0.0}
    verdict_map = { "Well-Supported": 1.0, "Partially Supported": 0.75, "Lacks Evidence": 0.5, "Disputed": 0.25, "Actively Refuted": 0.0 }
    verdict, score = "Error", 0.0
    for key in verdict_map:
        if key in response_text:
            verdict = key.replace("[", "").replace("]", ""); score = verdict_map[key]; break
    synthesis = response_text.split("\n")[0]
    return {"synthesis": synthesis, "verdict": verdict, "score": score}

def calculate_final_score(source_tier: int, bias_report: str, claim_scores: list[float]):
    tier_score_map = {1: 100, 2: 90, 3: 75, 4: 40, 5: 10, "satire": 0}
    source_score = tier_score_map.get(source_tier, 60)
    evidence_score = (sum(claim_scores) / len(claim_scores) * 100) if claim_scores else 50
    bias_rating_match = re.search(r'Bias rating:\s*(\d)', bias_report, re.IGNORECASE)
    bias_rating = int(bias_rating_match.group(1)) if bias_rating_match else 3
    bias_score = max(0, 100 - (bias_rating - 1) * 25)
    final_score = (source_score * 0.30) + (evidence_score * 0.50) + (bias_score * 0.20)
    return {"final_score": round(final_score, 2), "components": {"Source": source_score, "Evidence": round(evidence_score,2), "Bias": bias_score}}

# --- Main Workflow (Updated with Rate-Limit Delay) ---
async def analyze_article(user_input: str):
    print("--- Starting Full Analysis (All Phases) ---")
    phase1 = await process_input(user_input)
    if phase1["error"]: print(f"Report Error in Phase 1: {phase1['error']}"); return
    
    print("Phase 1 Complete. Deconstructing content...")
    phase2 = await extract_claims_and_bias(phase1["text"])
    claims = phase2.get("claims", [])
    if not claims or ("ERROR" in claims[0] if claims else False): print(f"Report Error in Phase 2: {claims[0] if claims else 'Could not extract claims.'}"); return

    print(f"Phase 2 Complete. Triangulating {len(claims)} claims...")
    fact_check_task = batch_query_fact_checks(claims)
    corroboration_task = batch_find_trusted_corroboration(claims)
    fact_check_data, corroboration_data = await asyncio.gather(fact_check_task, corroboration_task)
    
    print("Phase 3 Complete. Synthesizing evidence...")
    
    # --- FINAL FIX: Semaphore WITH a delay to respect API rate limits ---
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async def controlled_synthesis(claim, fact_check, corroboration):
        async with semaphore:
            result = await synthesize_evidence_and_score(claim, fact_check, corroboration)
            # Add a 1-second delay after each call to respect the 1 QPS limit
            await asyncio.sleep(1) 
            return result

    synthesis_tasks = [controlled_synthesis(claim, fact_check_data.get(claim), corroboration_data[i]) for i, claim in enumerate(claims)]
    claim_synthesis_results = await asyncio.gather(*synthesis_tasks)
    
    print("Phase 4 Synthesis Complete. Calculating final score...")
    claim_scores = [res['score'] for res in claim_synthesis_results]
    final_score_data = calculate_final_score(phase1["tier"], phase2["bias_report"], claim_scores)

    # --- Final Report ---
    print("\n\n--- Final Analysis Report ---")
    print("="*60)
    print(f"  FINAL CREDIBILITY SCORE: {final_score_data['final_score']} / 100")
    print(f"  (Components: Source={final_score_data['components']['Source']}, Evidence={final_score_data['components']['Evidence']}, Bias={final_score_data['components']['Bias']})")
    print("="*60)
    print(f"\nPublisher Credibility Tier: {phase1['tier']}")
    print("\n--- Bias & Framing Report ---")
    print(phase2["bias_report"])
    print("\n--- Claim-by-Claim Verification ---")
    for i, claim in enumerate(claims):
        synthesis_result = claim_synthesis_results[i]
        print(f"\n▶ Claim #{i+1}: \"{claim}\"")
        print(f"  ┣━ Verdict: {synthesis_result['verdict']}")
        print(f"  ┗━ AI Synthesis: {synthesis_result['synthesis']}")
    print("\n" + "="*60)
    print("--- Analysis Complete ---")

if __name__ == "__main__":
    url_to_check = "https://timesofindia.indiatimes.com/technology/top-10-useful-gadgets-for-home-use/articleshow/121653588.cms"
    asyncio.run(analyze_article(user_input=url_to_check))