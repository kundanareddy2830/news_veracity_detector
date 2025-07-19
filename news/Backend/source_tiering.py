

SOURCE_TIERS = {
    # Tier 1 (Highest Trust): Major international news wires
    "apnews.com": 1,
    "reuters.com": 1,

    # Tier 2 (High Trust): Major newspapers of record
    "nytimes.com": 2,
    "bbc.com": 2,
    "wsj.com": 2,

    # Tier 3 (Medium Trust): Reputable but smaller or with known leanings
    "theguardian.com": 3,
    "npr.org": 3,
    "aljazeera.com": 3,

    # Tier 4 (Low Trust): Known hyper-partisan sources
    "breitbart.com": 4,
    "dailycaller.com": 4,

    # Tier 5 (No Trust): Documented propaganda or conspiracy outlets
    "infowars.com": 5,

    # Special Category: Satire
    "theonion.com": "satire",
}

def get_source_tier(url: str) -> int | str:
    """
    Returns the credibility tier of a news source based on its domain.
    Defaults to Tier 3 if the source is not in the list.
    """
    if not url.startswith('http'):
        return "N/A (Raw Text Input)"
        
    try:
        domain = url.split('/')[2].replace('www.', '')
        return SOURCE_TIERS.get(domain, 3) # Default to Tier 3 (Medium Trust)
    except IndexError:
        return "Invalid URL"