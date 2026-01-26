"""
Headless Browser PDF Generator

Uses Playwright to render React components as PDFs with clinic branding.
Replaces the old ReportLab-based PDF generator.
"""

from playwright.async_api import async_playwright
import asyncio
from io import BytesIO
import json
import os
from pathlib import Path


async def generate_pdf_from_react(
    html_content: str,
    pdf_options: dict = None
) -> BytesIO:
    """
    Render React component HTML as PDF using Playwright.

    Args:
        html_content: Full HTML with embedded React component
        pdf_options: PDF settings (format, margins, landscape)

    Returns:
        BytesIO containing PDF bytes
    """
    if pdf_options is None:
        pdf_options = {}

    async with async_playwright() as p:
        # Launch headless Chromium
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']  # Required for Docker
        )

        page = await browser.new_page()

        # Log console messages for debugging
        page.on("console", lambda msg: print(f"[Browser {msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: print(f"[Browser Error] {exc}"))

        # Set viewport for consistent rendering
        await page.set_viewport_size({"width": 1200, "height": 1600})

        # Load HTML with React component
        await page.set_content(html_content, wait_until="networkidle")

        # Wait for fonts and images to load
        await page.wait_for_timeout(1000)

        # Generate PDF
        pdf_bytes = await page.pdf(
            format=pdf_options.get("format", "A4"),
            print_background=True,
            margin=pdf_options.get("margin", {
                "top": "20mm",
                "right": "15mm",
                "bottom": "20mm",
                "left": "15mm"
            }),
            landscape=pdf_options.get("landscape", False),
            prefer_css_page_size=False
        )

        await browser.close()

    return BytesIO(pdf_bytes)


def build_html_template(
    component_name: str,
    props_data: dict,
    clinic_branding: dict
) -> str:
    """
    Build HTML template with React component and data.

    Args:
        component_name: "PdfConsultationForm" or "PdfAnalysisReport"
        props_data: Component props as dict
        clinic_branding: Design tokens (colors, logos)

    Returns:
        HTML string ready for rendering
    """
    # Load Tailwind CSS from CDN for PDF generation
    tailwind_cdn = "https://cdn.tailwindcss.com"

    # Load React bundle (pre-built)
    react_bundle_path = Path(__file__).parent / "static" / "pdf-templates-bundle.js"

    if react_bundle_path.exists():
        with open(react_bundle_path, 'r') as f:
            react_bundle = f.read()
    else:
        # Fallback: use empty bundle (will need to build)
        react_bundle = "console.warn('PDF templates bundle not found');"

    # Inject clinic colors as CSS variables
    clinic_css = f"""
    :root {{
        --clinic-primary: {clinic_branding.get('primary_color', '#0c3555')};
        --clinic-accent: {clinic_branding.get('accent_color', '#1d9e99')};
        --clinic-background: {clinic_branding.get('background_color', '#f6f5ee')};

        /* Aneya defaults (fallback) */
        --aneya-navy: #0c3555;
        --aneya-teal: #1d9e99;
        --aneya-seagreen: #409f88;
        --aneya-cream: #f6f5ee;

        /* Medical aliases */
        --medical-navy: var(--aneya-navy);
        --medical-teal: var(--aneya-teal);
        --medical-sea-green: var(--aneya-seagreen);
        --medical-cream: var(--aneya-cream);
    }}

    /* Print-specific styles */
    @media print {{
        @page {{
            size: A4;
            margin: 15mm;
        }}

        .section-break {{
            page-break-after: always;
        }}

        .avoid-break {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}

        .print-background {{
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
            color-adjust: exact;
        }}
    }}

    /* Ensure backgrounds print */
    * {{
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}
    """

    # Load pdf-print.css
    pdf_print_css_path = Path(__file__).parent.parent / "aneya-frontend" / "src" / "styles" / "pdf-print.css"

    if pdf_print_css_path.exists():
        with open(pdf_print_css_path, 'r') as f:
            pdf_print_css = f.read()
    else:
        pdf_print_css = ""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="{tailwind_cdn}"></script>
        <style>{clinic_css}</style>
        <style>{pdf_print_css}</style>
    </head>
    <body>
        <div id="root"></div>

        <!-- PDF Templates bundle (includes React) -->
        <script>{react_bundle}</script>

        <script>
            // Render React component using bundled render function
            if (typeof PdfTemplates !== 'undefined' && PdfTemplates.render) {{
                const props = {{
                    ...{json.dumps(props_data)},
                    clinicBranding: {json.dumps(clinic_branding)}
                }};
                PdfTemplates.render('{component_name}', props);
            }} else {{
                document.getElementById('root').innerHTML =
                    '<h1>Error: PdfTemplates bundle not loaded. Type: ' + typeof PdfTemplates + '</h1>';
            }}
        </script>
    </body>
    </html>
    """

    return html


def get_default_clinic_branding() -> dict:
    """
    Get default Aneya branding when clinic-specific branding is not configured.

    Returns:
        Default design tokens dict
    """
    return {
        "logo_url": None,
        "primary_color": "#0c3555",
        "accent_color": "#1d9e99",
        "background_color": "#f6f5ee",
        "clinic_name": "Healthcare Medical Center",
        "contact_info": {
            "address": "456 Hospital Avenue",
            "phone": "(555) 123-4567"
        }
    }


async def generate_consultation_pdf(
    form_schema: dict,
    form_data: dict,
    patient_info: dict,
    appointment_info: dict,
    clinic_branding: dict = None
) -> BytesIO:
    """
    Generate PDF for consultation form.

    Args:
        form_schema: Form field definitions
        form_data: Filled form values
        patient_info: Patient details
        appointment_info: Appointment context
        clinic_branding: Optional clinic design tokens

    Returns:
        BytesIO containing PDF bytes
    """
    if clinic_branding is None:
        clinic_branding = get_default_clinic_branding()

    props_data = {
        "formSchema": form_schema,
        "formData": form_data,
        "patientInfo": patient_info,
        "appointmentInfo": appointment_info,
        "clinicBranding": clinic_branding
    }

    html_content = build_html_template(
        component_name="PdfConsultationForm",
        props_data=props_data,
        clinic_branding=clinic_branding
    )

    return await generate_pdf_from_react(
        html_content=html_content,
        pdf_options={"format": "A4", "landscape": False}
    )


async def generate_custom_form_pdf_headless(
    form_schema: dict,
    form_data: dict,
    form_name: str,
    patient_info: dict = None,
    clinic_branding: dict = None
) -> BytesIO:
    """
    Generate PDF for a custom form using headless React renderer.

    Args:
        form_schema: Form field definitions
        form_data: Filled form values
        form_name: Name of the form
        patient_info: Optional patient details
        clinic_branding: Optional clinic design tokens

    Returns:
        BytesIO containing PDF bytes
    """
    from datetime import datetime

    if clinic_branding is None:
        clinic_branding = get_default_clinic_branding()

    if patient_info is None:
        patient_info = {
            "name": "Unknown Patient",
            "age": "",
            "gender": "",
            "mrn": ""
        }

    # Build appointment info for the form
    appointment_info = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "form_name": form_name,
        "specialty": "custom"
    }

    # Debug: Check for any nested objects in formData that might cause React errors
    def find_nested_objects(data, path=""):
        """Recursively find any nested objects that would cause React error #31."""
        issues = []
        if isinstance(data, dict):
            for key, val in data.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(val, dict):
                    # Found a nested dict - this would cause React error #31
                    issues.append(f"{current_path}: dict with keys {list(val.keys())}")
                    issues.extend(find_nested_objects(val, current_path))
                elif isinstance(val, list):
                    for i, item in enumerate(val):
                        if isinstance(item, dict):
                            # Check if dict items have nested dicts
                            for k, v in item.items():
                                if isinstance(v, dict):
                                    issues.append(f"{current_path}[{i}].{k}: dict with keys {list(v.keys())}")
        return issues

    nested_issues = find_nested_objects(form_data)
    if nested_issues:
        print(f"   ⚠️ Warning: Found nested objects in formData - applying deep flattening...")
        for issue in nested_issues[:10]:  # Limit output
            print(f"      - {issue}")

    # CRITICAL FIX: Convert nested objects to arrays for React
    # React can render arrays (maps over them) but not plain objects as children
    def convert_dict_to_array(obj):
        """Convert a dict to an array of {label, value} pairs that React can render."""
        if not isinstance(obj, dict):
            return obj
        return [{"label": k, "value": str(v) if v is not None else ""} for k, v in obj.items()]

    def make_react_safe(value):
        """Convert any value to a React-safe format."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            # Convert dict to array of {label, value} pairs
            return convert_dict_to_array(value)
        if isinstance(value, list):
            # Process each item in the list
            result = []
            for item in value:
                if isinstance(item, dict):
                    # For dicts in lists, ensure all values are strings
                    flat_item = {}
                    for k, v in item.items():
                        if isinstance(v, dict):
                            flat_item[k] = convert_dict_to_array(v)
                        elif isinstance(v, list):
                            flat_item[k] = make_react_safe(v)
                        else:
                            flat_item[k] = str(v) if v is not None else ""
                    result.append(flat_item)
                else:
                    result.append(str(item) if item is not None else "")
            return result
        return str(value)

    def transform_form_data_for_react(data):
        """
        Transform form_data to be React-safe.
        - Keep section structure {section: {field: value}}
        - Convert any nested dict VALUES to arrays of {label, value}
        - Ensure all leaf values are strings or arrays
        """
        if not isinstance(data, dict):
            return {"_value": make_react_safe(data)}

        result = {}
        for section_name, section_data in data.items():
            if isinstance(section_data, dict):
                flat_section = {}
                for field_name, field_value in section_data.items():
                    flat_section[field_name] = make_react_safe(field_value)
                result[section_name] = flat_section
            else:
                result[section_name] = make_react_safe(section_data)
        return result

    # Apply transformation to form_data
    form_data = transform_form_data_for_react(form_data)

    # Debug: Print actual structure being passed to React
    print(f"   📊 Final formData structure for React (dict→array conversion):")
    for section_name, section_data in list(form_data.items())[:3]:
        if isinstance(section_data, dict):
            print(f"      {section_name}: dict with {len(section_data)} fields")
            for field_name, field_value in list(section_data.items())[:2]:
                val_type = type(field_value).__name__
                if isinstance(field_value, dict):
                    print(f"         ⚠️ {field_name}: DICT (this will cause React error!)")
                elif isinstance(field_value, list):
                    if field_value and isinstance(field_value[0], dict) and 'label' in field_value[0]:
                        print(f"         ✅ {field_name}: array[{len(field_value)}] of {{label,value}}")
                    else:
                        print(f"         {field_name}: list[{len(field_value)}]")
                else:
                    preview = str(field_value)[:30]
                    print(f"         {field_name}: {val_type} = '{preview}...'")
        else:
            print(f"      {section_name}: {type(section_data).__name__}")

    props_data = {
        "formSchema": form_schema,
        "formData": form_data,
        "patientInfo": patient_info,
        "appointmentInfo": appointment_info,
        "clinicBranding": clinic_branding
    }

    html_content = build_html_template(
        component_name="PdfConsultationForm",
        props_data=props_data,
        clinic_branding=clinic_branding
    )

    return await generate_pdf_from_react(
        html_content=html_content,
        pdf_options={"format": "A4", "landscape": False}
    )


async def generate_analysis_pdf(
    consultation_data: dict,
    patient_info: dict,
    appointment_info: dict,
    clinic_branding: dict = None
) -> BytesIO:
    """
    Generate PDF for clinical analysis report.

    Args:
        consultation_data: Full consultation record with diagnoses
        patient_info: Patient details
        appointment_info: Appointment context
        clinic_branding: Optional clinic design tokens

    Returns:
        BytesIO containing PDF bytes
    """
    if clinic_branding is None:
        clinic_branding = get_default_clinic_branding()

    props_data = {
        "consultationData": consultation_data,
        "patientInfo": patient_info,
        "appointmentInfo": appointment_info,
        "clinicBranding": clinic_branding
    }

    html_content = build_html_template(
        component_name="PdfAnalysisReport",
        props_data=props_data,
        clinic_branding=clinic_branding
    )

    return await generate_pdf_from_react(
        html_content=html_content,
        pdf_options={"format": "A4", "landscape": False}
    )


def build_html_for_doctor_report_card() -> str:
    """
    Build HTML that renders the DoctorReportCard component.
    Uses the component's built-in sample data.

    Returns:
        HTML string ready for Playwright rendering
    """
    # Load React bundle for DoctorReportCard
    bundle_path = Path(__file__).parent / "static" / "doctor-report-card-bundle.js"

    if bundle_path.exists():
        with open(bundle_path, 'r') as f:
            react_bundle = f.read()
    else:
        react_bundle = "console.error('DoctorReportCard bundle not found');"

    # Load index.css (contains medical color variables)
    css_path = Path(__file__).parent.parent / "aneya-frontend" / "src" / "index.css"

    if css_path.exists():
        with open(css_path, 'r') as f:
            index_css = f.read()
    else:
        index_css = ""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>{index_css}</style>
        <style>
            /* Ensure print backgrounds render */
            * {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}

            /* PDF page setup */
            @page {{
                size: A4;
                margin: 0;
            }}

            body {{
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
        <div id="root"></div>

        <!-- DoctorReportCard bundle (includes React) -->
        <script>{react_bundle}</script>

        <script>
            // Render DoctorReportCard component
            if (typeof DoctorReportCardBundle !== 'undefined' && DoctorReportCardBundle.render) {{
                DoctorReportCardBundle.render();
            }} else {{
                document.getElementById('root').innerHTML =
                    '<h1>Error: DoctorReportCard component not found. Type: ' + typeof DoctorReportCardBundle + '</h1>';
            }}
        </script>
    </body>
    </html>
    """

    return html


def build_html_for_doctor_report_card_with_data(
    patient_data: dict,
    pregnancy_history: list
) -> str:
    """
    Build HTML that renders DoctorReportCard with real patient data.

    Args:
        patient_data: Dictionary matching DoctorReportCard PatientData interface
        pregnancy_history: List of pregnancy records

    Returns:
        HTML string ready for Playwright rendering
    """
    # Load React bundle
    bundle_path = Path(__file__).parent / "static" / "doctor-report-card-bundle.js"

    if bundle_path.exists():
        with open(bundle_path, 'r') as f:
            react_bundle = f.read()
    else:
        react_bundle = "console.error('DoctorReportCard bundle not found');"

    # Load index.css
    css_path = Path(__file__).parent.parent / "aneya-frontend" / "src" / "index.css"

    if css_path.exists():
        with open(css_path, 'r') as f:
            index_css = f.read()
    else:
        index_css = ""

    # Serialize data as JSON
    data_json = json.dumps({
        'patientData': patient_data,
        'pregnancyHistory': pregnancy_history
    })

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>{index_css}</style>
        <style>
            /* Ensure print backgrounds render */
            * {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}

            /* PDF page setup */
            @page {{
                size: A4;
                margin: 0;
            }}

            body {{
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
        <div id="root"></div>

        <!-- DoctorReportCard bundle (includes React) -->
        <script>{react_bundle}</script>

        <script>
            // Render DoctorReportCard component with real data
            if (typeof DoctorReportCardBundle !== 'undefined' && DoctorReportCardBundle.render) {{
                const data = {data_json};
                DoctorReportCardBundle.render(data);
            }} else {{
                document.getElementById('root').innerHTML =
                    '<h1>Error: DoctorReportCard component not found</h1>';
            }}
        </script>
    </body>
    </html>
    """

    return html
