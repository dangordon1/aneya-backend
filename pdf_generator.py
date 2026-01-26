"""
PDF Generator for Consultation Forms

This module generates PDF reports for consultations, including:
- Appointment details
- Patient information
- Consultation form data (all form types)
- Prescription documents
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from typing import Dict, Any, Optional, List
import requests

# Import design tokens model
from models.design_tokens import DesignTokens

# QR code imports
try:
    import qrcode
    from qrcode.image.pil import PilImage
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    print("⚠️ qrcode library not installed - QR codes will be disabled")




def _flatten_value(value: Any) -> str:
    """
    Recursively flatten any nested objects/dicts into a string.
    Prevents React error #31 (objects not valid as React child).
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        # Flatten each item and join
        return ", ".join(_flatten_value(item) for item in value)
    if isinstance(value, dict):
        # Convert dict to key: value string
        parts = []
        for k, v in value.items():
            flat_v = _flatten_value(v)
            parts.append(f"{k}: {flat_v}")
        return "; ".join(parts)
    return str(value)


def generate_sample_form_data(
    form_schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate realistic sample/dummy data based on form schema for PDF preview.

    Args:
        form_schema: Form schema with sections and field definitions

    Returns:
        Dict with nested structure: {"section_name": {"field_name": "sample value"}}
        All values are guaranteed to be strings to prevent React rendering errors.
    """
    import random

    sample_data = {}

    # Iterate through form schema sections
    for section_name, section_config in form_schema.items():
        if not isinstance(section_config, dict):
            continue

        # Skip metadata sections
        if section_name in ['title', 'description', 'version']:
            continue

        section_data = {}
        fields = section_config.get('fields', [])

        # Handle both list and dict field formats
        if isinstance(fields, dict):
            # Dict format: {"field_name": {config}}
            field_items = [{"name": k, **v} if isinstance(v, dict) else {"name": k, "value": v} for k, v in fields.items()]
        elif isinstance(fields, list):
            # List format: [{"name": "field_name", ...}]
            field_items = fields
        else:
            field_items = []

        # If no 'fields' key, check if section keys are field definitions
        if not field_items and 'fields' not in section_config:
            # Treat section keys as field definitions (skip metadata keys)
            metadata_keys = {'title', 'description', 'type', 'version'}
            field_items = [
                {"name": k, **v} if isinstance(v, dict) else {"name": k, "value": v}
                for k, v in section_config.items()
                if k not in metadata_keys
            ]

        for field in field_items:
            field_name = field.get('name', '')
            field_type = field.get('type', 'string')
            input_type = field.get('input_type', '')

            # Generate sample data based on field type
            if field_type == 'array' and input_type.startswith('table'):
                # Table field - generate 2-3 sample rows
                row_fields = field.get('row_fields', [])
                if row_fields:
                    num_rows = random.choice([2, 3])
                    sample_rows = []

                    for row_idx in range(num_rows):
                        row_data = {}
                        for row_field in row_fields:
                            row_field_name = row_field.get('name', '')
                            row_field_type = row_field.get('type', 'string')

                            # Generate sample value for row field
                            if row_field_type == 'date':
                                # Generate dates in current month
                                day = 15 + row_idx * 7
                                if day > 28:
                                    day = day % 28
                                row_data[row_field_name] = datetime.now().strftime(f'{day:02d}/%m/%Y')
                            elif row_field_type == 'number':
                                # Generate realistic medical numbers
                                if 'weight' in row_field_name.lower() or 'wt' in row_field_name.lower():
                                    row_data[row_field_name] = str(65 + row_idx)
                                elif 'bp' in row_field_name.lower() or 'blood_pressure' in row_field_name.lower():
                                    row_data[row_field_name] = f"{120 - row_idx * 2}/{80 - row_idx * 2}"
                                elif 'temp' in row_field_name.lower() or 'temperature' in row_field_name.lower():
                                    row_data[row_field_name] = f"{37.0 + row_idx * 0.2:.1f}"
                                elif 'height' in row_field_name.lower():
                                    row_data[row_field_name] = str(165 + row_idx)
                                elif 'fhr' in row_field_name.lower() or 'heart_rate' in row_field_name.lower():
                                    row_data[row_field_name] = str(140 + row_idx * 5)
                                elif 'sfh' in row_field_name.lower():
                                    row_data[row_field_name] = str(30 + row_idx)
                                else:
                                    row_data[row_field_name] = str(random.randint(60, 120))
                            elif row_field_type == 'boolean':
                                row_data[row_field_name] = "Yes" if row_idx % 2 == 0 else "No"
                            else:
                                # String or other types
                                if 'scan_type' in row_field_name.lower():
                                    scan_types = ['Dating Scan', 'Anomaly Scan', 'Growth Scan']
                                    row_data[row_field_name] = scan_types[row_idx % len(scan_types)]
                                elif 'complaint' in row_field_name.lower():
                                    row_data[row_field_name] = f"Sample complaint {row_idx + 1}"
                                elif 'diagnosis' in row_field_name.lower():
                                    row_data[row_field_name] = f"Sample diagnosis {row_idx + 1}"
                                elif 'medication' in row_field_name.lower():
                                    row_data[row_field_name] = f"Sample medication {row_idx + 1}"
                                else:
                                    row_data[row_field_name] = f"Sample data {row_idx + 1}"

                        sample_rows.append(row_data)

                    section_data[field_name] = sample_rows

            elif field_type == 'string':
                section_data[field_name] = "Sample text"

            elif field_type == 'number':
                # Generate realistic medical numbers based on field name
                if 'weight' in field_name.lower():
                    section_data[field_name] = "65"
                elif 'height' in field_name.lower():
                    section_data[field_name] = "165"
                elif 'blood_pressure' in field_name.lower() or 'bp' in field_name.lower():
                    section_data[field_name] = "120/80"
                elif 'temperature' in field_name.lower() or 'temp' in field_name.lower():
                    section_data[field_name] = "37.5"
                elif 'pulse' in field_name.lower() or 'heart_rate' in field_name.lower():
                    section_data[field_name] = "72"
                elif 'respiratory_rate' in field_name.lower():
                    section_data[field_name] = "16"
                elif 'oxygen' in field_name.lower() or 'spo2' in field_name.lower():
                    section_data[field_name] = "98"
                else:
                    section_data[field_name] = "120"

            elif field_type == 'date':
                # Current date formatted as DD/MM/YYYY
                section_data[field_name] = datetime.now().strftime('%d/%m/%Y')

            elif field_type == 'boolean':
                # Alternate Yes/No
                section_data[field_name] = "Yes"

            elif field_type == 'select' or input_type == 'radio':
                # Use first option if available
                options = field.get('options', [])
                if options:
                    if isinstance(options[0], dict):
                        section_data[field_name] = options[0].get('value', 'Option 1')
                    else:
                        section_data[field_name] = options[0]
                else:
                    section_data[field_name] = "Option 1"

            elif input_type == 'textarea':
                section_data[field_name] = "Sample longer text content that would typically be entered in a textarea field. This demonstrates how multi-line text appears in the PDF."

            elif field_type == 'object':
                # Object field - generate flat string representation of nested fields
                # This prevents React error #31 (objects not valid as React child)
                nested_fields = field.get('properties', field.get('fields', []))
                if isinstance(nested_fields, list):
                    # Generate sample values for each nested field
                    nested_values = []
                    for nf in nested_fields:
                        nf_name = nf.get('name', nf.get('label', 'field'))
                        nf_type = nf.get('type', 'string')
                        if nf_type == 'date':
                            nested_values.append(f"{nf_name}: {datetime.now().strftime('%d/%m/%Y')}")
                        elif nf_type == 'boolean':
                            nested_values.append(f"{nf_name}: Yes")
                        else:
                            nested_values.append(f"{nf_name}: Sample value")
                    section_data[field_name] = "; ".join(nested_values) if nested_values else "N/A"
                elif isinstance(nested_fields, dict):
                    # Handle dict-style properties
                    nested_values = []
                    for nf_name, nf_config in nested_fields.items():
                        nf_type = nf_config.get('type', 'string') if isinstance(nf_config, dict) else 'string'
                        if nf_type == 'date':
                            nested_values.append(f"{nf_name}: {datetime.now().strftime('%d/%m/%Y')}")
                        elif nf_type == 'boolean':
                            nested_values.append(f"{nf_name}: Yes")
                        else:
                            nested_values.append(f"{nf_name}: Sample value")
                    section_data[field_name] = "; ".join(nested_values) if nested_values else "N/A"
                else:
                    section_data[field_name] = "N/A"

            else:
                # Default to sample text
                section_data[field_name] = "Sample text"

        # Only add section if it has data
        if section_data:
            sample_data[section_name] = section_data

    # Final pass: DEEP flatten everything to ensure no nested objects remain
    # This prevents React error #31 (objects not valid as React child)
    def deep_flatten_data(data: Any, depth: int = 0) -> Any:
        """Recursively ensure all values are React-safe (strings or flat arrays of dicts with string values)."""
        if depth > 10:  # Safety limit
            return str(data)

        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, (int, float, bool)):
            return str(data)
        if isinstance(data, list):
            # For lists, flatten each item
            result = []
            for item in data:
                if isinstance(item, dict):
                    # Flatten all values in the dict
                    result.append({k: _flatten_value(v) for k, v in item.items()})
                else:
                    result.append(_flatten_value(item))
            return result
        if isinstance(data, dict):
            # Check if this looks like section data (dict of field_name: value)
            # If any value is itself a dict (not a list of dicts), flatten it
            result = {}
            for key, val in data.items():
                if isinstance(val, dict):
                    # Nested dict - flatten to string
                    result[key] = _flatten_value(val)
                elif isinstance(val, list):
                    # List - process each item
                    result[key] = deep_flatten_data(val, depth + 1)
                else:
                    result[key] = _flatten_value(val)
            return result
        return str(data)

    # Apply deep flattening to all sections
    flattened_data = {}
    for section_name, section_data in sample_data.items():
        flattened_data[section_name] = deep_flatten_data(section_data)

    # FINAL SAFETY: Absolute last-resort flattening to prevent React error #31
    def ensure_no_nested_objects(data: Any) -> Any:
        """Last-resort flattening - convert ANY remaining nested object to string."""
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, (int, float, bool)):
            return str(data)
        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, dict):
                    # Ensure all values in dict are strings (not nested objects)
                    flat_item = {}
                    for k, v in item.items():
                        if isinstance(v, (dict, list)):
                            flat_item[k] = _flatten_value(v)
                        elif isinstance(v, (int, float, bool)):
                            flat_item[k] = str(v)
                        elif v is None:
                            flat_item[k] = ""
                        else:
                            flat_item[k] = str(v)
                    result.append(flat_item)
                elif isinstance(item, (dict, list)):
                    result.append(_flatten_value(item))
                else:
                    result.append(str(item) if item is not None else "")
            return result
        if isinstance(data, dict):
            result = {}
            for key, val in data.items():
                if isinstance(val, list):
                    result[key] = ensure_no_nested_objects(val)
                elif isinstance(val, dict):
                    # Dict value that's NOT a list - must be flattened to string
                    result[key] = _flatten_value(val)
                elif isinstance(val, (int, float, bool)):
                    result[key] = str(val)
                elif val is None:
                    result[key] = ""
                else:
                    result[key] = str(val)
            return result
        return str(data)

    # Apply the absolute final safety flattening
    safe_data = {}
    for section_name, section_data in flattened_data.items():
        safe_data[section_name] = ensure_no_nested_objects(section_data)

    # Debug: Print flattened data structure to verify
    print(f"   📋 Sample data structure after flattening:")
    for section_name, section_data in safe_data.items():
        if isinstance(section_data, dict):
            for field_name, value in section_data.items():
                val_type = type(value).__name__
                if isinstance(value, list) and value:
                    print(f"      - {section_name}.{field_name}: list[{len(value)}] of {type(value[0]).__name__}")
                elif isinstance(value, dict):
                    print(f"      ⚠️ {section_name}.{field_name}: DICT with keys {list(value.keys())} - THIS SHOULD NOT HAPPEN!")
                else:
                    preview = str(value)[:30] + "..." if len(str(value)) > 30 else str(value)
                    print(f"      - {section_name}.{field_name}: {val_type}")

    return safe_data


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

        # Calculate scaling to fit within 50mm x 20mm (reduced from 70mm x 28mm)
        img_width, img_height = img.getSize()
        max_width, max_height = 5*cm, 2*cm
        scale = min(max_width/img_width, max_height/img_height)

        scaled_width = img_width * scale
        scaled_height = img_height * scale

        # Position in top-right corner with whitespace from top
        x_pos = 19*cm - scaled_width
        y_pos = y - 0.5*cm  # Positioned with proper whitespace from top

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


def render_header(c: canvas.Canvas, y: float, doctor_info: Optional[Dict[str, Any]] = None,
                 tokens: Optional[DesignTokens] = None) -> float:
    """
    Render the PDF header with title, generation date, and optional clinic logo

    Args:
        c: ReportLab canvas
        y: Current Y position
        doctor_info: Optional dict with clinic_name and clinic_logo_url
        tokens: Design tokens for styling

    Returns:
        float: Updated Y position
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()
    typo = tokens.typography
    spacing = tokens.spacing

    width, height = A4

    # Try to render clinic logo if available
    logo_rendered = False
    if doctor_info and doctor_info.get('clinic_logo_url'):
        logo_rendered = render_clinic_logo(c, y, doctor_info['clinic_logo_url'])

    # Fallback to clinic name as text if no logo rendered
    if not logo_rendered and doctor_info and doctor_info.get('clinic_name'):
        c.setFillColor(colors["primary"])
        font_name, font_size = typo.body.to_reportlab_font()
        c.setFont(font_name, font_size + 2)
        c.drawRightString(19*cm, y + 0.5*cm, doctor_info['clinic_name'])

    # Title
    c.setFillColor(colors["primary"])
    font_name, font_size = typo.heading_1.to_reportlab_font()
    c.setFont(font_name, font_size)
    c.drawCentredString(width/2, y, "Consultation Report")
    y -= spacing.field_spacing * cm

    # Generation date
    c.setFillColor(colors["text"])
    font_name, font_size = typo.body.to_reportlab_font()
    c.setFont(font_name, font_size)
    generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
    c.drawCentredString(width/2, y, f"Generated: {generation_date}")
    y -= spacing.section_spacing * cm

    return y


def render_section_header(c: canvas.Canvas, title: str, y: float,
                         tokens: Optional[DesignTokens] = None) -> float:
    """Render a section header"""
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()
    typo = tokens.typography
    spacing = tokens.spacing

    c.setFillColor(colors["primary"])
    font_name, font_size = typo.heading_2.to_reportlab_font()
    c.setFont(font_name, font_size)
    c.drawString(2*cm, y, title)
    y -= 0.2*cm

    # Underline
    c.setStrokeColor(colors["accent"])
    c.setLineWidth(2)
    c.line(2*cm, y, 19*cm, y)
    y -= spacing.section_spacing * cm

    return y


def render_field(c: canvas.Canvas, label: str, value: Any, y: float, x_offset: float = 2*cm,
                tokens: Optional[DesignTokens] = None) -> float:
    """Render a field with label and value"""
    if value is None or value == '' or value == []:
        return y

    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()
    typo = tokens.typography
    spacing = tokens.spacing

    c.setFillColor(colors["primary"])
    font_name, font_size = typo.body_bold.to_reportlab_font()
    c.setFont(font_name, font_size)

    # Calculate label width to ensure enough spacing
    label_text = f"{label}:"
    label_font_name, label_font_size = typo.body_bold.to_reportlab_font()
    label_width = c.stringWidth(label_text, label_font_name, label_font_size)

    # Use dynamic spacing: label width + small gap (0.3cm ~ 1 space)
    value_x_offset = x_offset + label_width + 0.3*cm

    c.drawString(x_offset, y, label_text)

    c.setFillColor(colors["text"])
    value_font_name, value_font_size = typo.body.to_reportlab_font()
    c.setFont(value_font_name, value_font_size)

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
            if c.stringWidth(test_line, value_font_name, value_font_size) <= max_width:
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
            y -= spacing.line_spacing * cm

            # Draw remaining lines
            for line in lines[1:]:
                c.drawString(value_x_offset, y, line)
                y -= spacing.line_spacing * cm
    else:
        c.drawString(value_x_offset, y, value_str)
        y -= spacing.line_spacing * cm

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
        ("Patient Name", patient.get('name', 'Not recorded')),
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


# ============================================================================
# PRESCRIPTION PDF GENERATION
# ============================================================================

def render_qr_code(c: canvas.Canvas, consultation_url: str, x: float, y: float, size: float = 2*cm) -> bool:
    """
    Render a QR code containing the consultation verification URL.

    Args:
        c: ReportLab canvas
        consultation_url: URL to encode in QR code
        x: X position for QR code
        y: Y position for QR code (bottom-left of QR)
        size: Size of QR code (default 2cm)

    Returns:
        bool: True if QR code rendered successfully
    """
    if not HAS_QRCODE:
        print("⚠️ QR code library not available, skipping QR code")
        return False

    if not consultation_url:
        print("⚠️ No consultation URL provided for QR code")
        return False

    try:
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=1,
        )
        qr.add_data(str(consultation_url))  # Ensure string type
        qr.make(fit=True)

        # Create PIL image - use pure PIL mode for better compatibility
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Ensure we have a proper PIL Image
        if hasattr(qr_image, 'get_image'):
            pil_image = qr_image.get_image()
        else:
            pil_image = qr_image

        # Convert to BytesIO for ReportLab
        img_buffer = BytesIO()
        pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        # Draw on canvas
        img = ImageReader(img_buffer)
        c.drawImage(img, x, y, width=size, height=size)

        return True
    except Exception as e:
        print(f"⚠️ Failed to render QR code: {e}")
        import traceback
        traceback.print_exc()
        return False


