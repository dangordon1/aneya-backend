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




def generate_sample_form_data(
    form_schema: Dict[str, Any],
    pdf_template: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate realistic sample/dummy data based on form schema for PDF preview.

    Args:
        form_schema: Form schema with sections and field definitions
        pdf_template: PDF template configuration

    Returns:
        Dict with nested structure: {"section_name": {"field_name": "sample value"}}
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

        for field in fields:
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

            else:
                # Default to sample text
                section_data[field_name] = "Sample text"

        # Only add section if it has data
        if section_data:
            sample_data[section_name] = section_data

    return sample_data


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


def render_table_field(
    c: canvas.Canvas,
    section_id: str,
    field_name: str,
    label: str,
    schema_field: Dict[str, Any],
    form_data: Dict[str, Any],
    y: float,
    tokens: Optional[DesignTokens] = None
) -> float:
    """
    Render a table/array field with headers and rows.
    Handles landscape orientation and column wrapping automatically.

    Args:
        c: ReportLab canvas
        section_id: Section ID
        field_name: Field name
        label: Field label for display
        schema_field: Field schema definition
        form_data: Form data
        y: Current Y position
        tokens: Design tokens for styling

    Returns:
        Updated Y position
    """
    if tokens is None:
        tokens = DesignTokens.default()

    colors_dict = tokens.colors.to_hex_colors()
    typo = tokens.typography
    spacing = tokens.spacing

    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape

    width, height = A4

    # Get row_fields from schema
    row_fields = schema_field.get('row_fields', [])
    if not row_fields:
        # No row fields defined, skip table
        return y

    # Check if this is a transposed table with row headers
    is_transposed = schema_field.get('input_type', '').endswith('transposed')
    row_names = schema_field.get('row_names', [])

    if is_transposed and row_names:
        # Transposed table: rows are field names, columns are scan types
        # We'll build column headers after we know how many scans we have
        column_names = ['']  # Start with empty cell for row header column

        # Initial col_widths estimate (will be recalculated later based on actual scan count)
        # Assume 3 scans for initial landscape check
        col_widths = [3.5*cm, 2.2*cm, 2.2*cm, 2.2*cm]
    else:
        # Regular table: columns are field names
        column_names = [rf.get('label', rf.get('name', '')) for rf in row_fields]

        # Calculate column widths based on field types
        col_types = {rf.get('label', rf.get('name', '')): rf.get('type', 'string') for rf in row_fields}
        col_widths = []

        for col_name in column_names:
            if col_types.get(col_name) == 'boolean':
                col_widths.append(0.9*cm)
            elif col_types.get(col_name) == 'number' or 'No.' in col_name or 'Year' in col_name or 'Wt' in col_name or 'SFH' in col_name or 'FHR' in col_name:
                col_widths.append(1.2*cm)
            elif 'Date' in col_name:
                col_widths.append(1.6*cm)
            else:
                col_widths.append(2.2*cm)  # text default (reduced from 2.5cm)

    # Calculate total table width
    total_table_width = sum(col_widths)
    portrait_available = width - 4*cm  # ~17cm for A4 portrait
    landscape_available = landscape(A4)[0] - 2*cm  # ~27.7cm for A4 landscape (reduced margins)

    # Determine if we need landscape orientation (will be rechecked for transposed tables)
    needs_landscape = total_table_width > portrait_available

    # Check if we need to split the table (too wide even for landscape)
    needs_split = not is_transposed and total_table_width > landscape_available

    # Debug logging
    print(f"📊 Table: {label}")
    print(f"   Total width: {total_table_width/cm:.2f}cm ({len(col_widths)} columns)")
    print(f"   Portrait available: {portrait_available/cm:.2f}cm")
    print(f"   Landscape available: {landscape_available/cm:.2f}cm")
    print(f"   Needs landscape: {needs_landscape}")
    print(f"   Needs split: {needs_split}")
    print(f"   Is transposed: {is_transposed}")

    if not is_transposed:  # Only switch now for regular tables
        if needs_landscape or needs_split:
            # Always create a new page for landscape tables
            # (ReportLab cannot change page size of current page retroactively)
            current_y = y
            print(f"   Current y: {current_y/cm:.2f}cm, Page height: {A4[1]/cm:.2f}cm")
            print(f"   → Switching to landscape (new page)")

            c.showPage()
            c.setPageSize(landscape(A4))
            width, height = landscape(A4)
            y = height - 2*cm
            available_width = landscape_available
            print(f"   Page size after switch: {c._pagesize[0]/cm:.2f}cm x {c._pagesize[1]/cm:.2f}cm")
        else:
            # Check for page break in portrait
            if y < 8*cm:
                c.showPage()
                y = height - 2*cm
            available_width = portrait_available

    # Table title (skip if splitting, as each chunk will have its own title)
    if not needs_split:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors_dict["primary"])
        left_margin = 1*cm if needs_landscape else 2*cm
        c.drawString(left_margin, y, f"• {label}")
        y -= 0.6*cm

    # Get table data from form_data
    table_data_raw = form_data.get(section_id, {}).get(field_name, [])
    if not isinstance(table_data_raw, list):
        table_data_raw = []

    # Create paragraph styles for wrapping
    header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8,
        alignment=1  # Center
    )

    cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=7,
        leading=8,
        alignment=0  # Left
    )

    # Build table data for PDF
    table_data = []

    if is_transposed and row_names:
        # Transposed table: each row is a field, each column is a scan instance
        # Limit to 5 scans (columns) if data exists, otherwise 3 empty columns
        num_scans = min(len(table_data_raw), 5) if table_data_raw else 3

        # Build column headers from scan data (scan_type field)
        for i in range(num_scans):
            if table_data_raw and i < len(table_data_raw):
                scan_type = table_data_raw[i].get('scan_type', f'Scan {i+1}')
                column_names.append(scan_type)
            else:
                column_names.append(f'Scan {i+1}')

        # Recalculate column widths based on actual number of scans
        col_widths = [3.5*cm] + [2.2*cm] * num_scans
        total_table_width = sum(col_widths)
        needs_landscape = total_table_width > portrait_available

        # Re-check landscape if we recalculated
        if needs_landscape and c.pagesize == A4:  # Not already in landscape
            c.showPage()
            c.setPageSize(landscape(A4))
            width, height = landscape(A4)
            y = height - 2*cm
            available_width = landscape_available
        elif not needs_landscape:
            if y < 8*cm:
                c.showPage()
                y = height - 2*cm
            available_width = portrait_available

    # Header row with Paragraph wrapping for multi-word headers
    header_paragraphs = [Paragraph(col if col else '', header_style) for col in column_names]
    table_data.append(header_paragraphs)

    if is_transposed and row_names:

        # Build rows for each field (from row_names)
        for row_label in row_names:
            # Find the corresponding field in row_fields
            field_def = None
            for rf in row_fields:
                if rf.get('label', '') == row_label or rf.get('name', '') == row_label.lower().replace('/', '_').replace(' ', '_'):
                    field_def = rf
                    break

            # Start with row header
            row_data = [Paragraph(row_label, ParagraphStyle('RowHeader', fontName='Helvetica-Bold', fontSize=7, leading=8))]

            # Add data for each scan instance
            if table_data_raw and field_def:
                field_name_key = field_def.get('name', '')
                for scan_idx in range(num_scans):
                    if scan_idx < len(table_data_raw):
                        value = table_data_raw[scan_idx].get(field_name_key, '')
                        if value:
                            # Wrap text in Paragraph for proper cell wrapping
                            row_data.append(Paragraph(str(value), cell_style))
                        else:
                            row_data.append('')
                    else:
                        row_data.append('')
            else:
                # Empty columns
                row_data.extend([''] * num_scans)

            table_data.append(row_data)
    else:
        # Regular table: each row is a record
        # Data rows (limit to 10 rows if filled, show 3 empty rows if empty)
        if table_data_raw:
            for row in table_data_raw[:10]:  # Limit to 10 rows
                row_values = []
                for rf in row_fields:
                    field_name_in_row = rf.get('name', '')
                    value = row.get(field_name_in_row, '')
                    if value is None or value == '':
                        row_values.append('')
                    else:
                        # Wrap text in Paragraph for proper cell wrapping
                        row_values.append(Paragraph(str(value), cell_style))
                table_data.append(row_values)
        else:
            # Show 3 empty rows as template
            for i in range(3):
                table_data.append([''] * len(column_names))

    # Handle table splitting if needed
    if needs_split:
        # Split table into multiple landscape tables
        # Always include first column (usually Date) in each split

        # Calculate how many columns can fit per table
        first_col_width = col_widths[0]
        remaining_space = available_width - first_col_width

        # Group remaining columns into chunks that fit
        column_chunks = [[0]]  # Always start with column 0 (Date)
        current_chunk = []
        current_width = 0

        for i in range(1, len(col_widths)):
            if current_width + col_widths[i] <= remaining_space:
                current_chunk.append(i)
                current_width += col_widths[i]
            else:
                # Start new chunk
                if current_chunk:
                    column_chunks.append(current_chunk)
                current_chunk = [i]
                current_width = col_widths[i]

        # Add last chunk
        if current_chunk:
            column_chunks.append(current_chunk)

        # Render each chunk as a separate table
        for chunk_idx, chunk in enumerate(column_chunks):
            if chunk_idx > 0:  # Not the first chunk
                # Add first column to this chunk
                chunk_cols = [0] + chunk
            else:
                chunk_cols = chunk

            # Build table for this chunk
            chunk_table_data = []

            # Header row
            chunk_headers = [table_data[0][col_idx] for col_idx in chunk_cols]
            chunk_table_data.append(chunk_headers)

            # Data rows
            for row_idx in range(1, len(table_data)):
                chunk_row = [table_data[row_idx][col_idx] for col_idx in chunk_cols]
                chunk_table_data.append(chunk_row)

            # Column widths for this chunk
            chunk_widths = [col_widths[col_idx] for col_idx in chunk_cols]

            # Render table title (with part indicator for continuation, 1cm margin for landscape)
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(colors_dict["primary"])
            if chunk_idx > 0:
                c.drawString(1*cm, y, f"• {label} (continued - Part {chunk_idx + 1})")
            else:
                c.drawString(1*cm, y, f"• {label} (Part 1 of {len(column_chunks)})")
            y -= 0.6*cm

            # Create and render table
            row_heights = [None] * len(chunk_table_data)
            row_heights[0] = 0.8*cm

            pdf_table = Table(chunk_table_data, colWidths=chunk_widths, rowHeights=row_heights)

            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors_dict["text_light"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors_dict["primary"]),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors_dict["background_light"]]),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
            pdf_table.setStyle(TableStyle(table_style))

            # Draw table (use 1cm margin for landscape)
            table_width, table_height = pdf_table.wrap(available_width, height)
            pdf_table.drawOn(c, 1*cm, y - table_height)
            y -= (table_height + 0.5*cm)

            # New page for next chunk (except last)
            if chunk_idx < len(column_chunks) - 1:
                c.showPage()
                c.setPageSize(landscape(A4))
                width, height = landscape(A4)
                y = height - 2*cm

        # Return -1 to force page break; next page will be portrait
        return -1

    # Single table (no splitting needed)
    # Scale column widths if still too wide (shouldn't happen but just in case)
    if total_table_width > available_width:
        scale_factor = available_width / total_table_width
        col_widths = [w * scale_factor for w in col_widths]

    # Create table
    row_heights = [None] * len(table_data)
    row_heights[0] = 0.8*cm  # Taller header for wrapped text

    pdf_table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)

    # Base table style
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors_dict["text_light"]),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors_dict["primary"]),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors_dict["background_light"]]),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]

    # Additional styling for transposed tables with row headers
    if is_transposed and row_names:
        table_style.extend([
            ('BACKGROUND', (0, 1), (0, -1), colors_dict["text_light"]),  # Row header column background
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),  # Row header column bold
            ('FONTSIZE', (0, 1), (0, -1), 7),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Row headers left-aligned
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Data cells centered
        ])

    pdf_table.setStyle(TableStyle(table_style))

    # Draw table (use 1cm margin for landscape, 2cm for portrait)
    table_width, table_height = pdf_table.wrap(available_width, height)
    left_margin = 1*cm if needs_landscape else 2*cm
    pdf_table.drawOn(c, left_margin, y - table_height)
    y -= (table_height + 0.5*cm)

    # Return to portrait for next content if we were in landscape
    if needs_landscape:
        # Don't switch page size yet - wait until next page is created
        # Return negative y to force page break on next content
        return -1

    return y


