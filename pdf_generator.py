"""
PDF Generator for Consultation Forms

This module generates PDF reports for consultations, including:
- Appointment details
- Patient information
- Consultation form data (all form types)
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from typing import Dict, Any, Optional
import requests


# Aneya color scheme
ANEYA_NAVY = HexColor('#0c3555')
ANEYA_TEAL = HexColor('#1d9e99')
ANEYA_GRAY = HexColor('#6b7280')
ANEYA_LIGHT_GRAY = HexColor('#d1d5db')


def format_field_label(field_name: str) -> str:
    """Convert snake_case field names to readable labels"""
    return field_name.replace('_', ' ').title()


def format_date_time(iso_string: str) -> str:
    """Format ISO datetime string to readable format"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%d %B %Y at %H:%M')
    except:
        return iso_string


def render_clinic_logo(c: canvas.Canvas, y: float, logo_url: str) -> bool:
    """
    Download clinic logo from GCS and render in top-right corner

    Args:
        c: ReportLab canvas
        y: Current Y position
        logo_url: Public URL of the clinic logo

    Returns:
        bool: True if logo rendered successfully, False otherwise
    """
    try:
        # Download logo with timeout
        response = requests.get(logo_url, timeout=5)
        response.raise_for_status()

        # Load image
        image_bytes = BytesIO(response.content)
        img = ImageReader(image_bytes)

        # Calculate scaling to fit within 70mm x 28mm
        img_width, img_height = img.getSize()
        max_width, max_height = 7*cm, 2.8*cm
        scale = min(max_width/img_width, max_height/img_height)

        scaled_width = img_width * scale
        scaled_height = img_height * scale

        # Position in top-right corner
        x_pos = 19*cm - scaled_width
        y_pos = y + 0.5*cm

        # Draw image
        c.drawImage(img, x_pos, y_pos,
                   width=scaled_width,
                   height=scaled_height,
                   preserveAspectRatio=True,
                   mask='auto')

        print(f"✅ Clinic logo rendered successfully")
        return True

    except Exception as e:
        print(f"⚠️  Failed to render clinic logo: {e}")
        return False  # Graceful fallback


def render_header(c: canvas.Canvas, y: float, doctor_info: Optional[Dict[str, Any]] = None) -> float:
    """
    Render the PDF header with title, generation date, and optional clinic logo

    Args:
        c: ReportLab canvas
        y: Current Y position
        doctor_info: Optional dict with clinic_name and clinic_logo_url

    Returns:
        float: Updated Y position
    """
    width, height = A4

    # Try to render clinic logo if available
    logo_rendered = False
    if doctor_info and doctor_info.get('clinic_logo_url'):
        logo_rendered = render_clinic_logo(c, y, doctor_info['clinic_logo_url'])

    # Fallback to clinic name as text if no logo rendered
    if not logo_rendered and doctor_info and doctor_info.get('clinic_name'):
        c.setFillColor(ANEYA_NAVY)
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(19*cm, y + 0.5*cm, doctor_info['clinic_name'])

    # Title
    c.setFillColor(ANEYA_NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, y, "Consultation Report")
    y -= 0.5*cm

    # Generation date
    c.setFillColor(ANEYA_GRAY)
    c.setFont("Helvetica", 10)
    generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
    c.drawCentredString(width/2, y, f"Generated: {generation_date}")
    y -= 1.5*cm

    return y


def render_section_header(c: canvas.Canvas, title: str, y: float) -> float:
    """Render a section header"""
    c.setFillColor(ANEYA_NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2*cm, y, title)
    y -= 0.2*cm

    # Underline
    c.setStrokeColor(ANEYA_TEAL)
    c.setLineWidth(2)
    c.line(2*cm, y, 19*cm, y)
    y -= 0.6*cm

    return y


