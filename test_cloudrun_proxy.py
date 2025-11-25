#!/usr/bin/env python3
"""
Minimal test script to verify ScrapeOps proxy works from Google Cloud Run
Deploy this to Cloud Run to test before full integration
"""
import os
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

SCRAPEOPS_API_KEY = os.getenv("SCRAPEOPS_API_KEY", "b47fbecb-8312-45ea-906c-e587c9827252")

@app.get("/")
def root():
    return {"message": "ScrapeOps BNF Test API", "status": "ready"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/test-scrapeops-google")
def test_scrapeops_google():
    """Test ScrapeOps with Google.com (should work)"""
    try:
        response = requests.get(
            url='https://proxy.scrapeops.io/v1/',
            params={
                'api_key': SCRAPEOPS_API_KEY,
                'url': 'https://www.google.com',
            },
            timeout=30
        )

        return {
            "test": "Google.com via ScrapeOps",
            "status_code": response.status_code,
            "response_size": len(response.content),
            "success": response.status_code == 200,
            "has_google_content": b'google' in response.content.lower()
        }
    except Exception as e:
        return {
            "test": "Google.com via ScrapeOps",
            "error": str(e),
            "success": False
        }

@app.get("/test-scrapeops-bnf")
def test_scrapeops_bnf():
    """Test ScrapeOps with BNF using residential + render_js"""
    try:
        response = requests.get(
            url='https://proxy.scrapeops.io/v1/',
            params={
                'api_key': SCRAPEOPS_API_KEY,
                'url': 'https://bnf.nice.org.uk/drugs/',
                'render_js': 'true',
                'residential': 'true',
            },
            timeout=120
        )

        has_bnf = b'bnf' in response.content.lower() or b'formulary' in response.content.lower()

        return {
            "test": "BNF via ScrapeOps (residential + render_js)",
            "status_code": response.status_code,
            "response_size": len(response.content),
            "success": response.status_code == 200 and has_bnf,
            "has_bnf_content": has_bnf,
            "first_500_chars": response.text[:500] if response.status_code == 200 else None
        }
    except requests.exceptions.Timeout:
        return {
            "test": "BNF via ScrapeOps",
            "error": "Request timed out after 120 seconds",
            "success": False
        }
    except Exception as e:
        return {
            "test": "BNF via ScrapeOps",
            "error": str(e),
            "success": False
        }

@app.get("/test-bnf-direct")
def test_bnf_direct():
    """Test direct BNF access (will likely fail from Cloud Run)"""
    try:
        response = requests.get(
            'https://bnf.nice.org.uk/drugs/',
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0'}
        )

        return {
            "test": "BNF direct (no proxy)",
            "status_code": response.status_code,
            "response_size": len(response.content),
            "success": response.status_code == 200
        }
    except Exception as e:
        return {
            "test": "BNF direct (no proxy)",
            "error": str(e),
            "success": False
        }

@app.get("/test-all")
def test_all():
    """Run all tests"""
    return {
        "google_test": test_scrapeops_google(),
        "bnf_proxy_test": test_scrapeops_bnf(),
        "bnf_direct_test": test_bnf_direct()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
