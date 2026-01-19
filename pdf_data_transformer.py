"""
PDF Data Transformer

Transforms consultation form JSONB data to DoctorReportCard component format.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime


def transform_form_to_doctor_report_card(
    form_data: Dict[str, Any],
    patient_info: Dict[str, Any],
    appointment_info: Optional[Dict[str, Any]] = None,
    form_type: str = "antenatal"
) -> Dict[str, Any]:
    """
    Transform consultation form JSONB data to DoctorReportCard format.

    Args:
        form_data: JSONB form data from database
        patient_info: Patient details (name, ID, address)
        appointment_info: Appointment context (optional)
        form_type: Type of form (antenatal, infertility, obgyn)

    Returns:
        Dictionary with patientData and pregnancyHistory
    """
    # Extract vitals
    vital_signs = form_data.get('vital_signs', {})
    medical_history_data = form_data.get('medical_history', {})

    # Build patient data
    patient_data = {
        # Patient information
        'patientName': patient_info.get('name', ''),
        'patientId': patient_info.get('patient_id', ''),
        'address': patient_info.get('address', ''),

        # Vitals (convert numbers to strings)
        'age': str(calculate_age(patient_info.get('date_of_birth'))),
        'height': str(vital_signs.get('height', '')),
        'weight': str(vital_signs.get('weight', '')),
        'bloodPressureSystolic': str(vital_signs.get('systolic_bp', '')),
        'bloodPressureDiastolic': str(vital_signs.get('diastolic_bp', '')),

        # Medical conditions
        'diabetes': medical_history_data.get('diabetes', False),
        'hypertension': medical_history_data.get('hypertension', False),
        'allergies': medical_history_data.get('allergies', False),
        'smokingStatus': medical_history_data.get('smoking', False),

        # Medical history text
        'medicalHistory': build_medical_history_text(form_data)
    }

    # Extract pregnancy history
    pregnancy_history = transform_pregnancy_history(
        form_data.get('previous_pregnancies', [])
    )

    return {
        'patientData': patient_data,
        'pregnancyHistory': pregnancy_history
    }


def transform_pregnancy_history(pregnancies: List[Dict]) -> List[Dict]:
    """
    Transform JSONB pregnancy data to DoctorReportCard PregnancyRecord format.
    """
    records = []
    for idx, preg in enumerate(pregnancies, start=1):
        record = {
            'no': idx,
            'modeOfConception': preg.get('mode_of_conception', 'Natural'),
            'modeOfDelivery': preg.get('mode_of_delivery', ''),
            'sexAge': format_sex_age(preg.get('sex'), preg.get('age')),
            'aliveDead': 'Alive' if preg.get('alive', True) else 'Dead',
            'abortion': 'Yes' if preg.get('abortion', False) else 'No',
            'birthWt': str(preg.get('birth_weight_kg', '')),
            'year': str(preg.get('year', '')),
            'breastFeeding': format_breastfeeding(preg.get('breastfeeding_months')),
            'anomalies': preg.get('anomalies', 'None')
        }
        records.append(record)

    return records


def format_sex_age(sex: Optional[str], age: Optional[int]) -> str:
    """Format sex and age as 'Male/5yrs' or 'Female/2yrs'."""
    if not sex:
        return ''
    sex_formatted = sex.capitalize()
    age_str = f'{age}yrs' if age else ''
    return f'{sex_formatted}/{age_str}' if age_str else sex_formatted


def format_breastfeeding(months: Optional[int]) -> str:
    """Format breastfeeding duration as 'Yes - 6mo'."""
    if not months:
        return 'No'
    return f'Yes - {months}mo'


def build_medical_history_text(form_data: Dict) -> str:
    """
    Build comprehensive medical history text from form data.
    """
    sections = []

    # Add treatment history
    if 'treatment_history' in form_data:
        sections.append(form_data['treatment_history'])

    # Add significant findings
    medical_history = form_data.get('medical_history', {})
    if medical_history:
        conditions = []
        if medical_history.get('diabetes'):
            conditions.append('Diabetes')
        if medical_history.get('hypertension'):
            conditions.append('Hypertension')
        if medical_history.get('pcos'):
            conditions.append('PCOS')

        if conditions:
            sections.append(f"Known conditions: {', '.join(conditions)}")

    # Add any free-text history
    if 'history_text' in form_data:
        sections.append(form_data['history_text'])

    return '. '.join(sections) if sections else 'No significant medical history recorded.'


def calculate_age(date_of_birth: Optional[str]) -> int:
    """Calculate age from date of birth."""
    if not date_of_birth:
        return 0

    dob = datetime.fromisoformat(date_of_birth.replace('Z', '+00:00'))
    today = datetime.now()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


# Form-type-specific transformers

def transform_antenatal_form(form_data: Dict, patient_info: Dict) -> Dict:
    """Transform antenatal form to DoctorReportCard format."""
    return transform_form_to_doctor_report_card(
        form_data, patient_info, form_type='antenatal'
    )


def transform_infertility_form(form_data: Dict, patient_info: Dict) -> Dict:
    """Transform infertility form to DoctorReportCard format."""
    return transform_form_to_doctor_report_card(
        form_data, patient_info, form_type='infertility'
    )


def transform_obgyn_form(form_data: Dict, patient_info: Dict) -> Dict:
    """Transform OBGYN form to DoctorReportCard format."""
    return transform_form_to_doctor_report_card(
        form_data, patient_info, form_type='obgyn'
    )


# Dispatcher
FORM_TRANSFORMERS = {
    'antenatal': transform_antenatal_form,
    'infertility': transform_infertility_form,
    'obgyn': transform_obgyn_form
}


def transform_by_form_type(form_type: str, form_data: Dict, patient_info: Dict) -> Dict:
    """
    Route to appropriate transformer based on form type.
    """
    transformer = FORM_TRANSFORMERS.get(form_type, transform_form_to_doctor_report_card)
    return transformer(form_data, patient_info)
