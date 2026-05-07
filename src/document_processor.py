"""
Document processing module for OCR and text extraction
"""
import os
from typing import Tuple, Optional
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import PyPDF2
from PIL import Image
import pytesseract


class DocumentProcessor:
    """Handles multi-format document processing"""
    
    def __init__(self, tesseract_path: Optional[str] = None):
        """Initialize document processor"""
        if tesseract_path:
            pytesseract.pytesseract.pytesseract_cmd = tesseract_path
    
    def extract_from_pdf(self, pdf_path: str) -> Tuple[str, float]:
        """
        Extract text from PDF
        Returns: (text, confidence_score)
        """
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            
            # Confidence based on text extraction success
            confidence = 0.9 if text.strip() else 0.3
            return text, confidence
        except Exception as e:
            return "", 0.0
    
    def extract_from_image(self, image_path: str) -> Tuple[str, float]:
        """
        Extract text from image using OCR
        Returns: (text, confidence_score)
        """
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            
            # Confidence based on OCR quality
            confidence = 0.7 if text.strip() else 0.2
            return text, confidence
        except Exception as e:
            return "", 0.0

    def extract_from_docx(self, docx_path: str) -> Tuple[str, float]:
        """
        Extract text from DOCX files using the zipped XML document body.
        Returns: (text, confidence_score)
        """
        try:
            with zipfile.ZipFile(docx_path) as docx:
                xml_bytes = docx.read("word/document.xml")

            root = ET.fromstring(xml_bytes)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for paragraph in root.findall(".//w:p", ns):
                parts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
                if parts:
                    paragraphs.append("".join(parts))

            text = "\n".join(paragraphs)
            confidence = 0.85 if text.strip() else 0.25
            return text, confidence
        except Exception:
            return "", 0.0
    
    def process_document(self, file_path: str) -> Tuple[str, float, int]:
        """
        Process any supported document format
        Returns: (text, confidence, page_count)
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            text, conf = self.extract_from_pdf(file_path)
            page_count = self._get_pdf_page_count(file_path)
            return text, conf, page_count

        elif file_ext == '.docx':
            text, conf = self.extract_from_docx(file_path)
            return text, conf, max(1, text.count("\n") // 35 + 1)
        
        elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff']:
            text, conf = self.extract_from_image(file_path)
            return text, conf, 1
        
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total page count of PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                return len(reader.pages)
        except:
            return 0
