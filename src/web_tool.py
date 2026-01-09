from googlesearch import search
import requests
import re
import time

def search_duckduckgo_html_fallback(query: str, num_results: int = 15) -> list:
    """
    Fallback: Scrapes DuckDuckGo HTML if Google fails.
    Returns a list of dicts: [{'url': '...', 'title': '...'}]
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://duckduckgo.com/"
    }
    data = {"q": query}
    
    try:
        print(">> Triggering DuckDuckGo HTML Fallback...")
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # Regex to extract links (class="result__a")
        pattern = r'class="result__a" href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, resp.text)
        
        results = []
        for href, title in matches[:num_results]:
            results.append({'url': href, 'title': title})
            
        return results
    except Exception as e:
        print(f"Fallback search failed: {e}")
        return []

def _perform_web_search(query: str, num_results: int = 15) -> list:
    """
    Internal helper to perform search using Google, falling back to DDG.
    Returns a normalized list of dicts {'url': ..., 'title': ...}
    """
    print(f"Performing web search for: {query}")
    results = []

    # Attempt 1: Google
    try:
        google_results = list(search(query, num_results=num_results, advanced=True))
        if google_results:
            # Normalize Google results to dicts
            for res in google_results:
                results.append({
                    'url': res.url,
                    'title': res.title if res.title else ""
                })
            return results
        else:
            print("Google returned 0 results. Switching to fallback.")
    except Exception as e:
        print(f"Google Search error: {e}")

    # Attempt 2: DuckDuckGo Fallback
    return search_duckduckgo_html_fallback(query, num_results)

def find_provider_url(name: str, city: str, state: str) -> dict:
    """
    Orchestrates the search for a provider's digital footprint.
    """
    query = f"{name} {city} {state}" 
    
    # Use the shared search helper
    raw_results = _perform_web_search(query, num_results=15)
    
    footprint = {
        "official_site": None,
        "social_media": [],
        "directories": [],
        "other_mentions": []
    }

    process_results(raw_results, footprint)
    return footprint

def verify_address_claim(claimed_name: str, claimed_address: str) -> list:
    """
    Searches specifically for the combination of name and address to find confirmation links.
    Returns a list of URLs that mention both.
    """
    query = f"{claimed_name} {claimed_address}"
    raw_results = _perform_web_search(query, num_results=5)
    
    links = []
    for res in raw_results:
        links.append(res['url'])
        
    return links

def process_results(results, footprint):
    """
    Categorizes a list of result dicts into the footprint dictionary.
    """
    # 1. Social Media Domains
    social_domains = [
        'linkedin.com', 'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 
        'youtube.com', 'tiktok.com', 'pinterest.com'
    ]
    
    # 2. Directory/Review Domains
    directory_domains = [
        'healthgrades.com', 'webmd.com', 'doximity.com', 'vitals.com', 
        'usnews.com', 'yellowpages.com', 'sharecare.com', 'mapquest.com', 
        'yelp.com', 'zocdoc.com', 'md.com', 'health.usnews.com'
    ]
    
    # 3. Official Site Keywords
    official_keywords = [
        'clinic', 'md', 'associates', 'heart', 'care', 
        'hospital', 'health', 'medical', 'center', 
        'system', 'group', 'dr', 'physician', 'surgery', 'official', 'home'
    ]

    for res in results:
        url = res.get('url', '').lower()
        title = res.get('title', '').lower()
        raw_url = res.get('url')

        if not raw_url: continue

        # --- Category A: Social Media ---
        if any(domain in url for domain in social_domains):
            footprint["social_media"].append(raw_url)
            continue
            
        # --- Category B: Directories ---
        if any(domain in url for domain in directory_domains):
            footprint["directories"].append(raw_url)
            continue
            
        # --- Category C: Official Website Candidate ---
        if not footprint["official_site"]:
            if any(kw in title or kw in url for kw in official_keywords):
                footprint["official_site"] = raw_url
                continue
        
        # --- Category D: Everything Else ---
        footprint["other_mentions"].append(raw_url)

if __name__ == "__main__":
    # Test Block
    print("--- Testing General Search ---")
    fp = find_provider_url("Providence Hospital", "Mobile", "AL")
    print(f"Found Official: {fp['official_site']}")
    
    print("\n--- Testing Address Claim Verification ---")
    links = verify_address_claim("Providence Hospital", "6801 Airport Blvd")
    print(f"Confirmation Links: {links}")