def render_field(c: canvas.Canvas, label: str, value: Any, y: float, x_offset: float = 2*cm) -> float:
    """Render a field with label and value"""
    if value is None or value == '' or value == []:
        return y

    c.setFillColor(ANEYA_NAVY)
    c.setFont("Helvetica-Bold", 10)

    # Calculate label width to ensure enough spacing
    label_text = f"{label}:"
    label_width = c.stringWidth(label_text, "Helvetica-Bold", 10)

    # Use dynamic spacing: minimum 5cm for long labels, 4cm for shorter ones
    value_x_offset = max(x_offset + 5*cm, x_offset + label_width + 0.5*cm)

    c.drawString(x_offset, y, label_text)

    c.setFillColor(ANEYA_GRAY)
    c.setFont("Helvetica", 10)

    # Convert value to string
    value_str = str(value)

    # Handle long text with word wrapping
    if len(value_str) > 80:
        # Split into multiple lines
        max_width = 19*cm - value_x_offset
        lines = []
        words = value_str.split()
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", 10) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # Draw first line next to label
        if lines:
            c.drawString(value_x_offset, y, lines[0])
            y -= 0.4*cm

            # Draw remaining lines
            for line in lines[1:]:
                c.drawString(value_x_offset, y, line)
                y -= 0.4*cm
    else:
        c.drawString(value_x_offset, y, value_str)
        y -= 0.4*cm

    return y


def render_appointment_section(c: canvas.Canvas, appointment: Dict[str, Any], patient: Dict[str, Any], y: float) -> float:
    """Render appointment details section"""
    y = render_section_header(c, "Appointment Details", y)

    fields = [
        ("Patient Name", patient.get('name')),
        ("Date & Time", format_date_time(appointment.get('scheduled_time', ''))),
        ("Duration", f"{appointment.get('duration_minutes', 'N/A')} minutes"),
        ("Specialty", appointment.get('specialty', 'N/A')),
        ("Status", appointment.get('status', '').title()),
        ("Reason for Visit", appointment.get('reason')),
        ("Notes", appointment.get('notes')),
    ]

    for label, value in fields:
        y = render_field(c, label, value, y)

    y -= 0.6*cm
    return y


def render_patient_section(c: canvas.Canvas, patient: Dict[str, Any], y: float) -> float:
    """Render patient information section"""
    y = render_section_header(c, "Patient Information", y)

    # Calculate age from date_of_birth if available
    age_display = "Not recorded"
    if patient.get('date_of_birth'):
        try:
            # Handle various date formats
            dob_str = patient['date_of_birth']
            # Remove timezone info and parse
            if 'T' in dob_str:
                dob_str = dob_str.split('T')[0]
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
            age = (datetime.now() - dob).days // 365
            age_display = f"{age} years (DOB: {dob.strftime('%d %B %Y')})"
        except Exception as e:
            print(f"⚠️  Error parsing date_of_birth: {e}")
            # If parsing fails, just show the date if it looks reasonable
            dob_str = str(patient['date_of_birth'])
            if len(dob_str) > 20:
                age_display = "Not recorded"
            else:
                age_display = dob_str
    elif patient.get('age_years'):
        age_display = f"{patient['age_years']} years"

    # Get height and weight
    height = patient.get('height_cm')
    height_display = f"{height} cm" if height else "Not recorded"

    weight = patient.get('weight_kg')
    weight_display = f"{weight} kg" if weight else "Not recorded"

    fields = [
        ("Age", age_display),
        ("Sex", patient.get('sex', 'Not specified')),
        ("Height", height_display),
        ("Weight", weight_display),
        ("Allergies", patient.get('allergies') or "None recorded"),
        ("Current Medications", patient.get('current_medications') or "None recorded"),
        ("Current Conditions", patient.get('current_conditions') or "None recorded"),
    ]

    for label, value in fields:
        y = render_field(c, label, value, y)

    y -= 0.6*cm
    return y


