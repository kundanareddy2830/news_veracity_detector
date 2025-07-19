# filename: main.py

import asyncio
from source_tiering import get_source_tier
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def process_input(input_content: str):
    """
    This single function processes content from either a URL or raw HTML string
    by leveraging Crawl4AI's prefix handling.
    """
    # Configure a markdown generator with a pruning filter to get the core article text[cite: 271, 337].
    # This filter removes boilerplate like ads, sidebars, and footers[cite: 272].
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.5)
    )
    config = CrawlerRunConfig(markdown_generator=md_generator)

    # Determine the source URL for tiering.
    source_url = input_content if input_content.startswith('http') else 'raw_text_input'
    
    async with AsyncWebCrawler() as crawler:
        # The arun method handles the full crawling and extraction process[cite: 559].
        result = await crawler.arun(input_content, config=config)

    if result.success and result.markdown:
        tier = get_source_tier(source_url)
        # We use 'fit_markdown' as it's the version cleaned by our PruningContentFilter[cite: 285, 339].
        core_text = result.markdown.fit_markdown 
        return {"tier": tier, "text": core_text, "error": None}
    else:
        return {"error": result.error_message, "tier": None, "text": None}

async def analyze_article(user_input: str):
    """
    Handles both URL and raw text input, calls the unified processing
    pipeline, and prints the result.
    """
    print("--- Starting Analysis ---")
    
    input_to_crawl = ""
    is_url = user_input.strip().startswith('http')

    if is_url:
        print("Input Type: URL")
        input_to_crawl = user_input.strip()
    else:
        print("Input Type: Raw HTML Text")
        # Prefix with 'raw://' to tell Crawl4AI to process the string directly[cite: 582, 488].
        input_to_crawl = f"raw://{user_input}"

    # --- UNIFIED PIPELINE BEGINS ---
    analysis = await process_input(input_to_crawl)
    
    print("\n--- Analysis Report ---")
    if analysis["error"]:
        print(f"An error occurred: {analysis['error']}")
    else:
        print(f"Publisher Credibility Tier: {analysis['tier']}")
        print("\n--- Extracted Article Core Text (Snippet) ---")
        print(f"{analysis['text'][:700]}...")
    
    print("\n--- Analysis Complete ---")


if __name__ == "__main__":
    # --- CHOOSE ONE EXAMPLE TO RUN ---

    # Example 1: Analyze an article from a URL
    url_to_check = "https://www.npr.org/2024/08/28/g-s1-19832/workers-killed-injured-delta-air-lines-atlanta"
    asyncio.run(analyze_article(url_to_check))

    # Example 2: Analyze an article from a raw HTML string
    # raw_html_content = """
    # <html>
    #   <head><title>Test Article</title></head>
    #   <body>
    #     <header>This is a header, it should be removed.</header>
    #     <main>
    #         <h1>A Major Event Happened</h1>
    #         <p>This is the core content of the article. A factual claim is that the sky is blue. Another claim is that water is wet.</p>
    #         <p>This paragraph contains opinions and should be treated as such by the LLM later.</p>
    #     </main>
    #     <footer>This is a footer and should also be removed.</footer>
    #   </body>
    # </html>
    # """
    # asyncio.run(analyze_article(raw_html_content))