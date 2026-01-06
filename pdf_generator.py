"""
PDF Generator for Consultation Forms

This module generates beautiful, modern PDF reports for consultations, including:
- Appointment details
- Patient information
- Consultation form data (all form types)

Design Philosophy:
- Modern, minimalist aesthetic with medical professionalism
- AI-forward design language with clean geometric elements
- Strong visual hierarchy for enhanced readability
- Trust-building color palette (deep blues, soft teals)
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from typing import Dict, Any, Optional
import requests


# ═══════════════════════════════════════════════════════════════════════════════
# MODERN COLOR PALETTE - "AI Medical" Theme
# ═══════════════════════════════════════════════════════════════════════════════

# Primary colors - Deep, trustworthy navy with modern undertones
ANEYA_NAVY = HexColor('#0f172a')           # Deep slate navy (headers, titles)
ANEYA_NAVY_LIGHT = HexColor('#1e3a5f')     # Lighter navy (section backgrounds)

# Accent colors - Modern teal/cyan for a futuristic medical feel
ANEYA_TEAL = HexColor('#0d9488')           # Primary teal (accents, highlights)
ANEYA_TEAL_LIGHT = HexColor('#5eead4')     # Light teal (subtle accents)
ANEYA_CYAN = HexColor('#22d3ee')           # Bright cyan (special highlights)

# Text colors - Warm grays for better readability
ANEYA_GRAY = HexColor('#374151')           # Primary text (dark gray)
ANEYA_GRAY_MEDIUM = HexColor('#6b7280')    # Secondary text
ANEYA_GRAY_LIGHT = HexColor('#9ca3af')     # Tertiary text

# Background colors - Subtle, calming tones
ANEYA_LIGHT_GRAY = HexColor('#e5e7eb')     # Borders, dividers
ANEYA_CREAM = HexColor('#f8fafc')          # Alternating rows (very light)
ANEYA_WHITE = HexColor('#ffffff')          # Pure white
ANEYA_BG_SUBTLE = HexColor('#f1f5f9')      # Subtle background

# Status/semantic colors
ANEYA_SUCCESS = HexColor('#10b981')        # Green for positive indicators
ANEYA_WARNING = HexColor('#f59e0b')        # Amber for warnings
ANEYA_INFO = HexColor('#3b82f6')           # Blue for info


# ═══════════════════════════════════════════════════════════════════════════════
# TYPOGRAPHY CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Font sizes for strong visual hierarchy
FONT_TITLE = 24                            # Main document title
FONT_SUBTITLE = 14                         # Subtitles, dates
FONT_SECTION_HEADER = 13                   # Section headers
FONT_SUBSECTION = 11                       # Subsection headers
FONT_LABEL = 9                             # Field labels
FONT_VALUE = 10                            # Field values
FONT_SMALL = 8                             # Footer, captions
FONT_TABLE_HEADER = 8                      # Table headers
FONT_TABLE_CELL = 8                        # Table cell content

# Line heights and spacing
LINE_HEIGHT = 0.45 * cm                    # Standard line height
SECTION_SPACING = 0.8 * cm                 # Space between sections
FIELD_SPACING = 0.4 * cm                   # Space between fields


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Page margins (generous for modern feel)
MARGIN_TOP = 2.2 * cm
MARGIN_BOTTOM = 2.5 * cm
MARGIN_LEFT = 2 * cm
MARGIN_RIGHT = 2 * cm

# Content area
CONTENT_WIDTH = A4[0] - MARGIN_LEFT - MARGIN_RIGHT


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATIVE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def draw_gradient_rect(c: canvas.Canvas, x: float, y: float, width: float, height: float,
                       color_start: Color, color_end: Color, steps: int = 50) -> None:
    """
    Draw a vertical gradient rectangle (simulated with horizontal stripes).
    Creates a subtle gradient effect from color_start (top) to color_end (bottom).
    """
    step_height = height / steps

    for i in range(steps):
        # Interpolate color
        ratio = i / steps
        r = color_start.red + (color_end.red - color_start.red) * ratio
        g = color_start.green + (color_end.green - color_start.green) * ratio
        b = color_start.blue + (color_end.blue - color_start.blue) * ratio

        c.setFillColor(Color(r, g, b))
        c.rect(x, y - (i + 1) * step_height, width, step_height + 0.5, fill=1, stroke=0)


def draw_subtle_line(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float,
                     color: Color = ANEYA_LIGHT_GRAY, width: float = 0.5) -> None:
    """Draw a subtle decorative line."""
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)


def draw_accent_bar(c: canvas.Canvas, x: float, y: float, width: float, height: float,
                    color: Color = ANEYA_TEAL) -> None:
    """Draw a thin accent bar (used for visual emphasis)."""
    c.setFillColor(color)
    c.rect(x, y, width, height, fill=1, stroke=0)


def draw_rounded_rect(c: canvas.Canvas, x: float, y: float, width: float, height: float,
                      radius: float = 3*mm, fill_color: Color = None,
                      stroke_color: Color = None, stroke_width: float = 0.5) -> None:
    """
    Draw a rectangle with rounded corners.
    Creates a modern card-like appearance.
    """
    path = c.beginPath()

    # Start from bottom-left, going clockwise
    path.moveTo(x + radius, y)
    path.lineTo(x + width - radius, y)
    path.arcTo(x + width - radius, y, x + width, y + radius, radius)
    path.lineTo(x + width, y + height - radius)
    path.arcTo(x + width, y + height - radius, x + width - radius, y + height, radius)
    path.lineTo(x + radius, y + height)
    path.arcTo(x + radius, y + height, x, y + height - radius, radius)
    path.lineTo(x, y + radius)
    path.arcTo(x, y + radius, x + radius, y, radius)
    path.close()

    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)

    if fill_color and stroke_color:
        c.drawPath(path, fill=1, stroke=1)
    elif fill_color:
        c.drawPath(path, fill=1, stroke=0)
    elif stroke_color:
        c.drawPath(path, fill=0, stroke=1)


def draw_decorative_dots(c: canvas.Canvas, x: float, y: float,
                         count: int = 3, spacing: float = 4*mm,
                         radius: float = 1*mm, color: Color = ANEYA_TEAL_LIGHT) -> None:
    """Draw a row of decorative dots (subtle AI/tech aesthetic)."""
    c.setFillColor(color)
    for i in range(count):
        c.circle(x + i * spacing, y, radius, fill=1, stroke=0)


def draw_header_decoration(c: canvas.Canvas, width: float, height: float,
                           primary_color: Color = ANEYA_NAVY,
                           accent_color: Color = ANEYA_TEAL) -> float:
    """
    Draw a modern, elegant header decoration at the top of the page.
    Returns the Y position after the header decoration.
    """
    page_width, page_height = A4

    # Subtle gradient header bar at very top
    header_height = 8 * mm
    draw_gradient_rect(c, 0, page_height - header_height, page_width, header_height,
                       primary_color, ANEYA_NAVY_LIGHT, steps=30)

    # Thin accent line below header
    draw_accent_bar(c, 0, page_height - header_height - 1*mm, page_width, 1*mm, accent_color)

    return page_height - header_height - 1*mm - MARGIN_TOP


def draw_page_footer(c: canvas.Canvas, page_num: int, total_pages: int = None,
                     primary_color: Color = ANEYA_NAVY,
                     accent_color: Color = ANEYA_TEAL) -> None:
    """
    Draw a modern footer with page numbers and branding.
    """
    page_width, page_height = A4
    footer_y = MARGIN_BOTTOM - 0.5*cm

    # Subtle line above footer
    draw_subtle_line(c, MARGIN_LEFT, footer_y + 0.8*cm,
                     page_width - MARGIN_RIGHT, footer_y + 0.8*cm,
                     ANEYA_LIGHT_GRAY, 0.3)

    # Left side: Aneya branding with subtle styling
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica", FONT_SMALL)
    c.drawString(MARGIN_LEFT, footer_y + 0.3*cm, "Powered by")

    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", FONT_SMALL)
    c.drawString(MARGIN_LEFT + 2.2*cm, footer_y + 0.3*cm, "Aneya")

    # Small accent dot
    c.setFillColor(accent_color)
    c.circle(MARGIN_LEFT + 3.2*cm, footer_y + 0.45*cm, 1*mm, fill=1, stroke=0)

    # Center: Confidentiality notice
    c.setFillColor(ANEYA_GRAY_LIGHT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(page_width/2, footer_y, "Confidential Medical Document")

    # Right side: Page number with modern styling
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica", FONT_SMALL)
    if total_pages:
        page_text = f"Page {page_num} of {total_pages}"
    else:
        page_text = f"Page {page_num}"
    c.drawRightString(page_width - MARGIN_RIGHT, footer_y + 0.3*cm, page_text)



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


def render_clinic_logo(c: canvas.Canvas, x: float, y: float, logo_url: str,
                       max_width: float = 4.5*cm, max_height: float = 1.8*cm) -> bool:
    """
    Download clinic logo from GCS and render at specified position.

    Args:
        c: ReportLab canvas
        x: X position for logo
        y: Y position for logo (top of logo)
        logo_url: Public URL of the clinic logo
        max_width: Maximum logo width
        max_height: Maximum logo height

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

        # Calculate scaling to fit within constraints
        img_width, img_height = img.getSize()
        scale = min(max_width/img_width, max_height/img_height)

        scaled_width = img_width * scale
        scaled_height = img_height * scale

        # Draw image
        c.drawImage(img, x, y - scaled_height,
                   width=scaled_width,
                   height=scaled_height,
                   preserveAspectRatio=True,
                   mask='auto')

        print(f"✅ Clinic logo rendered successfully")
        return True

    except Exception as e:
        print(f"⚠️  Failed to render clinic logo: {e}")
        return False


