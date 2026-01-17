"""
Design Token Model
Represents extracted design tokens from Figma and database
Colors come from database (per-clinic), layout/typography from Figma
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional
from reportlab.lib.colors import HexColor
from functools import lru_cache
import json
from pathlib import Path
import os


class ColorTokens(BaseModel):
    """Color design tokens"""
    primary: str = "#0c3555"
    accent: str = "#1d9e99"
    text: str = "#6b7280"
    text_light: str = "#d1d5db"
    background_light: str = "#f6f5ee"
    background_white: str = "#ffffff"

    def to_hex_colors(self) -> Dict[str, HexColor]:
        """Convert to ReportLab HexColor objects"""
        return {
            "primary": HexColor(self.primary),
            "accent": HexColor(self.accent),
            "text": HexColor(self.text),
            "text_light": HexColor(self.text_light),
            "background_light": HexColor(self.background_light),
            "background_white": HexColor(self.background_white)
        }


class TypographyToken(BaseModel):
    """Single typography token"""
    fontFamily: str = "Helvetica"
    fontSize: int = 10
    fontWeight: str = "Normal"  # "Normal" or "Bold"
    lineHeight: float = 12.0

    def to_reportlab_font(self) -> tuple[str, int]:
        """Convert to ReportLab (fontName, fontSize)"""
        font_name = self.fontFamily
        if self.fontWeight == "Bold":
            font_name = f"{font_name}-Bold"
        return (font_name, self.fontSize)


class TypographyTokens(BaseModel):
    """Typography design tokens"""
    heading_1: TypographyToken = TypographyToken(fontSize=20, fontWeight="Bold")
    heading_2: TypographyToken = TypographyToken(fontSize=14, fontWeight="Bold")
    body: TypographyToken = TypographyToken(fontSize=10)
    body_bold: TypographyToken = TypographyToken(fontSize=10, fontWeight="Bold")
    caption: TypographyToken = TypographyToken(fontSize=8)
    table_header: TypographyToken = TypographyToken(fontSize=7, fontWeight="Bold")
    table_cell: TypographyToken = TypographyToken(fontSize=7)


class SpacingTokens(BaseModel):
    """Spacing design tokens (in cm)"""
    margin_top: float = 2.0
    margin_left: float = 2.0
    margin_right: float = 1.0
    margin_bottom: float = 1.5
    section_spacing: float = 0.6
    field_spacing: float = 0.4
    line_spacing: float = 0.4
    table_padding: float = 0.3


class LayoutTokens(BaseModel):
    """Layout design tokens"""
    page_width: float = 21.0  # cm (A4)
    page_height: float = 29.7  # cm (A4)
    two_column_left_x: float = 2.0
    two_column_right_x: float = 11.0
    three_column_col1_x: float = 2.0
    three_column_col2_x: float = 7.8
    three_column_col3_x: float = 13.6


class DesignTokens(BaseModel):
    """Complete design token set"""
    colors: ColorTokens = ColorTokens()
    typography: TypographyTokens = TypographyTokens()
    spacing: SpacingTokens = SpacingTokens()
    layout: LayoutTokens = LayoutTokens()

    @classmethod
    async def from_figma(cls, file_key: str) -> "DesignTokens":
        """Load design tokens from Figma file"""
        from clients.figma_mcp_client import FigmaClient, FigmaTokenExtractor

        client = FigmaClient()
        file_data = await client.get_file(file_key)
        variables = await client.get_variables(file_key)

        # Extract tokens
        colors_dict = FigmaTokenExtractor.extract_colors(variables)
        typography_dict = FigmaTokenExtractor.extract_typography(file_data)
        spacing_dict = FigmaTokenExtractor.extract_spacing(file_data)
        layout_dict = FigmaTokenExtractor.extract_layout(file_data)

        # Build token model (merge with defaults)
        return cls(
            colors=ColorTokens(**{k: v for k, v in colors_dict.items() if hasattr(ColorTokens, k)}),
            typography=TypographyTokens(**{
                k: TypographyToken(**v) for k, v in typography_dict.items()
                if hasattr(TypographyTokens, k)
            }),
            spacing=SpacingTokens(**spacing_dict),
            layout=LayoutTokens(**layout_dict)
        )

    @classmethod
    def default(cls) -> "DesignTokens":
        """Get default Aneya design tokens"""
        return cls()

    @classmethod
    async def from_clinic(cls, doctor_id: str, figma_file_key: Optional[str] = None) -> "DesignTokens":
        """Load design tokens for a specific clinic

        Colors come from database (per-clinic), with fallback to Aneya defaults
        Typography/spacing/layout come from Figma if file_key provided, else use defaults

        Args:
            doctor_id: UUID of the doctor/clinic
            figma_file_key: Optional Figma file key for layout templates

        Returns:
            DesignTokens with clinic colors and optional Figma layout
        """
        # Load colors from database
        from supabase import create_client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            print("⚠️  Supabase credentials not found, using default colors")
            colors = ColorTokens()
        else:
            supabase = create_client(supabase_url, supabase_key)

            # Query clinic color scheme
            response = supabase.table("clinic_color_schemes").select("*").eq("doctor_id", doctor_id).single().execute()

            if response.data:
                # Use clinic-specific colors
                colors = ColorTokens(
                    primary=response.data.get("primary_color", "#0c3555"),
                    accent=response.data.get("accent_color", "#1d9e99"),
                    text=response.data.get("text_color", "#6b7280"),
                    text_light=response.data.get("text_light_color", "#d1d5db"),
                    background_light=response.data.get("background_light_color", "#f6f5ee"),
                    background_white=response.data.get("background_white_color", "#ffffff")
                )
                print(f"✅ Loaded custom color scheme for clinic {doctor_id}")
            else:
                # No custom colors, use defaults
                colors = ColorTokens()
                print(f"ℹ️  No custom colors for clinic {doctor_id}, using Aneya defaults")

        # Load typography/spacing/layout from Figma if provided
        if figma_file_key:
            try:
                figma_tokens = await cls.from_figma(figma_file_key)
                return cls(
                    colors=colors,
                    typography=figma_tokens.typography,
                    spacing=figma_tokens.spacing,
                    layout=figma_tokens.layout
                )
            except Exception as e:
                print(f"⚠️  Failed to load Figma tokens: {e}, using defaults")
                return cls(colors=colors)
        else:
            # Use default typography/spacing/layout
            return cls(colors=colors)

    @classmethod
    def from_cache(cls, file_key: str) -> Optional["DesignTokens"]:
        """Load tokens from cache if available"""
        cache_path = Path(f".cache/figma_tokens/{file_key}.json")

        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception as e:
                print(f"⚠️  Failed to load tokens from cache: {e}")
                return None

        return None

    def save_to_cache(self, file_key: str):
        """Save tokens to cache"""
        cache_path = Path(f".cache/figma_tokens/{file_key}.json")

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(self.dict(), f, indent=2)
            print(f"✅ Tokens cached to {cache_path}")
        except Exception as e:
            print(f"⚠️  Failed to save tokens to cache: {e}")


def get_clinic_design_tokens(clinic_id: str, supabase_client=None) -> dict:
    """
    Fetch clinic design tokens (logos, colors, contact info) from database.
    Returns a simple dict suitable for React component props.
    Falls back to Aneya defaults if not configured.

    Args:
        clinic_id: UUID of the clinic
        supabase_client: Optional Supabase client instance

    Returns:
        Dict with logo_url, primary_color, accent_color, background_color,
        clinic_name, and contact_info
    """
    # Default Aneya branding
    default_branding = {
        "logo_url": None,
        "primary_color": "#0c3555",
        "accent_color": "#1d9e99",
        "background_color": "#f6f5ee",
        "clinic_name": "Healthcare Medical Center",
        "contact_info": {
            "address": "456 Hospital Avenue",
            "phone": "(555) 123-4567",
            "fax": None
        }
    }

    if not supabase_client:
        print("⚠️  No Supabase client provided, using default branding")
        return default_branding

    try:
        # Query clinic information
        clinic_response = supabase_client.table("clinics").select("*").eq("id", clinic_id).single().execute()

        if not clinic_response.data:
            print(f"ℹ️  Clinic {clinic_id} not found, using default branding")
            return default_branding

        clinic_data = clinic_response.data

        # Try to get clinic-specific design tokens/color scheme
        design_tokens_response = supabase_client.table("clinic_design_tokens").select("*").eq(
            "clinic_id", clinic_id
        ).execute()

        # Merge clinic data with design tokens
        branding = {
            "logo_url": None,
            "primary_color": default_branding["primary_color"],
            "accent_color": default_branding["accent_color"],
            "background_color": default_branding["background_color"],
            "clinic_name": clinic_data.get("name", default_branding["clinic_name"]),
            "contact_info": {
                "address": clinic_data.get("address"),
                "phone": clinic_data.get("phone"),
                "fax": clinic_data.get("fax")
            }
        }

        # If design tokens exist, override colors and logo
        if design_tokens_response.data and len(design_tokens_response.data) > 0:
            tokens = design_tokens_response.data[0]
            branding["logo_url"] = tokens.get("logo_url")
            branding["primary_color"] = tokens.get("primary_color", branding["primary_color"])
            branding["accent_color"] = tokens.get("accent_color", branding["accent_color"])
            branding["background_color"] = tokens.get("background_color", branding["background_color"])
            print(f"✅ Loaded custom design tokens for clinic {clinic_id}")
        else:
            print(f"ℹ️  No custom design tokens for clinic {clinic_id}, using clinic info with default colors")

        return branding

    except Exception as e:
        print(f"⚠️  Error fetching clinic branding: {e}, using defaults")
        return default_branding