def render_signature_watermark(
    c: canvas.Canvas,
    doctor_name: str,
    x: float,
    y: float,
    tokens: Optional[DesignTokens] = None
):
    """
    Render doctor's name as a diagonal semi-transparent watermark.

    Args:
        c: ReportLab canvas
        doctor_name: Doctor's name to render
        x: Center X position
        y: Center Y position
        tokens: Design tokens for styling
    """
    if tokens is None:
        tokens = DesignTokens.default()

    # Ensure doctor_name is a valid string
    if not doctor_name:
        doctor_name = "Doctor"
    doctor_name = str(doctor_name)

    c.saveState()

    # Set up semi-transparent watermark
    c.translate(x, y)
    c.rotate(45)  # 45 degree diagonal

    # Use primary color with transparency (approximate with lighter version)
    # ReportLab doesn't support true alpha, so we use a light tint
    watermark_color = HexColor("#B8C6D1")  # Light version of primary
    c.setFillColor(watermark_color)
    c.setFont("Helvetica-Bold", 24)

    # Draw centered text
    c.drawCentredString(0, 0, doctor_name)

    c.restoreState()


def render_prescription_header(
    c: canvas.Canvas,
    y: float,
    doctor_info: Dict[str, Any],
    consultation_date: str,
    tokens: Optional[DesignTokens] = None
) -> float:
    """
    Render prescription header with clinic branding and date.

    Args:
        c: ReportLab canvas
        y: Current Y position
        doctor_info: Doctor information including clinic details
        consultation_date: Date of consultation
        tokens: Design tokens for styling

    Returns:
        float: Updated Y position
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()
    typo = tokens.typography

    width, height = A4

    # Try to render clinic logo if available
    logo_rendered = False
    if doctor_info.get('clinic_logo_url'):
        logo_rendered = render_clinic_logo(c, y, doctor_info['clinic_logo_url'])

    # Clinic name (left side)
    clinic_name = doctor_info.get('clinic_name') or 'Medical Clinic'
    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, y, str(clinic_name))
    y -= 0.6*cm

    # Clinic address if available
    if doctor_info.get('clinic_address'):
        c.setFillColor(colors["text"])
        c.setFont("Helvetica", 9)
        c.drawString(2*cm, y, str(doctor_info['clinic_address']))
        y -= 0.4*cm

    # Doctor name and credentials
    doctor_name = doctor_info.get('name') or 'Doctor'
    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2*cm, y, f"Dr. {doctor_name}")

    # Date on right side
    c.setFillColor(colors["text"])
    c.setFont("Helvetica", 10)
    c.drawRightString(19*cm, y, f"Date: {consultation_date}")
    y -= 0.4*cm

    # Qualifications if available
    if doctor_info.get('qualifications'):
        c.setFont("Helvetica", 9)
        c.setFillColor(colors["text"])
        c.drawString(2*cm, y, str(doctor_info['qualifications']))
        y -= 0.4*cm

    # Registration number if available
    if doctor_info.get('license_number'):
        c.setFont("Helvetica", 9)
        c.setFillColor(colors["text"])
        c.drawString(2*cm, y, f"Reg. No: {str(doctor_info['license_number'])}")
        y -= 0.4*cm

    y -= 0.4*cm

    # Draw divider line
    c.setStrokeColor(colors["accent"])
    c.setLineWidth(2)
    c.line(2*cm, y, 19*cm, y)
    y -= 0.8*cm

    return y


def render_prescription_patient_info(
    c: canvas.Canvas,
    y: float,
    patient: Dict[str, Any],
    tokens: Optional[DesignTokens] = None
) -> float:
    """
    Render patient information section on prescription.

    Args:
        c: ReportLab canvas
        y: Current Y position
        patient: Patient information
        tokens: Design tokens for styling

    Returns:
        float: Updated Y position
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()

    # Patient name
    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2*cm, y, "Patient:")

    c.setFillColor(colors["text"])
    c.setFont("Helvetica", 11)
    patient_name = patient.get('name') or 'Unknown'
    c.drawString(4.5*cm, y, str(patient_name))

    # Patient ID on right side if available
    if patient.get('id'):
        c.setFont("Helvetica", 10)
        c.drawRightString(19*cm, y, f"ID: {str(patient['id'])[:8]}...")

    y -= 0.5*cm

    # Age and sex on same line
    patient_details = []
    if patient.get('age_years') or patient.get('date_of_birth'):
        age = patient.get('age_years')
        if not age and patient.get('date_of_birth'):
            try:
                dob_str = patient['date_of_birth']
                if 'T' in dob_str:
                    dob_str = dob_str.split('T')[0]
                dob = datetime.strptime(dob_str, '%Y-%m-%d')
                age = (datetime.now() - dob).days // 365
            except:
                pass
        if age:
            patient_details.append(f"Age: {age} years")

    if patient.get('sex'):
        patient_details.append(f"Sex: {patient['sex']}")

    if patient_details:
        c.setFont("Helvetica", 10)
        c.drawString(2*cm, y, " | ".join(patient_details))
        y -= 0.5*cm

    y -= 0.3*cm

    return y