def render_header(c: canvas.Canvas, y: float, doctor_info: Optional[Dict[str, Any]] = None,
                 primary_color=ANEYA_NAVY, text_color=ANEYA_GRAY,
                 accent_color=ANEYA_TEAL, title: str = "Consultation Report") -> float:
    """
    Render a modern, elegant PDF header with gradient decoration,
    title, generation date, and optional clinic logo.

    Args:
        c: ReportLab canvas
        y: Current Y position (ignored - header starts at top)
        doctor_info: Optional dict with clinic_name and clinic_logo_url
        primary_color: Primary color for title
        text_color: Text color for date
        accent_color: Accent color for decorative elements
        title: Document title

    Returns:
        float: Updated Y position after header
    """
    width, height = A4

    # Draw decorative header bar at top of page
    y = draw_header_decoration(c, width, height, primary_color, accent_color)

    # === Document Title Section ===
    # Main title with elegant typography
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", FONT_TITLE)
    c.drawString(MARGIN_LEFT, y, title)

    # Try to render clinic logo on the right
    logo_rendered = False
    if doctor_info and doctor_info.get('clinic_logo_url'):
        logo_x = width - MARGIN_RIGHT - 4.5*cm
        logo_rendered = render_clinic_logo(c, logo_x, y + 0.3*cm, doctor_info['clinic_logo_url'])

    # Fallback to clinic name as elegant text if no logo rendered
    if not logo_rendered and doctor_info and doctor_info.get('clinic_name'):
        c.setFillColor(primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(width - MARGIN_RIGHT, y, doctor_info['clinic_name'])

    y -= 0.7*cm

    # Generation date with subtle styling
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica", FONT_SUBTITLE - 2)
    generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
    c.drawString(MARGIN_LEFT, y, f"Generated: {generation_date}")

    # Decorative dots after date
    date_width = c.stringWidth(f"Generated: {generation_date}", "Helvetica", FONT_SUBTITLE - 2)
    draw_decorative_dots(c, MARGIN_LEFT + date_width + 0.5*cm, y + 0.15*cm,
                        count=3, spacing=3*mm, radius=0.8*mm, color=accent_color)

    y -= 1.2*cm

    # Subtle separator line
    draw_subtle_line(c, MARGIN_LEFT, y + 0.3*cm, width - MARGIN_RIGHT, y + 0.3*cm,
                    ANEYA_LIGHT_GRAY, 0.5)

    y -= 0.4*cm

    return y


def render_section_header(c: canvas.Canvas, title: str, y: float,
                         primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL,
                         with_background: bool = True) -> float:
    """
    Render a modern section header with optional subtle background.

    Features:
    - Subtle rounded background for visual grouping
    - Accent bar on the left for emphasis
    - Clean typography with good spacing

    Args:
        c: ReportLab canvas
        title: Section title
        y: Current Y position
        primary_color: Primary color for text
        accent_color: Accent color for decorative elements
        with_background: Whether to draw subtle background

    Returns:
        float: Updated Y position
    """
    width, height = A4
    header_height = 0.8*cm
    content_width = width - MARGIN_LEFT - MARGIN_RIGHT

    if with_background:
        # Subtle background for section header
        draw_rounded_rect(c, MARGIN_LEFT, y - header_height + 0.1*cm,
                         content_width, header_height,
                         radius=2*mm, fill_color=ANEYA_BG_SUBTLE)

    # Left accent bar
    draw_accent_bar(c, MARGIN_LEFT, y - header_height + 0.1*cm, 3*mm, header_height, accent_color)

    # Section title
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", FONT_SECTION_HEADER)
    c.drawString(MARGIN_LEFT + 0.6*cm, y - 0.45*cm, title)

    y -= header_height + 0.4*cm

    return y


def render_field(c: canvas.Canvas, label: str, value: Any, y: float, x_offset: float = None,
                text_color=ANEYA_GRAY, primary_color=ANEYA_NAVY,
                label_width: float = None, inline: bool = True) -> float:
    """
    Render a field with label and value using modern styling.

    Features:
    - Clean label/value separation
    - Subtle visual distinction between label and value
    - Support for inline and stacked layouts
    - Intelligent word wrapping for long values

    Args:
        c: ReportLab canvas
        label: Field label
        value: Field value
        y: Current Y position
        x_offset: X offset for field (defaults to MARGIN_LEFT)
        text_color: Color for value text
        primary_color: Color for label text
        label_width: Fixed label width (auto-calculated if None)
        inline: If True, value appears next to label; if False, below

    Returns:
        float: Updated Y position
    """
    if value is None or value == '' or value == []:
        return y

    x_offset = x_offset if x_offset is not None else MARGIN_LEFT
    width, height = A4

    # Label styling - slightly lighter weight for modern feel
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica", FONT_LABEL)
    label_text = f"{label}"

    if label_width is None:
        label_width = c.stringWidth(label_text, "Helvetica", FONT_LABEL)

    c.drawString(x_offset, y, label_text)

    # Value styling - slightly bolder for emphasis
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", FONT_VALUE)

    # Convert value to string
    value_str = str(value)

    if inline:
        # Inline layout: value next to label
        value_x = x_offset + label_width + 0.4*cm
        max_value_width = width - MARGIN_RIGHT - value_x

        # Handle long text with word wrapping
        if c.stringWidth(value_str, "Helvetica-Bold", FONT_VALUE) > max_value_width:
            lines = []
            words = value_str.split()
            current_line = ""

            for word in words:
                test_line = f"{current_line} {word}".strip()
                if c.stringWidth(test_line, "Helvetica-Bold", FONT_VALUE) <= max_value_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word

            if current_line:
                lines.append(current_line)

            # Draw first line next to label
            if lines:
                c.drawString(value_x, y, lines[0])
                y -= FIELD_SPACING

                # Draw remaining lines with indentation
                for line in lines[1:]:
                    c.drawString(value_x, y, line)
                    y -= FIELD_SPACING
        else:
            c.drawString(value_x, y, value_str)
            y -= FIELD_SPACING
    else:
        # Stacked layout: value below label
        y -= 0.35*cm
        c.drawString(x_offset + 0.2*cm, y, value_str)
        y -= FIELD_SPACING

    return y


def render_field_card(c: canvas.Canvas, label: str, value: Any, y: float,
                      x: float, card_width: float, card_height: float = 1.2*cm,
                      primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL) -> float:
    """
    Render a field as a modern card with subtle border.
    Great for key metrics like vital signs.

    Args:
        c: ReportLab canvas
        label: Field label
        value: Field value
        y: Current Y position (top of card)
        x: X position for card
        card_width: Width of the card
        card_height: Height of the card
        primary_color: Primary color
        accent_color: Accent color for border

    Returns:
        float: Updated Y position
    """
    if value is None or value == '' or value == []:
        return y

    # Draw card background with subtle border
    draw_rounded_rect(c, x, y - card_height, card_width, card_height,
                     radius=2*mm, fill_color=ANEYA_WHITE,
                     stroke_color=ANEYA_LIGHT_GRAY, stroke_width=0.3)

    # Small accent at top of card
    c.setFillColor(accent_color)
    c.rect(x + 3*mm, y - 2*mm, card_width - 6*mm, 1.5*mm, fill=1, stroke=0)

    # Label (smaller, above value)
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica", 7)
    c.drawString(x + 0.3*cm, y - 0.55*cm, label)

    # Value (larger, prominent)
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 12)
    value_str = str(value)
    if len(value_str) > 15:
        value_str = value_str[:12] + "..."
    c.drawString(x + 0.3*cm, y - 0.95*cm, value_str)

    return y


