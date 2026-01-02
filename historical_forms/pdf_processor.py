"""
PDF Processing Utility for Historical Form Imports
Extracts text and converts PDF pages to images for OCR processing
"""

import io
import base64
from typing import List, Dict, Any, Optional
from PyPDF2 import PdfReader
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process PDF files for form data extraction"""

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """
        Extract all text content from a PDF file

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Extracted text content
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)

            text_content = []
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_content.append(f"--- Page {page_num + 1} ---\n{text}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                    continue

            return "\n\n".join(text_content)

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise ValueError(f"Invalid or corrupted PDF file: {e}")

    @staticmethod
    def get_pdf_page_count(pdf_bytes: bytes) -> int:
        """Get the number of pages in a PDF"""
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to count PDF pages: {e}")
            raise ValueError(f"Invalid PDF file: {e}")

    @staticmethod
    def extract_pdf_metadata(pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PDF (author, creation date, etc.)

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Dictionary containing PDF metadata
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)

            metadata = {
                "page_count": len(reader.pages),
                "has_text": False,
            }

            # Check if PDF has extractable text
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    metadata["has_text"] = True
                    break

            # Extract PDF metadata if available
            if reader.metadata:
                metadata.update({
                    "author": reader.metadata.get("/Author", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "title": reader.metadata.get("/Title", ""),
                    "creation_date": reader.metadata.get("/CreationDate", ""),
                })

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return {"page_count": 0, "has_text": False, "error": str(e)}

    @staticmethod
    def process_pdf_for_vision_api(
        pdf_bytes: bytes,
        max_pages: int = 10
    ) -> Dict[str, Any]:
        """
        Process PDF for Claude Vision API analysis
        Extracts both text and metadata

        Args:
            pdf_bytes: PDF file as bytes
            max_pages: Maximum number of pages to process

        Returns:
            Dictionary with extracted text, metadata, and processing info
        """
        try:
            metadata = PDFProcessor.extract_pdf_metadata(pdf_bytes)
            page_count = metadata.get("page_count", 0)

            if page_count == 0:
                raise ValueError("PDF has no pages")

            # Extract text content
            text_content = PDFProcessor.extract_text_from_pdf(pdf_bytes)

            # Limit pages if needed
            pages_processed = min(page_count, max_pages)

            return {
                "success": True,
                "text_content": text_content,
                "metadata": metadata,
                "page_count": page_count,
                "pages_processed": pages_processed,
                "has_extractable_text": metadata.get("has_text", False),
                "truncated": page_count > max_pages,
            }

        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            return {
                "success": False,
                "error": str(e),
                "text_content": "",
                "metadata": {},
                "page_count": 0,
                "pages_processed": 0,
            }


def is_pdf_file(file_bytes: bytes) -> bool:
    """Check if file is a valid PDF based on magic bytes"""
    return file_bytes[:4] == b'%PDF'


def get_file_type_from_bytes(file_bytes: bytes) -> str:
    """
    Detect file type from magic bytes

    Returns:
        File type: 'pdf', 'jpeg', 'png', 'heic', or 'unknown'
    """
    if not file_bytes or len(file_bytes) < 12:
        return 'unknown'

    # PDF
    if file_bytes[:4] == b'%PDF':
        return 'pdf'

    # JPEG
    if file_bytes[:2] == b'\xff\xd8':
        return 'jpeg'

    # PNG
    if file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'

    # HEIC/HEIF (check ftyp box)
    if len(file_bytes) >= 12:
        if file_bytes[4:8] == b'ftyp':
            ftyp = file_bytes[8:12]
            if ftyp in [b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis',
                       b'hevm', b'hevs', b'mif1', b'msf1']:
                return 'heic'

    return 'unknown'