def render_rx_symbol(c: canvas.Canvas, x: float, y: float, tokens: Optional[DesignTokens] = None):
    """
    Render the Rx prescription symbol.

    Args:
        c: ReportLab canvas
        x: X position
        y: Y position
        tokens: Design tokens for styling
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()

    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 28)
    c.drawString(x, y, "Rx")


def render_medications_table(
    c: canvas.Canvas,
    y: float,
    prescriptions: List[Dict[str, Any]],
    tokens: Optional[DesignTokens] = None
) -> float:
    """
    Render medications in a structured table format.

    Args:
        c: ReportLab canvas
        y: Current Y position
        prescriptions: List of prescription dictionaries
        tokens: Design tokens for styling

    Returns:
        float: Updated Y position
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()

    width, height = A4

    # Rx symbol
    render_rx_symbol(c, 2*cm, y - 0.3*cm, tokens)
    y -= 1.2*cm

    if not prescriptions:
        c.setFillColor(colors["text"])
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(2*cm, y, "No medications prescribed")
        return y - 1*cm

    # Column definitions
    col_x = {
        'num': 2*cm,
        'drug': 2.8*cm,
        'qty': 10*cm,
        'dose': 12*cm,
    }

    # Table header (subtle)
    c.setFillColor(colors["text_light"])
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_x['drug'], y, "Medication")
    c.drawString(col_x['qty'], y, "Qty")
    c.drawString(col_x['dose'], y, "Dosage Instructions")
    y -= 0.5*cm

    # Draw header line
    c.setStrokeColor(colors["text_light"])
    c.setLineWidth(0.5)
    c.line(2*cm, y + 0.15*cm, 19*cm, y + 0.15*cm)

    # Render each medication
    for idx, med in enumerate(prescriptions, 1):
        drug_name = med.get('drug_name') or 'Unknown medication'
        amount = med.get('amount') or ''
        method = med.get('method') or ''
        frequency = med.get('frequency') or ''
        duration = med.get('duration') or ''

        # Check for page break
        if y < 4*cm:
            c.showPage()
            y = height - 2*cm
            # Re-render Rx symbol on new page
            render_rx_symbol(c, 2*cm, y - 0.3*cm, tokens)
            y -= 1.5*cm

        # Medication number
        c.setFillColor(colors["primary"])
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col_x['num'], y, f"{idx}.")

        # Drug name (bold)
        c.setFillColor(colors["primary"])
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col_x['drug'], y, str(drug_name))

        # Quantity
        if amount:
            c.setFillColor(colors["text"])
            c.setFont("Helvetica", 10)
            c.drawString(col_x['qty'], y, str(amount))

        y -= 0.5*cm

        # Dosage instructions (second line, indented)
        dosage_parts = []
        if method:
            dosage_parts.append(method)
        if frequency:
            dosage_parts.append(frequency)
        if duration:
            dosage_parts.append(f"for {duration}")

        if dosage_parts:
            c.setFillColor(colors["text"])
            c.setFont("Helvetica", 10)
            dosage_text = " - ".join(dosage_parts)
            c.drawString(col_x['drug'], y, dosage_text)
            y -= 0.5*cm

        y -= 0.3*cm  # Extra spacing between medications

    return y


