#!/usr/bin/env python
"""
Aneya API - Vercel Serverless Deployment
FastAPI Backend adapted for Vercel's serverless platform
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import httpx

# Import from local api directory
from clinical_decision_support_client import ClinicalDecisionSupportClient

# Global client instance (cached across warm starts)
_client: Optional[ClinicalDecisionSupportClient] = None


def get_client() -> ClinicalDecisionSupportClient:
    """
    Get or initialize the clinical decision support client.
    This function handles lazy initialization for serverless context.
    """
    global _client

    if _client is None:
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

        _client = ClinicalDecisionSupportClient(anthropic_api_key=anthropic_key)

    return _client


app = FastAPI(
    title="Aneya Clinical Decision Support API",
    version="1.0.0"
)

# Enable CORS for Vercel deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    """Request body for consultation analysis"""
    consultation: str
    patient_id: Optional[str] = None
    patient_age: Optional[str] = None
    allergies: Optional[str] = None
    user_ip: Optional[str] = None
    location_override: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


async def get_country_from_ip(ip_address: str) -> Optional[dict]:
    """
    Get country information from an IP address using ip-api.com.

    Args:
        ip_address: The IP address to lookup

    Returns:
        Dictionary with country and country_code, or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f'http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode'
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'fail':
                return None

            return {
                'ip': ip_address,
                'country': data.get('country'),
                'country_code': data.get('countryCode')
            }
    except Exception as e:
        print(f"Geolocation failed: {str(e)}")
        return None


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return {
        "status": "ok",
        "message": "Aneya Clinical Decision Support API is running on Vercel"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        client = get_client()
        return {
            "status": "healthy",
            "message": "All systems operational"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


@app.post("/analyze")
async def analyze_consultation(request: AnalysisRequest):
    """
    Analyze a clinical consultation and return recommendations

    Args:
        request: AnalysisRequest with consultation text and optional patient info

    Returns:
        Complete clinical decision support analysis
    """
    if not request.consultation.strip():
        raise HTTPException(status_code=400, detail="Consultation text is required")

    try:
        # Get client (will initialize if first request)
        client = get_client()

        # Connect to MCP servers if not already connected
        # This happens on cold starts
        if not hasattr(client, '_servers_connected'):
            await client.connect_to_servers(verbose=False)
            client._servers_connected = True

        # Determine location from user IP if provided
        location_to_use = request.location_override

        if not location_to_use and request.user_ip:
            geo_data = await get_country_from_ip(request.user_ip)
            if geo_data:
                location_to_use = geo_data.get('country_code')

        # Run clinical decision support workflow
        result = await client.clinical_decision_support(
            clinical_scenario=request.consultation,
            patient_id=request.patient_id,
            patient_age=request.patient_age,
            allergies=request.allergies,
            location_override=location_to_use,
            verbose=False  # Reduced logging for serverless
        )

        return result

    except Exception as e:
        print(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/examples")
async def get_examples():
    """Get example clinical scenarios for testing"""
    return {
        "examples": [
            {
                "id": "pediatric-croup",
                "name": "Pediatric Croup",
                "scenario": "3-year-old with croup, moderate stridor at rest, barking cough",
                "patient_id": "P001"
            },
            {
                "id": "post-op-sepsis",
                "name": "Post-Operative Sepsis",
                "scenario": "Post-operative sepsis, fever 38.5C, tachycardia, suspected wound infection",
                "patient_id": "P002"
            },
            {
                "id": "acute-asthma",
                "name": "Acute Asthma Exacerbation",
                "scenario": "45-year-old with severe asthma exacerbation, peak flow 40% predicted, breathless",
                "patient_id": "P003"
            },
            {
                "id": "community-pneumonia",
                "name": "Community-Acquired Pneumonia",
                "scenario": "72-year-old with CAP, CURB-65 score 2, productive cough, fever",
                "patient_id": "P004"
            }
        ]
    }


# Vercel expects a variable named 'app' or 'handler'
handler = app