def render_form_data_section(c: canvas.Canvas, form_data: Dict[str, Any], form_type: str, y: float) -> float:
    """Render consultation form data based on form type"""
    width, height = A4

    y = render_section_header(c, f"Consultation Form ({form_type.upper()})", y)

    # Check if we need a new page
    if y < 5*cm:
        c.showPage()
        y = height - 2*cm
        y = render_section_header(c, f"Consultation Form ({form_type.upper()}) - Continued", y)

    # Render nested JSONB data
    for section_key, section_value in form_data.items():
        # Check if need new page
        if y < 3*cm:
            c.showPage()
            y = height - 2*cm

        if isinstance(section_value, dict):
            # Nested section (e.g., "vital_signs", "physical_exam")
            c.setFillColor(ANEYA_TEAL)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(2.5*cm, y, format_field_label(section_key))
            y -= 0.5*cm

            for field_key, field_value in section_value.items():
                if field_value is not None and field_value != '' and field_value != []:
                    y = render_field(c, format_field_label(field_key), field_value, y, x_offset=3*cm)

                    # Check if need new page
                    if y < 3*cm:
                        c.showPage()
                        y = height - 2*cm

            y -= 0.4*cm
        elif isinstance(section_value, list):
            # List field (e.g., diagnoses)
            if section_value:  # Only render if not empty
                c.setFillColor(ANEYA_TEAL)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(2.5*cm, y, format_field_label(section_key))
                y -= 0.4*cm

                for item in section_value:
                    if isinstance(item, dict):
                        # Render each dict item
                        for k, v in item.items():
                            if v:
                                y = render_field(c, format_field_label(k), v, y, x_offset=3*cm)
                    else:
                        # Simple list item
                        c.setFillColor(ANEYA_GRAY)
                        c.setFont("Helvetica", 10)
                        c.drawString(3*cm, y, f"• {str(item)}")
                        y -= 0.4*cm

                y -= 0.4*cm
        else:
            # Top-level field
            if section_value is not None and section_value != '':
                y = render_field(c, format_field_label(section_key), section_value, y, x_offset=2.5*cm)

    return y