def render_prescription_footer(
    c: canvas.Canvas,
    doctor_info: Dict[str, Any],
    consultation_id: str,
    tokens: Optional[DesignTokens] = None
):
    """
    Render prescription footer with signature area, QR code, and clinic info.

    Args:
        c: ReportLab canvas
        doctor_info: Doctor information
        consultation_id: Consultation ID for QR code
        tokens: Design tokens for styling
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()

    width, height = A4

    # Signature area (right side)
    sig_x = 13*cm
    sig_y = 5*cm

    # Render signature watermark
    doctor_name = doctor_info.get('name') or 'Doctor'
    render_signature_watermark(c, f"Dr. {doctor_name}", sig_x + 3*cm, sig_y + 1*cm, tokens)

    # Signature line
    c.setStrokeColor(colors["text_light"])
    c.setLineWidth(1)
    c.line(sig_x, sig_y - 0.5*cm, 19*cm, sig_y - 0.5*cm)

    # Doctor credentials below signature line
    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(sig_x + 3*cm, sig_y - 1*cm, f"Dr. {doctor_name}")

    if doctor_info.get('qualifications'):
        c.setFillColor(colors["text"])
        c.setFont("Helvetica", 9)
        c.drawCentredString(sig_x + 3*cm, sig_y - 1.4*cm, str(doctor_info['qualifications']))

    if doctor_info.get('license_number'):
        c.setFont("Helvetica", 9)
        c.drawCentredString(sig_x + 3*cm, sig_y - 1.8*cm, f"Reg. No: {str(doctor_info['license_number'])}")

    # QR code (left side)
    qr_url = f"https://aneya.health/consultations/{consultation_id}"
    qr_rendered = render_qr_code(c, qr_url, 2*cm, 3.5*cm, size=2.2*cm)

    if qr_rendered:
        c.setFillColor(colors["text"])
        c.setFont("Helvetica", 7)
        c.drawString(2*cm, 3.2*cm, "Scan to verify")

    # Footer line
    c.setStrokeColor(colors["text_light"])
    c.setLineWidth(0.5)
    c.line(2*cm, 2.5*cm, 19*cm, 2.5*cm)

    # Clinic contact info in footer
    c.setFillColor(colors["text"])
    c.setFont("Helvetica", 8)

    footer_parts = []
    if doctor_info.get('clinic_name'):
        footer_parts.append(str(doctor_info['clinic_name']))
    if doctor_info.get('clinic_address'):
        footer_parts.append(str(doctor_info['clinic_address']))
    if doctor_info.get('clinic_phone'):
        footer_parts.append(f"Tel: {str(doctor_info['clinic_phone'])}")

    if footer_parts:
        footer_text = " | ".join(footer_parts)
        # Truncate if too long
        if len(footer_text) > 100:
            footer_text = footer_text[:97] + "..."
        c.drawCentredString(width/2, 2*cm, footer_text)

    # Generated by Aneya
    c.setFillColor(colors["text_light"])
    c.setFont("Helvetica", 7)
    c.drawCentredString(width/2, 1.5*cm, "Generated by Aneya Healthcare Platform")


def generate_prescription_pdf(
    prescriptions: List[Dict[str, Any]],
    patient: Dict[str, Any],
    doctor_info: Dict[str, Any],
    consultation_id: str,
    consultation_date: str,
    tokens: Optional[DesignTokens] = None
) -> BytesIO:
    """
    Generate a prescription PDF document.

    Args:
        prescriptions: List of prescription dicts with drug_name, amount, method, frequency, duration
        patient: Patient information dict with name, id, age_years/date_of_birth, sex
        doctor_info: Doctor information dict with name, qualifications, license_number,
                     clinic_name, clinic_logo_url, clinic_address, clinic_phone
        consultation_id: UUID of the consultation for QR code verification
        consultation_date: Date of consultation (DD/MM/YYYY format)
        tokens: Optional design tokens for styling

    Returns:
        BytesIO containing PDF bytes
    """
    if tokens is None:
        tokens = DesignTokens.default()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Start Y position
    y = height - 2*cm

    # Render header with clinic branding
    try:
        print("  [PDF] Rendering header...")
        y = render_prescription_header(c, y, doctor_info, consultation_date, tokens)
        print("  [PDF] Header done")
    except Exception as e:
        print(f"  [PDF] ❌ Header failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Render patient info
    try:
        print("  [PDF] Rendering patient info...")
        y = render_prescription_patient_info(c, y, patient, tokens)
        print("  [PDF] Patient info done")
    except Exception as e:
        print(f"  [PDF] ❌ Patient info failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Render medications table
    try:
        print("  [PDF] Rendering medications table...")
        y = render_medications_table(c, y, prescriptions, tokens)
        print("  [PDF] Medications table done")
    except Exception as e:
        print(f"  [PDF] ❌ Medications table failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Render footer with signature and QR code
    try:
        print("  [PDF] Rendering footer...")
        render_prescription_footer(c, doctor_info, consultation_id, tokens)
        print("  [PDF] Footer done")
    except Exception as e:
        print(f"  [PDF] ❌ Footer failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    c.save()
    buffer.seek(0)

    print(f"✅ Prescription PDF generated for {len(prescriptions)} medications")
    return buffer
