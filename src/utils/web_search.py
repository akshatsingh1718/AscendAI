from urllib.parse import urlparse
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
import os
import requests
import json

def search_with_serper(self, query: str) -> Dict:
    """
    Perform a web search using Serper API
    
    Args:
        query: The search query string
        
    Returns:
        Dict containing search results from Serper API
    """
    url = "https://google.serper.dev/search"

    # simple file cache for serper responses
    cache_dir = Path("cache/serper")
    cache_dir.mkdir(parents=True, exist_ok=True)
    qhash = hashlib.sha256(query.encode('utf-8')).hexdigest()
    cache_file = cache_dir / f"{qhash}.json"

    # return cached response if present
    if cache_file.exists():
        try:
            with cache_file.open('r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception as e:
            print(f"⚠️ Failed to read cache for query: {e}")

    payload = json.dumps({
        "q": query
    })

    headers = {
        'X-API-KEY': os.environ.get('SERPER_API_KEY', 'a82e506a1d9965b424c351f90e0396952b5d3c10'),
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        # save to cache (best-effort)
        try:
            with cache_file.open('w', encoding='utf-8') as fh:
                json.dump(data, fh)
        except Exception as e:
            print(f"⚠️ Failed to write cache file: {e}")
        return data
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Serper API error: {e}")
        return {}