def render_appointment_section(c: canvas.Canvas, appointment: Dict[str, Any], patient: Dict[str, Any], y: float,
                               primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL) -> float:
    """
    Render appointment details section with modern card-based layout.
    Key information displayed prominently in cards.
    """
    width, height = A4

    y = render_section_header(c, "Appointment Details", y, primary_color=primary_color, accent_color=accent_color)

    # Key metrics in cards (top row)
    card_width = 4*cm
    card_height = 1.3*cm
    card_spacing = 0.4*cm
    cards_start_x = MARGIN_LEFT

    # Row of key metric cards
    patient_name = patient.get('name', 'N/A')
    date_time = format_date_time(appointment.get('scheduled_time', ''))
    specialty = appointment.get('specialty', 'N/A')
    status = appointment.get('status', '').title()

    # Draw cards for key metrics
    metrics = [
        ("Patient", patient_name[:20] if len(patient_name) > 20 else patient_name),
        ("Date & Time", date_time.split(' at ')[0] if ' at ' in date_time else date_time[:15]),
        ("Specialty", specialty),
        ("Status", status)
    ]

    for i, (label, value) in enumerate(metrics):
        if value and value != 'N/A':
            card_x = cards_start_x + i * (card_width + card_spacing)
            render_field_card(c, label, value, y, card_x, card_width, card_height,
                            primary_color=primary_color, accent_color=accent_color)

    y -= card_height + 0.6*cm

    # Additional details below cards
    additional_fields = [
        ("Duration", f"{appointment.get('duration_minutes', 'N/A')} minutes" if appointment.get('duration_minutes') else None),
        ("Reason for Visit", appointment.get('reason')),
        ("Notes", appointment.get('notes')),
    ]

    for label, value in additional_fields:
        if value:
            y = render_field(c, label, value, y, primary_color=primary_color)

    y -= SECTION_SPACING
    return y


