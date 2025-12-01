#!/usr/bin/env python
"""
Minimal BNF Proxy Test Service
Tests if Bright Data residential proxy can bypass Cloudflare on BNF website.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import urllib3

# Suppress SSL verification warnings (required for Bright Data proxy)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="BNF Proxy Test")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bright Data residential proxy configuration
BRIGHT_DATA_PROXY = {
    'username': 'brd-customer-hl_3dba8aa2-zone-residential_proxy1',
    'password': 'i4c5leuevuqr',
    'host': 'brd.superproxy.io',
    'port': '33335'
}

# Build proxy URL
proxy_url = f"http://{BRIGHT_DATA_PROXY['username']}:{BRIGHT_DATA_PROXY['password']}@{BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}"
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Create session with proxy
session = requests.Session()
session.headers.update(HEADERS)
session.proxies.update(proxies)


@app.get("/")
async def root():
    return {"status": "ok", "message": "BNF Proxy Test Service"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/test-bnf")
async def test_bnf():
    """Test fetching amoxicillin page from BNF via Bright Data proxy"""
    url = "https://bnf.nice.org.uk/drugs/amoxicillin/"

    try:
        print(f"Testing BNF request via Bright Data proxy...")
        print(f"URL: {url}")
        print(f"Proxy: {BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}")

        # verify=False needed for Bright Data proxy SSL interception
        response = session.get(url, timeout=60, verify=False)

        result = {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "url": url,
            "proxy_used": f"{BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}",
            "response_length": len(response.text),
        }

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title')
            result["page_title"] = title.text if title else "No title found"

            # Try to find drug name
            drug_name = soup.find('h1')
            result["drug_name"] = drug_name.text.strip() if drug_name else "Not found"

            # Check for Cloudflare challenge page indicators
            if "challenge" in response.text.lower() or "cloudflare" in response.text.lower():
                result["cloudflare_blocked"] = True
            else:
                result["cloudflare_blocked"] = False
        else:
            result["error"] = f"HTTP {response.status_code}"

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "proxy_used": f"{BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}"
        }


@app.get("/test-no-proxy")
async def test_no_proxy():
    """Test fetching BNF without proxy (should fail with 403 from Cloud Run)"""
    url = "https://bnf.nice.org.uk/drugs/amoxicillin/"

    try:
        print(f"Testing BNF request WITHOUT proxy...")

        # Make request without proxy
        direct_session = requests.Session()
        direct_session.headers.update(HEADERS)

        response = direct_session.get(url, timeout=30)

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "url": url,
            "proxy_used": None,
            "response_length": len(response.text),
            "note": "This should fail with 403 from Cloud Run due to Cloudflare blocking GCP IPs"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "proxy_used": None
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