def generate_consultation_pdf(
    appointment: Dict[str, Any],
    patient: Dict[str, Any],
    form_data: Dict[str, Any],
    form_type: str = 'consultation_form',
    doctor_info: Optional[Dict[str, Any]] = None
) -> BytesIO:
    """
    Generate a PDF consultation report.

    Args:
        appointment: dict with appointment details
        patient: dict with patient information
        form_data: dict with consultation form JSONB data
        form_type: str indicating form type ('consultation_form', 'obgyn', 'infertility', 'antenatal')
        doctor_info: Optional dict with clinic_name and clinic_logo_url for header rendering

    Returns:
        BytesIO containing PDF bytes
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Track Y position
    y = height - 2*cm

    # Render sections
    y = render_header(c, y, doctor_info)
    y = render_appointment_section(c, appointment, patient, y)

    # Check if need new page before patient section
    if y < 8*cm:
        c.showPage()
        y = height - 2*cm

    y = render_patient_section(c, patient, y)

    # Check if need new page before form data
    if y < 8*cm:
        c.showPage()
        y = height - 2*cm

    y = render_form_data_section(c, form_data, form_type, y)

    # Add footer on last page
    c.setFillColor(ANEYA_LIGHT_GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 1.5*cm, "Aneya Healthcare Platform")
    c.drawCentredString(width/2, 1*cm, "This document is confidential and for medical professionals only")

    c.save()
    buffer.seek(0)
    return buffer


def render_custom_form_section(
    c: canvas.Canvas,
    section_config: Dict[str, Any],
    form_data: Dict[str, Any],
    y: float
) -> float:
    """
    Render a custom form section using pdf_template configuration.

    Args:
        c: ReportLab canvas
        section_config: PDF template section configuration
        form_data: Actual form data (JSONB)
        y: Current Y position

    Returns:
        float: Updated Y position
    """
    width, height = A4

    # Get section ID and title
    section_id = section_config.get('id', '')
    section_title = section_config.get('title', format_field_label(section_id))
    layout = section_config.get('layout', 'single_column')

    # Render section header
    y = render_section_header(c, section_title, y)

    # Get fields for this section
    fields = section_config.get('fields', [])

    # Render fields based on layout
    if layout == 'two_column':
        # Two column layout
        col_width = 8.5*cm
        left_x = 2*cm
        right_x = 11*cm
        row_height = 0.5*cm

        for i, field_config in enumerate(fields):
            field_name = field_config.get('field_name', '')
            label = field_config.get('label', format_field_label(field_name))

            # Get value from form_data
            value = form_data.get(section_id, {}).get(field_name, '')

            # Skip empty fields
            if value is None or value == '' or value == []:
                continue

            # Determine column
            column = field_config.get('position', {}).get('column', 1)
            x_offset = left_x if column == 1 else right_x

            # Check for page break
            if y < 3*cm:
                c.showPage()
                y = height - 2*cm
                y = render_section_header(c, f"{section_title} - Continued", y)

            # Render field
            y = render_field(c, label, value, y, x_offset=x_offset)

    elif layout == 'three_column':
        # Three column layout
        col_width = 5.5*cm
        col1_x = 2*cm
        col2_x = 7.8*cm
        col3_x = 13.6*cm

        for field_config in fields:
            field_name = field_config.get('field_name', '')
            label = field_config.get('label', format_field_label(field_name))

            # Get value from form_data
            value = form_data.get(section_id, {}).get(field_name, '')

            # Skip empty fields
            if value is None or value == '' or value == []:
                continue

            # Determine column
            column = field_config.get('position', {}).get('column', 1)
            if column == 1:
                x_offset = col1_x
            elif column == 2:
                x_offset = col2_x
            else:
                x_offset = col3_x

            # Check for page break
            if y < 3*cm:
                c.showPage()
                y = height - 2*cm
                y = render_section_header(c, f"{section_title} - Continued", y)

            # Render field
            y = render_field(c, label, value, y, x_offset=x_offset)

    else:
        # Single column layout (default)
        for field_config in fields:
            field_name = field_config.get('field_name', '')
            label = field_config.get('label', format_field_label(field_name))

            # Get value from form_data
            value = form_data.get(section_id, {}).get(field_name, '')

            # Skip empty fields
            if value is None or value == '' or value == []:
                continue

            # Check for page break
            if y < 3*cm:
                c.showPage()
                y = height - 2*cm
                y = render_section_header(c, f"{section_title} - Continued", y)

            # Render field
            y = render_field(c, label, value, y)

    y -= 0.6*cm
    return y


def generate_custom_form_pdf(
    form_data: Dict[str, Any],
    pdf_template: Dict[str, Any],
    form_name: str,
    specialty: str,
    patient: Optional[Dict[str, Any]] = None,
    doctor_info: Optional[Dict[str, Any]] = None
) -> BytesIO:
    """
    Generate a PDF for a custom form using stored pdf_template.

    Args:
        form_data: Filled form data (JSONB from filled_forms table)
        pdf_template: PDF layout template (JSONB from custom_forms table)
        form_name: Name of the form
        specialty: Medical specialty
        patient: Optional patient information
        doctor_info: Optional dict with clinic_name and clinic_logo_url

    Returns:
        BytesIO containing PDF bytes
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Track Y position
    y = height - 2*cm

    # Get page config
    page_config = pdf_template.get('page_config', {})
    header_config = page_config.get('header', {})

    # Render header
    if header_config.get('show_logo') or header_config.get('show_clinic_name'):
        y = render_header(c, y, doctor_info)
    else:
        # Simple header with form title
        c.setFillColor(ANEYA_NAVY)
        c.setFont("Helvetica-Bold", 20)
        form_title = header_config.get('title', format_field_label(form_name))
        c.drawCentredString(width/2, y, form_title)
        y -= 0.5*cm

        # Specialty subtitle
        c.setFillColor(ANEYA_GRAY)
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, y, f"Specialty: {specialty.title()}")
        y -= 0.5*cm

        # Generation date
        c.setFont("Helvetica", 10)
        generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
        c.drawCentredString(width/2, y, f"Generated: {generation_date}")
        y -= 1.5*cm

    # Render patient section if provided
    if patient:
        if y < 8*cm:
            c.showPage()
            y = height - 2*cm

        y = render_patient_section(c, patient, y)

    # Render form sections using template
    sections = pdf_template.get('sections', [])

    for section_config in sections:
        # Check for page break before section
        if section_config.get('page_break_before', False):
            c.showPage()
            y = height - 2*cm

        # Check if need new page
        if y < 8*cm:
            c.showPage()
            y = height - 2*cm

        # Render section
        y = render_custom_form_section(c, section_config, form_data, y)

    # Add footer if configured
    footer_config = page_config.get('footer', {})
    if footer_config.get('show_page_numbers') or footer_config.get('show_timestamp'):
        c.setFillColor(ANEYA_LIGHT_GRAY)
        c.setFont("Helvetica", 8)
        c.drawCentredString(width/2, 1.5*cm, "Aneya Healthcare Platform")
        c.drawCentredString(width/2, 1*cm, "This document is confidential and for medical professionals only")

    c.save()
    buffer.seek(0)
    return buffer
