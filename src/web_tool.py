from googlesearch import search
import requests
import re
import time

def search_duckduckgo_html_fallback(query: str) -> list:
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
        # <a class="result__a" href="URL">TITLE</a>
        pattern = r'class="result__a" href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, resp.text)
        
        results = []
        for href, title in matches[:15]:
            results.append({'url': href, 'title': title})
            
        return results
    except Exception as e:
        print(f"Fallback search failed: {e}")
        return []

def process_results(results, footprint):
    """
    Categorizes a list of result objects/dicts into the footprint dictionary.
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

    count = 0
    for res in results:
        # Normalize input (Google returns objects, DDG fallback returns dicts)
        if isinstance(res, dict):
            url = res.get('url', '').lower()
            title = res.get('title', '').lower()
            raw_url = res.get('url')
        else:
            # Assumes googlesearch-python result object
            url = res.url.lower()
            title = res.title.lower() if res.title else ""
            raw_url = res.url

        if not raw_url: continue
        count += 1

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
    
    return count

def find_provider_url(name: str, city: str, state: str) -> dict:
    """
    Orchestrates the search: Google -> Fallback to DDG -> Return Categorized Footprint.
    """
    query = f"{name} {city} {state}" 
    print(f"Searching for digital footprint: {query}")

    footprint = {
        "official_site": None,
        "social_media": [],
        "directories": [],
        "other_mentions": []
    }

    # Attempt 1: Google
    try:
        # advanced=True is required to get titles
        google_results = list(search(query, num_results=15, advanced=True))
        
        if google_results:
            print(f"Google returned {len(google_results)} results.")
            process_results(google_results, footprint)
            return footprint
        else:
            print("Google returned 0 results. Switching to fallback.")

    except Exception as e:
        print(f"Google Search error: {e}")

    # Attempt 2: DuckDuckGo HTML Fallback
    # (Runs if Google fails or returns 0 results)
    ddg_results = search_duckduckgo_html_fallback(query)
    if ddg_results:
        print(f"DuckDuckGo Fallback returned {len(ddg_results)} results.")
        process_results(ddg_results, footprint)
    
    return footprint

if __name__ == "__main__":
    # Test Block
    test_name = "Providence Hospital"
    test_city = "Mobile"
    test_state = "AL"
    
    print(f"Running footprint search for {test_name}...")
    result = find_provider_url(test_name, test_city, test_state)
    
    if result:
        print("\n--- Digital Footprint Found ---")
        print(f"Official Site: {result['official_site']}")
        print(f"Social Media: {result['social_media']}")
        print(f"Directories: {len(result['directories'])} found")
        print(f"Other: {len(result['other_mentions'])}")
    else:
        print("No results found.")