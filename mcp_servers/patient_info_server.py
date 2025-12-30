#!/usr/bin/env python3
"""
MCP Server for Patient Information.

Provides tools to retrieve comprehensive patient information including demographics,
current medications, medical history, and vital statistics.
"""

from typing import Optional
from fastmcp import FastMCP
from datetime import datetime

# Initialize FastMCP server
mcp = FastMCP(
    "PatientInfo",
    instructions="Patient information service providing demographics, current medications, medical history, and vital statistics for clinical decision support"
)

# Mock patient database (in a real system, this would query an EHR/EMR)
PATIENT_DATABASE = {
    "P001": {
        "patient_id": "P001",
        "age": "3 years",
        "gender": "Male",
        "weight_kg": 14.5,
        "height_cm": 95,
        "ethnicity": "White British",
        "current_medications": [],
        "existing_conditions": [],
        "allergies": [],
        "family_history": ["Asthma (father)"]
    },
    "P002": {
        "patient_id": "P002",
        "age": "65 years",
        "gender": "Female",
        "weight_kg": 72,
        "height_cm": 165,
        "ethnicity": "White British",
        "current_medications": ["Metformin 500mg BD", "Ramipril 5mg OD"],
        "existing_conditions": ["Type 2 Diabetes", "Hypertension"],
        "allergies": ["Penicillin"],
        "family_history": ["Type 2 Diabetes (mother)", "CVD (father)"]
    },
    "P003": {
        "patient_id": "P003",
        "age": "45 years",
        "gender": "Female",
        "weight_kg": 68,
        "height_cm": 162,
        "ethnicity": "Asian British",
        "current_medications": ["Salbutamol inhaler PRN"],
        "existing_conditions": ["Asthma"],
        "allergies": ["NSAIDs"],
        "family_history": ["Asthma (sister)"]
    },
    "P004": {
        "patient_id": "P004",
        "age": "72 years",
        "gender": "Male",
        "weight_kg": 85,
        "height_cm": 178,
        "ethnicity": "White British",
        "current_medications": ["Atorvastatin 40mg ON", "Aspirin 75mg OD"],
        "existing_conditions": ["Hyperlipidemia", "Previous MI"],
        "allergies": [],
        "family_history": ["CVD (father, mother)"]
    },
    "P005": {
        "patient_id": "P005",
        "age": "15 years",
        "gender": "Female",
        "weight_kg": 52,
        "height_cm": 160,
        "ethnicity": "Mixed",
        "current_medications": [],
        "existing_conditions": [],
        "allergies": [],
        "family_history": []
    },
    "P006": {
        "patient_id": "P006",
        "age": "28 years",
        "gender": "Female",
        "weight_kg": 58,
        "height_cm": 168,
        "ethnicity": "White British",
        "current_medications": [],
        "existing_conditions": ["Ehlers-Danlos Syndrome (Hypermobile type)"],
        "allergies": [],
        "family_history": ["EDS (mother)"]
    }
}


@mcp.tool(
    name="get_patient_info",
    description="Retrieve comprehensive patient information including demographics, current medications, medical history, and vital statistics"
)
def get_patient_info(patient_id: str) -> dict:
    """
    Get comprehensive patient information.

    Args:
        patient_id: Patient identifier (e.g., "P001", "P002")

    Returns:
        Dictionary containing:
            - patient_id (str): Patient identifier
            - age (str): Patient age
            - gender (str): Patient gender
            - weight_kg (float): Weight in kilograms
            - height_cm (float): Height in centimeters
            - bmi (float): Calculated BMI
            - ethnicity (str): Ethnic background
            - current_medications (list): List of current medications
            - existing_conditions (list): List of existing medical conditions
            - allergies (list): List of known allergies
            - family_history (list): Relevant family medical history
            - current_season (str): Current season (for seasonal conditions)
            - current_date (str): Current date
            - success (bool): Whether retrieval succeeded
            - error (str|None): Error message if failed
    """
    # Get current season
    month = datetime.now().month
    if month in [12, 1, 2]:
        season = "Winter"
    elif month in [3, 4, 5]:
        season = "Spring"
    elif month in [6, 7, 8]:
        season = "Summer"
    else:
        season = "Autumn"

    if patient_id not in PATIENT_DATABASE:
        return {
            'success': False,
            'error': f'Patient {patient_id} not found in database',
            'patient_id': patient_id
        }

    patient = PATIENT_DATABASE[patient_id].copy()

    # Calculate BMI
    weight = patient['weight_kg']
    height_m = patient['height_cm'] / 100
    bmi = round(weight / (height_m ** 2), 1)

    patient['bmi'] = bmi
    patient['current_season'] = season
    patient['current_date'] = datetime.now().strftime("%Y-%m-%d")
    patient['success'] = True
    patient['error'] = None

    return patient


@mcp.tool(
    name="get_current_season",
    description="Get the current season and date for seasonal condition considerations (e.g., RSV in winter, hay fever in spring)"
)
def get_current_season() -> dict:
    """
    Get current season and date.

    Returns:
        Dictionary containing:
            - season (str): Current season (Winter, Spring, Summer, Autumn)
            - month (str): Current month name
            - date (str): Current date (YYYY-MM-DD)
            - seasonal_notes (str): Notes about seasonal health considerations
    """
    now = datetime.now()
    month = now.month
    month_name = now.strftime("%B")

    if month in [12, 1, 2]:
        season = "Winter"
        notes = "Peak season for: RSV, influenza, norovirus, respiratory infections"
    elif month in [3, 4, 5]:
        season = "Spring"
        notes = "Peak season for: hay fever, allergic rhinitis, asthma exacerbations"
    elif month in [6, 7, 8]:
        season = "Summer"
        notes = "Peak season for: gastroenteritis, insect bites, heat-related illness"
    else:
        season = "Autumn"
        notes = "Peak season for: respiratory infections increasing, flu vaccine season"

    return {
        'season': season,
        'month': month_name,
        'date': now.strftime("%Y-%m-%d"),
        'seasonal_notes': notes
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