def render_patient_section(c: canvas.Canvas, patient: Dict[str, Any], y: float,
                           primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL) -> float:
    """
    Render patient information section with modern styling.
    Uses cards for physical measurements and clean layout for other info.
    """
    width, height = A4

    y = render_section_header(c, "Patient Information", y, primary_color=primary_color, accent_color=accent_color)

    # Calculate age from date_of_birth if available
    age_display = None
    dob_display = None
    if patient.get('date_of_birth'):
        try:
            dob_str = patient['date_of_birth']
            if 'T' in dob_str:
                dob_str = dob_str.split('T')[0]
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
            age = (datetime.now() - dob).days // 365
            age_display = f"{age} yrs"
            dob_display = dob.strftime('%d %b %Y')
        except Exception as e:
            print(f"⚠️  Error parsing date_of_birth: {e}")
            dob_str = str(patient['date_of_birth'])
            if len(dob_str) <= 20:
                dob_display = dob_str
    elif patient.get('age_years'):
        age_display = f"{patient['age_years']} yrs"

    # Get measurements
    height_val = patient.get('height_cm')
    weight_val = patient.get('weight_kg')
    sex_val = patient.get('sex', '').title() if patient.get('sex') else None

    # Patient identifier cards row
    card_width = 3.2*cm
    card_height = 1.2*cm
    card_spacing = 0.3*cm

    patient_cards = []
    if age_display:
        patient_cards.append(("Age", age_display))
    if sex_val:
        patient_cards.append(("Sex", sex_val))
    if height_val:
        patient_cards.append(("Height", f"{height_val} cm"))
    if weight_val:
        patient_cards.append(("Weight", f"{weight_val} kg"))

    # Draw measurement cards if we have any
    if patient_cards:
        for i, (label, value) in enumerate(patient_cards[:5]):  # Max 5 cards
            card_x = MARGIN_LEFT + i * (card_width + card_spacing)
            render_field_card(c, label, value, y, card_x, card_width, card_height,
                            primary_color=primary_color, accent_color=accent_color)
        y -= card_height + 0.5*cm

    # Text fields for other patient info
    text_fields = [
        ("Full Name", patient.get('name')),
        ("Date of Birth", dob_display),
    ]

    for label, value in text_fields:
        if value:
            y = render_field(c, label, value, y, primary_color=primary_color)

    # Medical history section (visually distinct)
    y -= 0.3*cm

    # Subtle subsection header
    c.setFillColor(ANEYA_GRAY_MEDIUM)
    c.setFont("Helvetica-Bold", FONT_SUBSECTION - 1)
    c.drawString(MARGIN_LEFT, y, "Medical History")
    y -= 0.5*cm

    # Draw subtle line
    draw_subtle_line(c, MARGIN_LEFT, y + 0.2*cm, MARGIN_LEFT + 4*cm, y + 0.2*cm, accent_color, 1)

    medical_fields = [
        ("Allergies", patient.get('allergies') or "None recorded"),
        ("Current Medications", patient.get('current_medications') or "None recorded"),
        ("Current Conditions", patient.get('current_conditions') or "None recorded"),
    ]

    for label, value in medical_fields:
        y = render_field(c, label, value, y, primary_color=primary_color)

    y -= SECTION_SPACING
    return y