def render_custom_form_section(
    c: canvas.Canvas,
    section_config: Dict[str, Any],
    form_data: Dict[str, Any],
    y: float,
    form_schema: Optional[Dict[str, Any]] = None,
    tokens: Optional[DesignTokens] = None
) -> float:
    """
    Render a custom form section using pdf_template configuration.

    Args:
        c: ReportLab canvas
        section_config: PDF template section configuration
        form_data: Actual form data (JSONB)
        y: Current Y position
        form_schema: Optional form schema for table field rendering
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

    # Get section ID and title
    section_id = section_config.get('id', '')
    section_title = section_config.get('title', format_field_label(section_id))
    layout = section_config.get('layout', 'single_column')

    # Check for orphaned section header (need at least 3cm for header + content)
    if y < 3*cm:
        c.showPage()
        y = height - 2*cm

    # Render section header
    y = render_section_header(c, section_title, y, tokens=tokens)

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

            # Check if this is a table field by looking it up in schema
            schema_field = None
            if form_schema:
                for schema_section_name, schema_section_data in form_schema.items():
                    if isinstance(schema_section_data, dict) and 'fields' in schema_section_data:
                        for f in schema_section_data['fields']:
                            if f.get('name') == field_name:
                                schema_field = f
                                break
                    if schema_field:
                        break

            is_table = schema_field and schema_field.get('type') == 'array' and schema_field.get('input_type', '').startswith('table')

            if is_table:
                # Render table field (spans full width, ignores columns)
                y = render_table_field(c, section_id, field_name, label, schema_field, form_data, y, tokens=tokens)

                # Check if table was landscape (returns -1 to force page break)
                if y < 0:
                    c.showPage()
                    c.setPageSize(A4)  # Switch back to portrait
                    y = height - 2*cm
            else:
                # Regular field - get value from form_data
                value = form_data.get(section_id, {}).get(field_name, '')

                # Convert None to empty string for display
                if value is None:
                    value = ''

                # Determine column
                column = field_config.get('position', {}).get('column', 1)
                x_offset = left_x if column == 1 else right_x

                # Check for page break
                if y < 3*cm:
                    c.showPage()
                    y = height - 2*cm
                    y = render_section_header(c, f"{section_title} - Continued", y, tokens=tokens)

                # Render field
                y = render_field(c, label, value, y, x_offset=x_offset, tokens=tokens)

    elif layout == 'three_column':
        # Three column layout
        col_width = 5.5*cm
        col1_x = 2*cm
        col2_x = 7.8*cm
        col3_x = 13.6*cm

        for field_config in fields:
            field_name = field_config.get('field_name', '')
            label = field_config.get('label', format_field_label(field_name))

            # Check if this is a table field by looking it up in schema
            schema_field = None
            if form_schema:
                for schema_section_name, schema_section_data in form_schema.items():
                    if isinstance(schema_section_data, dict) and 'fields' in schema_section_data:
                        for f in schema_section_data['fields']:
                            if f.get('name') == field_name:
                                schema_field = f
                                break
                    if schema_field:
                        break

            is_table = schema_field and schema_field.get('type') == 'array' and schema_field.get('input_type', '').startswith('table')

            if is_table:
                # Render table field (spans full width, ignores columns)
                y = render_table_field(c, section_id, field_name, label, schema_field, form_data, y, tokens=tokens)

                # Check if table was landscape (returns -1 to force page break)
                if y < 0:
                    c.showPage()
                    c.setPageSize(A4)  # Switch back to portrait
                    y = height - 2*cm
            else:
                # Regular field - get value from form_data
                value = form_data.get(section_id, {}).get(field_name, '')

                # Convert None to empty string for display
                if value is None:
                    value = ''

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
                    y = render_section_header(c, f"{section_title} - Continued", y, tokens=tokens)

                # Render field
                y = render_field(c, label, value, y, x_offset=x_offset, tokens=tokens)

    else:
        # Single column layout (default)
        for field_config in fields:
            field_name = field_config.get('field_name', '')
            label = field_config.get('label', format_field_label(field_name))

            # Check if this is a table field by looking it up in schema
            schema_field = None
            if form_schema:
                for schema_section_name, schema_section_data in form_schema.items():
                    if isinstance(schema_section_data, dict) and 'fields' in schema_section_data:
                        for f in schema_section_data['fields']:
                            if f.get('name') == field_name:
                                schema_field = f
                                break
                    if schema_field:
                        break

            is_table = schema_field and schema_field.get('type') == 'array' and schema_field.get('input_type', '').startswith('table')

            if is_table:
                # Render table field with headers and rows
                y = render_table_field(c, section_id, field_name, label, schema_field, form_data, y,
                                      tokens=tokens)

                # Check if table was landscape (returns -1 to force page break)
                if y < 0:
                    c.showPage()
                    c.setPageSize(A4)  # Switch back to portrait
                    y = height - 2*cm
            else:
                # Regular field
                # Get value from form_data
                value = form_data.get(section_id, {}).get(field_name, '')

                # Convert None to empty string for display
                if value is None:
                    value = ''

                # Check for page break
                if y < 3*cm:
                    c.showPage()
                    y = height - 2*cm
                    y = render_section_header(c, f"{section_title} - Continued", y, tokens=tokens)

                # Render field
                y = render_field(c, label, value, y, tokens=tokens)

    y -= 0.6*cm
    return y


def generate_custom_form_pdf(
    form_data: Dict[str, Any],
    pdf_template: Dict[str, Any],
    form_name: str,
    specialty: str,
    patient: Optional[Dict[str, Any]] = None,
    doctor_info: Optional[Dict[str, Any]] = None,
    form_schema: Optional[Dict[str, Any]] = None,
    tokens: Optional[DesignTokens] = None
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
        form_schema: Optional form schema for table rendering
        tokens: Optional DesignTokens for styling (falls back to Aneya defaults)

    Returns:
        BytesIO containing PDF bytes
    """
    # Use provided tokens or default to Aneya styling
    if tokens is None:
        tokens = DesignTokens.default()

    colors = tokens.colors.to_hex_colors()
    typo = tokens.typography
    spacing = tokens.spacing

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
        y = render_header(c, y, doctor_info, tokens=tokens)
    else:
        # Simple header with form title
        c.setFillColor(colors["primary"])
        font_name, font_size = typo.heading_1.to_reportlab_font()
        c.setFont(font_name, font_size)
        form_title = header_config.get('title', format_field_label(form_name))
        c.drawCentredString(width/2, y, form_title)
        y -= spacing.field_spacing * cm

        # Specialty subtitle
        c.setFillColor(colors["text"])
        font_name, font_size = typo.body.to_reportlab_font()
        c.setFont(font_name, font_size + 2)  # Slightly larger for subtitle
        c.drawCentredString(width/2, y, f"Specialty: {specialty.title()}")
        y -= spacing.field_spacing * cm

        # Generation date
        font_name, font_size = typo.body.to_reportlab_font()
        c.setFont(font_name, font_size)
        generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
        c.drawCentredString(width/2, y, f"Generated: {generation_date}")
        y -= spacing.section_spacing * cm

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
        y = render_custom_form_section(c, section_config, form_data, y, form_schema, tokens=tokens)

    # Add footer if configured
    footer_config = page_config.get('footer', {})
    if footer_config.get('show_page_numbers') or footer_config.get('show_timestamp'):
        c.setFillColor(colors["text_light"])
        font_name, font_size = typo.caption.to_reportlab_font()
        c.setFont(font_name, font_size)
        c.drawCentredString(width/2, 1.5*cm, "Aneya Healthcare Platform")
        c.drawCentredString(width/2, 1*cm, "This document is confidential and for medical professionals only")

    c.save()
    buffer.seek(0)
    return buffer


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
    clinic_name = doctor_info.get('clinic_name', 'Medical Clinic')
    c.setFillColor(colors["primary"])
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, y, clinic_name)
    y -= 0.6*cm

    # Clinic address if available
    if doctor_info.get('clinic_address'):
        c.setFillColor(colors["text"])
        c.setFont("Helvetica", 9)
        c.drawString(2*cm, y, doctor_info['clinic_address'])
        y -= 0.4*cm

    # Doctor name and credentials
    doctor_name = doctor_info.get('name', 'Doctor')
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
        c.drawString(2*cm, y, doctor_info['qualifications'])
        y -= 0.4*cm

    # Registration number if available
    if doctor_info.get('license_number'):
        c.setFont("Helvetica", 9)
        c.setFillColor(colors["text"])
        c.drawString(2*cm, y, f"Reg. No: {doctor_info['license_number']}")
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
    patient_name = patient.get('name', 'Unknown')
    c.drawString(4.5*cm, y, patient_name)

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
        drug_name = med.get('drug_name', 'Unknown medication')
        amount = med.get('amount', '')
        method = med.get('method', '')
        frequency = med.get('frequency', '')
        duration = med.get('duration', '')

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
        c.drawString(col_x['drug'], y, drug_name)

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
    doctor_name = doctor_info.get('name', 'Doctor')
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
        c.drawCentredString(sig_x + 3*cm, sig_y - 1.4*cm, doctor_info['qualifications'])

    if doctor_info.get('license_number'):
        c.setFont("Helvetica", 9)
        c.drawCentredString(sig_x + 3*cm, sig_y - 1.8*cm, f"Reg. No: {doctor_info['license_number']}")

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
        footer_parts.append(doctor_info['clinic_name'])
    if doctor_info.get('clinic_address'):
        footer_parts.append(doctor_info['clinic_address'])
    if doctor_info.get('clinic_phone'):
        footer_parts.append(f"Tel: {doctor_info['clinic_phone']}")

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
