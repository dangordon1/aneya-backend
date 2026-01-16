"""
Figma API Client for extracting design tokens and component definitions
Uses Figma REST API to fetch file data and extract visual properties
"""

import httpx
import os
from typing import Dict, Any, List, Optional
from functools import lru_cache


class FigmaClient:
    """Client for Figma REST API to extract design data"""

    BASE_URL = "https://api.figma.com/v1"

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("FIGMA_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("FIGMA_ACCESS_TOKEN environment variable required")

    async def get_file(self, file_key: str) -> Dict[str, Any]:
        """Get complete Figma file data"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/files/{file_key}",
                headers={"X-Figma-Token": self.access_token},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_component(self, file_key: str, node_id: str) -> Dict[str, Any]:
        """Get specific component by node ID"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/files/{file_key}/nodes",
                params={"ids": node_id},
                headers={"X-Figma-Token": self.access_token},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_styles(self, file_key: str) -> Dict[str, Any]:
        """Get all styles (colors, text, effects) from file"""
        file_data = await self.get_file(file_key)
        return file_data.get("styles", {})

    async def get_variables(self, file_key: str) -> Dict[str, Any]:
        """Get design variables (colors, numbers, strings)"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/files/{file_key}/variables/local",
                headers={"X-Figma-Token": self.access_token},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()


class FigmaTokenExtractor:
    """Extract design tokens from Figma file data"""

    @staticmethod
    def extract_colors(variables: Dict[str, Any]) -> Dict[str, str]:
        """Extract color tokens from Figma variables

        Returns dict like:
        {
            "primary": "#0c3555",
            "accent": "#1d9e99",
            "text": "#6b7280",
            ...
        }
        """
        colors = {}

        for var_id, var_data in variables.get("meta", {}).get("variables", {}).items():
            if var_data.get("resolvedType") == "COLOR":
                name = var_data.get("name", "").lower().replace(" ", "_")

                # Get color value from valuesByMode
                modes = var_data.get("valuesByMode", {})
                if modes:
                    mode_id = list(modes.keys())[0]
                    rgba = modes[mode_id]

                    # Convert RGBA (0-1) to hex
                    r = int(rgba.get("r", 0) * 255)
                    g = int(rgba.get("g", 0) * 255)
                    b = int(rgba.get("b", 0) * 255)
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"

                    colors[name] = hex_color

        return colors

    @staticmethod
    def extract_typography(file_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract typography tokens from text styles

        Returns dict like:
        {
            "heading_1": {
                "fontFamily": "Helvetica",
                "fontSize": 20,
                "fontWeight": "Bold",
                "lineHeight": 24
            },
            ...
        }
        """
        typography = {}

        # Look for text styles in document
        def find_text_styles(node: Dict[str, Any], path: str = ""):
            if node.get("type") == "TEXT":
                style = node.get("style", {})
                name = node.get("name", "").lower().replace(" ", "_")

                typography[name] = {
                    "fontFamily": style.get("fontFamily", "Helvetica"),
                    "fontSize": style.get("fontSize", 10),
                    "fontWeight": style.get("fontWeight", 400),
                    "lineHeight": style.get("lineHeightPx", style.get("fontSize", 10) * 1.2)
                }

            # Recurse through children
            for child in node.get("children", []):
                find_text_styles(child, f"{path}/{node.get('name', '')}")

        document = file_data.get("document", {})
        find_text_styles(document)

        return typography

    @staticmethod
    def extract_spacing(file_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract spacing tokens from auto-layout frames

        Returns dict like:
        {
            "margin_top": 2.0,  # in cm
            "margin_left": 2.0,
            "section_spacing": 0.6,
            ...
        }
        """
        spacing = {}

        # Default spacings (will be overridden by Figma values if found)
        spacing["margin_top"] = 2.0
        spacing["margin_left"] = 2.0
        spacing["margin_right"] = 2.0
        spacing["section_spacing"] = 0.6
        spacing["field_spacing"] = 0.4
        spacing["line_height"] = 0.4

        # Look for spacing components in Figma
        # (Implementation depends on how spacing is structured in Figma)

        return spacing

    @staticmethod
    def extract_layout(file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract layout configuration from Figma frames

        Returns dict like:
        {
            "page_width": 21.0,  # A4 width in cm
            "page_height": 29.7,  # A4 height in cm
            "columns": {
                "two_column": {
                    "left_x": 2.0,
                    "right_x": 11.0,
                    "width": 8.5
                },
                ...
            }
        }
        """
        layout = {
            "page_width": 21.0,
            "page_height": 29.7,
            "columns": {
                "two_column": {
                    "left_x": 2.0,
                    "right_x": 11.0,
                    "width": 8.5
                },
                "three_column": {
                    "col1_x": 2.0,
                    "col2_x": 7.8,
                    "col3_x": 13.6,
                    "width": 5.5
                }
            }
        }

        # Extract from Figma if structured appropriately

        return layout