def render_form_data_section(c: canvas.Canvas, form_data: Dict[str, Any], form_type: str, y: float,
                             primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL) -> float:
    """
    Render consultation form data with modern styling.
    Supports nested sections, lists, and various field types.
    """
    width, height = A4

    # Format form type for display
    form_type_display = form_type.replace('_', ' ').title()
    y = render_section_header(c, f"Clinical Notes — {form_type_display}", y,
                             primary_color=primary_color, accent_color=accent_color)

    # Check if we need a new page
    if y < 5*cm:
        c.showPage()
        y = height - MARGIN_TOP
        y = render_section_header(c, f"Clinical Notes — {form_type_display} (cont.)", y,
                                 primary_color=primary_color, accent_color=accent_color)

    # Render nested JSONB data
    for section_key, section_value in form_data.items():
        # Check if need new page
        if y < 3*cm:
            c.showPage()
            y = height - MARGIN_TOP

        if isinstance(section_value, dict):
            # Nested section (e.g., "vital_signs", "physical_exam")
            # Subsection header with accent styling
            y -= 0.2*cm

            # Small accent bar
            draw_accent_bar(c, MARGIN_LEFT, y - 0.1*cm, 2*mm, 0.4*cm, accent_color)

            c.setFillColor(primary_color)
            c.setFont("Helvetica-Bold", FONT_SUBSECTION)
            c.drawString(MARGIN_LEFT + 0.5*cm, y, format_field_label(section_key))
            y -= 0.6*cm

            for field_key, field_value in section_value.items():
                if field_value is not None and field_value != '' and field_value != []:
                    y = render_field(c, format_field_label(field_key), field_value, y,
                                   x_offset=MARGIN_LEFT + 0.3*cm, primary_color=primary_color)

                    # Check if need new page
                    if y < 3*cm:
                        c.showPage()
                        y = height - MARGIN_TOP

            y -= 0.4*cm

        elif isinstance(section_value, list):
            # List field (e.g., diagnoses)
            if section_value:  # Only render if not empty
                y -= 0.2*cm

                # Small accent bar
                draw_accent_bar(c, MARGIN_LEFT, y - 0.1*cm, 2*mm, 0.4*cm, accent_color)

                c.setFillColor(primary_color)
                c.setFont("Helvetica-Bold", FONT_SUBSECTION)
                c.drawString(MARGIN_LEFT + 0.5*cm, y, format_field_label(section_key))
                y -= 0.5*cm

                for item in section_value:
                    if isinstance(item, dict):
                        # Render each dict item
                        for k, v in item.items():
                            if v:
                                y = render_field(c, format_field_label(k), v, y,
                                               x_offset=MARGIN_LEFT + 0.3*cm, primary_color=primary_color)
                    else:
                        # Simple list item with bullet
                        c.setFillColor(accent_color)
                        c.circle(MARGIN_LEFT + 0.5*cm, y + 0.1*cm, 1.5*mm, fill=1, stroke=0)
                        c.setFillColor(ANEYA_GRAY)
                        c.setFont("Helvetica", FONT_VALUE)
                        c.drawString(MARGIN_LEFT + 0.9*cm, y, str(item))
                        y -= FIELD_SPACING

                y -= 0.4*cm
        else:
            # Top-level field
            if section_value is not None and section_value != '':
                y = render_field(c, format_field_label(section_key), section_value, y,
                               x_offset=MARGIN_LEFT, primary_color=primary_color)

    return y


