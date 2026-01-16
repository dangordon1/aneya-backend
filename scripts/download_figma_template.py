#!/usr/bin/env python3
"""
Download and analyze Figma template for PDF generation

This script fetches a Figma file and extracts:
- Layout structure (frames, sections, spacing)
- Typography definitions (text styles, sizes)
- Color variables
- Component definitions

Output: JSON template file that pdf_generator.py can use
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

from clients.figma_mcp_client import FigmaClient, FigmaTokenExtractor


async def download_figma_template(file_key: str, output_path: str):
    """
    Download Figma template and convert to JSON

    Args:
        file_key: Figma file key (from URL)
        output_path: Where to save the JSON template
    """
    print(f"🎨 Downloading Figma file: {file_key}")

    try:
        # Initialize Figma client
        client = FigmaClient()

        # Fetch file data
        print("📥 Fetching file data from Figma API...")
        file_data = await client.get_file(file_key)

        print(f"✅ File fetched: {file_data.get('name', 'Unknown')}")

        # Fetch variables (colors, spacing, etc.)
        print("📥 Fetching design variables...")
        try:
            variables = await client.get_variables(file_key)
            print(f"✅ Variables fetched")
        except Exception as e:
            print(f"⚠️  No variables found (this is okay): {e}")
            variables = {}

        # Extract design tokens
        print("\n🔍 Extracting design tokens...")
        colors = FigmaTokenExtractor.extract_colors(variables)
        typography = FigmaTokenExtractor.extract_typography(file_data)
        spacing = FigmaTokenExtractor.extract_spacing(file_data)
        layout = FigmaTokenExtractor.extract_layout(file_data)

        print(f"  Colors: {len(colors)} found")
        print(f"  Typography: {len(typography)} styles found")
        print(f"  Spacing: {len(spacing)} values found")
        print(f"  Layout: {layout}")

        # Extract page structure
        print("\n🔍 Extracting page structure...")
        document = file_data.get('document', {})
        pages = document.get('children', [])

        template_structure = {
            "file_name": file_data.get('name', 'Unknown'),
            "file_key": file_key,
            "version": file_data.get('version', 'unknown'),
            "design_tokens": {
                "colors": colors,
                "typography": typography,
                "spacing": spacing,
                "layout": layout
            },
            "pages": []
        }

        # Process each page
        for page in pages:
            page_info = {
                "name": page.get('name', 'Untitled'),
                "id": page.get('id'),
                "frames": []
            }

            # Extract frames from page
            for frame in page.get('children', []):
                if frame.get('type') in ['FRAME', 'COMPONENT', 'COMPONENT_SET']:
                    frame_info = extract_frame_info(frame)
                    page_info['frames'].append(frame_info)

            template_structure['pages'].append(page_info)

        # Save to JSON
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(template_structure, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Template saved to: {output_file}")
        print(f"📊 Structure:")
        print(f"  - {len(template_structure['pages'])} pages")
        total_frames = sum(len(p['frames']) for p in template_structure['pages'])
        print(f"  - {total_frames} frames/components")

        return template_structure

    except Exception as e:
        print(f"\n❌ Error downloading Figma template: {e}")
        import traceback
        traceback.print_exc()
        raise


def extract_frame_info(frame: dict) -> dict:
    """Extract relevant information from a Figma frame"""
    frame_info = {
        "name": frame.get('name', 'Untitled'),
        "id": frame.get('id'),
        "type": frame.get('type'),
        "width": frame.get('absoluteBoundingBox', {}).get('width', 0),
        "height": frame.get('absoluteBoundingBox', {}).get('height', 0),
        "background_color": extract_background_color(frame),
        "children": []
    }

    # Recursively extract children
    for child in frame.get('children', []):
        child_info = extract_node_info(child)
        if child_info:
            frame_info['children'].append(child_info)

    return frame_info


def extract_node_info(node: dict) -> dict:
    """Extract information from any Figma node"""
    node_type = node.get('type')

    base_info = {
        "name": node.get('name', 'Untitled'),
        "id": node.get('id'),
        "type": node_type,
        "visible": node.get('visible', True)
    }

    # Add type-specific information
    if node_type == 'TEXT':
        base_info.update({
            "text": node.get('characters', ''),
            "font_family": node.get('style', {}).get('fontFamily', 'Helvetica'),
            "font_size": node.get('style', {}).get('fontSize', 10),
            "font_weight": node.get('style', {}).get('fontWeight', 400),
            "text_align": node.get('style', {}).get('textAlignHorizontal', 'LEFT'),
            "color": extract_color(node.get('fills', []))
        })
    elif node_type == 'RECTANGLE':
        base_info.update({
            "fill": extract_color(node.get('fills', [])),
            "stroke": extract_color(node.get('strokes', [])),
            "corner_radius": node.get('cornerRadius', 0)
        })
    elif node_type in ['FRAME', 'GROUP', 'COMPONENT']:
        base_info['children'] = [extract_node_info(child) for child in node.get('children', [])]

    # Add dimensions if available
    if 'absoluteBoundingBox' in node:
        bbox = node['absoluteBoundingBox']
        base_info.update({
            "x": bbox.get('x', 0),
            "y": bbox.get('y', 0),
            "width": bbox.get('width', 0),
            "height": bbox.get('height', 0)
        })

    return base_info


def extract_background_color(frame: dict) -> str:
    """Extract background color from frame"""
    fills = frame.get('backgroundColor')
    if fills:
        r = int(fills.get('r', 0) * 255)
        g = int(fills.get('g', 0) * 255)
        b = int(fills.get('b', 0) * 255)
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#ffffff"


def extract_color(fills: list) -> str:
    """Extract color from Figma fills/strokes"""
    if not fills or len(fills) == 0:
        return "transparent"

    fill = fills[0]
    if fill.get('type') == 'SOLID':
        color = fill.get('color', {})
        r = int(color.get('r', 0) * 255)
        g = int(color.get('g', 0) * 255)
        b = int(color.get('b', 0) * 255)
        opacity = fill.get('opacity', 1.0)

        if opacity < 1.0:
            return f"rgba({r}, {g}, {b}, {opacity})"
        else:
            return f"#{r:02x}{g:02x}{b:02x}"

    return "transparent"


async def main():
    """Main entry point"""
    # Figma file key from URL: https://www.figma.com/make/kKbl1fqJyRqEO990tOSPWs/...
    file_key = "kKbl1fqJyRqEO990tOSPWs"
    output_path = "templates/figma_doctor_report_template.json"

    print("=" * 70)
    print("Figma Template Downloader for Aneya PDF Generator")
    print("=" * 70)
    print()

    # Check for Figma access token
    if not os.getenv('FIGMA_ACCESS_TOKEN') or os.getenv('FIGMA_ACCESS_TOKEN') == 'your_figma_personal_access_token':
        print("❌ ERROR: Figma Personal Access Token not configured!")
        print()
        print("Please follow these steps:")
        print("1. Go to https://www.figma.com/settings")
        print("2. Scroll down to 'Personal access tokens'")
        print("3. Click 'Generate new token'")
        print("4. Copy the token")
        print("5. Add it to /aneya-backend/.env:")
        print("   FIGMA_ACCESS_TOKEN=your_token_here")
        print()
        print("Then run this script again.")
        sys.exit(1)

    try:
        await download_figma_template(file_key, output_path)
        print("\n" + "=" * 70)
        print("✅ SUCCESS! Template downloaded and converted to JSON")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Review the template: cat templates/figma_doctor_report_template.json")
        print("2. Test PDF generation with the template")
        print("3. Customize colors per clinic via API")
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ FAILED")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