def generate_consultation_pdf(
    appointment: Dict[str, Any],
    patient: Dict[str, Any],
    form_data: Dict[str, Any],
    form_type: str = 'consultation_form',
    doctor_info: Optional[Dict[str, Any]] = None
) -> BytesIO:
    """
    Generate a beautiful, modern PDF consultation report.

    Features:
    - Modern gradient header with clinic branding
    - Card-based layout for key metrics
    - Clean typography with strong visual hierarchy
    - Professional footer with page numbers

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

    # Track page number
    page_num = 1

    # Track Y position - start from top
    y = height - MARGIN_TOP

    # Render modern header with gradient decoration
    y = render_header(c, y, doctor_info, title="Consultation Report")

    # Render appointment section with card-based metrics
    y = render_appointment_section(c, appointment, patient, y)

    # Check if need new page before patient section
    if y < 8*cm:
        draw_page_footer(c, page_num)
        c.showPage()
        page_num += 1
        # New page header decoration
        y = draw_header_decoration(c, width, height, ANEYA_NAVY, ANEYA_TEAL)

    # Render patient section with modern cards for vitals
    y = render_patient_section(c, patient, y)

    # Check if need new page before form data
    if y < 8*cm:
        draw_page_footer(c, page_num)
        c.showPage()
        page_num += 1
        y = draw_header_decoration(c, width, height, ANEYA_NAVY, ANEYA_TEAL)

    # Render form data section
    y = render_form_data_section(c, form_data, form_type, y)

    # Add modern footer on last page
    draw_page_footer(c, page_num, primary_color=ANEYA_NAVY, accent_color=ANEYA_TEAL)

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
    primary_color=ANEYA_NAVY,
    text_color=ANEYA_GRAY,
    light_gray_color=ANEYA_LIGHT_GRAY
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
        primary_color: Primary color for headers
        text_color: Text color for cells
        light_gray_color: Light gray color for backgrounds

    Returns:
        Updated Y position
    """
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

    # Table title with modern styling (skip if splitting, as each chunk will have its own title)
    if not needs_split:
        left_margin = 1*cm if needs_landscape else MARGIN_LEFT

        # Accent bar before title
        draw_accent_bar(c, left_margin, y - 0.1*cm, 2*mm, 0.4*cm, ANEYA_TEAL)

        c.setFont("Helvetica-Bold", FONT_SUBSECTION)
        c.setFillColor(primary_color)
        c.drawString(left_margin + 0.5*cm, y, label)
        y -= 0.7*cm

    # Get table data from form_data
    table_data_raw = form_data.get(section_id, {}).get(field_name, [])
    if not isinstance(table_data_raw, list):
        table_data_raw = []

    # Create paragraph styles for wrapping with modern typography
    header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=FONT_TABLE_HEADER,
        leading=10,
        alignment=1,  # Center
        textColor=ANEYA_WHITE
    )

    cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=FONT_TABLE_CELL,
        leading=10,
        alignment=0,  # Left
        textColor=ANEYA_GRAY
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
            c.setFillColor(primary_color)
            if chunk_idx > 0:
                c.drawString(1*cm, y, f"• {label} (continued - Part {chunk_idx + 1})")
            else:
                c.drawString(1*cm, y, f"• {label} (Part 1 of {len(column_chunks)})")
            y -= 0.6*cm

            # Create and render table
            row_heights = [None] * len(chunk_table_data)
            row_heights[0] = 0.8*cm

            pdf_table = Table(chunk_table_data, colWidths=chunk_widths, rowHeights=row_heights)

            # Modern table styling with dark header
            table_style = [
                # Header styling - dark background with white text
                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), ANEYA_WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), FONT_TABLE_HEADER),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Data row styling
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TEXTCOLOR', (0, 1), (-1, -1), ANEYA_GRAY),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), FONT_TABLE_CELL),
                # Subtle borders - only horizontal lines for modern look
                ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
                ('LINEBELOW', (0, 1), (-1, -2), 0.3, ANEYA_LIGHT_GRAY),
                ('LINEBELOW', (0, -1), (-1, -1), 0.5, ANEYA_LIGHT_GRAY),
                # Alternating row backgrounds
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [ANEYA_WHITE, ANEYA_CREAM]),
                # Generous padding for readability
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
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

    # Modern table styling with elegant dark header
    table_style = [
        # Header styling - dark background with white text
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), ANEYA_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), FONT_TABLE_HEADER),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data row styling
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 1), (-1, -1), ANEYA_GRAY),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), FONT_TABLE_CELL),
        # Subtle borders - modern horizontal line style
        ('LINEBELOW', (0, 0), (-1, 0), 1, primary_color),
        ('LINEBELOW', (0, 1), (-1, -2), 0.3, ANEYA_LIGHT_GRAY),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, ANEYA_LIGHT_GRAY),
        # Alternating row backgrounds for readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [ANEYA_WHITE, ANEYA_CREAM]),
        # Generous padding for modern feel
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    # Additional styling for transposed tables with row headers
    if is_transposed and row_names:
        table_style.extend([
            ('BACKGROUND', (0, 1), (0, -1), ANEYA_BG_SUBTLE),  # Row header column - subtle background
            ('TEXTCOLOR', (0, 1), (0, -1), primary_color),     # Row header text color
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),   # Row header column bold
            ('FONTSIZE', (0, 1), (0, -1), FONT_TABLE_CELL),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),                # Row headers left-aligned
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),             # Data cells centered
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
    primary_color=ANEYA_NAVY,
    accent_color=ANEYA_TEAL,
    text_color=ANEYA_GRAY,
    light_gray_color=ANEYA_LIGHT_GRAY
) -> float:
    """
    Render a custom form section using pdf_template configuration.

    Args:
        c: ReportLab canvas
        section_config: PDF template section configuration
        form_data: Actual form data (JSONB)
        y: Current Y position
        form_schema: Optional form schema for table field rendering
        primary_color: Primary color for headers
        accent_color: Accent color for underlines
        text_color: Text color for fields
        light_gray_color: Light gray color for backgrounds

    Returns:
        float: Updated Y position
    """
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
    y = render_section_header(c, section_title, y, primary_color=primary_color, accent_color=accent_color)

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
                y = render_table_field(c, section_id, field_name, label, schema_field, form_data, y,
                                      primary_color=primary_color, text_color=text_color, light_gray_color=light_gray_color)

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
                    y = render_section_header(c, f"{section_title} - Continued", y, primary_color=primary_color, accent_color=accent_color)

                # Render field
                y = render_field(c, label, value, y, x_offset=x_offset, text_color=text_color, primary_color=primary_color)

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
                y = render_table_field(c, section_id, field_name, label, schema_field, form_data, y,
                                      primary_color=primary_color, text_color=text_color, light_gray_color=light_gray_color)

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
                    y = render_section_header(c, f"{section_title} - Continued", y, primary_color=primary_color, accent_color=accent_color)

                # Render field
                y = render_field(c, label, value, y, x_offset=x_offset, text_color=text_color, primary_color=primary_color)

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
                                      primary_color=primary_color, text_color=text_color, light_gray_color=light_gray_color)

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
                    y = render_section_header(c, f"{section_title} - Continued", y, primary_color=primary_color, accent_color=accent_color)

                # Render field
                y = render_field(c, label, value, y, text_color=text_color, primary_color=primary_color)

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
    # Color customization
    primary_color: Optional[str] = None,
    accent_color: Optional[str] = None,
    text_color: Optional[str] = None,
    light_gray_color: Optional[str] = None
) -> BytesIO:
    """
    Generate a beautiful, modern PDF for a custom form using stored pdf_template.

    Features:
    - Modern gradient header with clinic branding
    - Card-based layout for patient metrics
    - Clean typography with strong visual hierarchy
    - Professional footer with page numbers

    Args:
        form_data: Filled form data (JSONB from filled_forms table)
        pdf_template: PDF layout template (JSONB from custom_forms table)
        form_name: Name of the form
        specialty: Medical specialty
        patient: Optional patient information
        doctor_info: Optional dict with clinic_name and clinic_logo_url
        form_schema: Optional form schema for table rendering
        primary_color: Optional primary color (hex string)
        accent_color: Optional accent color (hex string)
        text_color: Optional text color (hex string)
        light_gray_color: Optional light gray color (hex string)

    Returns:
        BytesIO containing PDF bytes
    """
    # Convert color parameters to HexColor, falling back to Aneya defaults
    primary_hex = HexColor(primary_color) if primary_color else ANEYA_NAVY
    accent_hex = HexColor(accent_color) if accent_color else ANEYA_TEAL
    text_hex = HexColor(text_color) if text_color else ANEYA_GRAY
    light_gray_hex = HexColor(light_gray_color) if light_gray_color else ANEYA_LIGHT_GRAY

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Track page number
    page_num = 1

    # Track Y position - start from top
    y = height - MARGIN_TOP

    # Get page config
    page_config = pdf_template.get('page_config', {})
    header_config = page_config.get('header', {})

    # Format form title
    form_title = header_config.get('title', format_field_label(form_name))

    # Render modern header with gradient decoration
    if header_config.get('show_logo') or header_config.get('show_clinic_name'):
        y = render_header(c, y, doctor_info, primary_color=primary_hex, text_color=text_hex,
                         accent_color=accent_hex, title=form_title)
    else:
        # Draw decorative header bar at top of page
        y = draw_header_decoration(c, width, height, primary_hex, accent_hex)

        # Form title with elegant typography
        c.setFillColor(primary_hex)
        c.setFont("Helvetica-Bold", FONT_TITLE)
        c.drawString(MARGIN_LEFT, y, form_title)
        y -= 0.7*cm

        # Specialty subtitle with badge-like styling
        c.setFillColor(ANEYA_GRAY_MEDIUM)
        c.setFont("Helvetica", FONT_SUBTITLE - 2)
        specialty_text = f"{specialty.title()}"
        c.drawString(MARGIN_LEFT, y, specialty_text)

        # Generation date
        generation_date = datetime.now().strftime('%d %B %Y at %H:%M')
        date_x = MARGIN_LEFT + c.stringWidth(specialty_text, "Helvetica", FONT_SUBTITLE - 2) + 1*cm
        c.drawString(date_x, y, f"•  {generation_date}")

        # Decorative dots
        dots_x = date_x + c.stringWidth(f"•  {generation_date}", "Helvetica", FONT_SUBTITLE - 2) + 0.5*cm
        draw_decorative_dots(c, dots_x, y + 0.15*cm, count=3, spacing=3*mm, radius=0.8*mm, color=accent_hex)

        y -= 1.2*cm

        # Subtle separator
        draw_subtle_line(c, MARGIN_LEFT, y + 0.3*cm, width - MARGIN_RIGHT, y + 0.3*cm,
                        ANEYA_LIGHT_GRAY, 0.5)
        y -= 0.4*cm

    # Render patient section if provided
    if patient:
        if y < 8*cm:
            draw_page_footer(c, page_num, primary_color=primary_hex, accent_color=accent_hex)
            c.showPage()
            page_num += 1
            y = draw_header_decoration(c, width, height, primary_hex, accent_hex)

        y = render_patient_section(c, patient, y, primary_color=primary_hex, accent_color=accent_hex)

    # Render form sections using template
    sections = pdf_template.get('sections', [])

    for section_config in sections:
        # Check for page break before section
        if section_config.get('page_break_before', False):
            draw_page_footer(c, page_num, primary_color=primary_hex, accent_color=accent_hex)
            c.showPage()
            page_num += 1
            y = draw_header_decoration(c, width, height, primary_hex, accent_hex)

        # Check if need new page
        if y < 8*cm:
            draw_page_footer(c, page_num, primary_color=primary_hex, accent_color=accent_hex)
            c.showPage()
            page_num += 1
            y = draw_header_decoration(c, width, height, primary_hex, accent_hex)

        # Render section
        y = render_custom_form_section(c, section_config, form_data, y, form_schema,
                                      primary_color=primary_hex, accent_color=accent_hex,
                                      text_color=text_hex, light_gray_color=light_gray_hex)

    # Add modern footer on last page
    draw_page_footer(c, page_num, primary_color=primary_hex, accent_color=accent_hex)

    c.save()
    buffer.seek(0)
    return buffer
