import easyocr
import os
from pdf2image import convert_from_path
from datetime import datetime
from dateutil import parser as date_parser
import re

# Global cache for EasyOCR readers
_EASYOCR_READERS = {}

def get_easyocr_reader(lang='en'):
    if lang not in _EASYOCR_READERS:
        _EASYOCR_READERS[lang] = easyocr.Reader([lang])
    return _EASYOCR_READERS[lang]

def extract_text_easyocr(file_path, lang='en'):
    reader = get_easyocr_reader(lang)
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png']:
        result = reader.readtext(file_path, detail=0, paragraph=True)
        return '\n'.join(result)
    elif ext == '.pdf':
        images = convert_from_path(file_path)
        text = ''
        for img in images[:5]:  # Limit to first 5 pages for speed
            result = reader.readtext(img, detail=0, paragraph=True)
            text += '\n'.join(result)
        return text
    else:
        raise ValueError('Unsupported file type for OCR')

# Example vendor-category mapping (expand as needed)
VENDOR_CATEGORY_MAP = {
    'Amazon': 'Shopping',
    'Walmart': 'Groceries',
    'Reliance': 'Utilities',
    'Flipkart': 'Shopping',
    'Big Bazaar': 'Groceries',
    'Vodafone': 'Telecom',
    'Airtel': 'Telecom',
    'Tata Power': 'Electricity',
    # Add more as needed
}

CURRENCY_SYMBOLS = {'₹': 'INR', '$': 'USD', '€': 'EUR', '£': 'GBP'}

DATE_PATTERNS = [
    r'(\d{2}[/-]\d{2}[/-]\d{4})',   # 31/12/2023 or 31-12-2023
    r'(\d{4}[/-]\d{2}[/-]\d{2})',   # 2023-12-31
    r'(\d{2}[/-]\d{2}[/-]\d{2})',   # 31/12/23
    r'([A-Za-z]+\\s+\\d{4})',       # December 2023, Jan 2024, etc.
    r'([A-Za-z]+\\s+\\d{1,2},\\s*\\d{4})',  # December 8, 2023
]

AMOUNT_PATTERNS = [
    r'([₹$€£]\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Currency + amount
    r'(Total\s*[:\-]?\s*[₹$€£]?\s?\d+[\.,]\d{2})',
    r'(Amount\s*Due\s*[:\-]?\s*[₹$€£]?\s?\d+[\.,]\d{2})',
    r'(Grand\s*Total\s*[:\-]?\s*[₹$€£]?\s?\d+[\.,]\d{2})',
    r'([\d,]+[\.,]\d{2})',  # Fallback: any number with 2 decimals
]

def parse_receipt_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    vendor = None
    date = None
    amount = None
    category = None
    currency = None

    # Vendor: look for known vendors, else try to find a business name after "INVOICE"
    for i, line in enumerate(lines):
        for v in VENDOR_CATEGORY_MAP:
            if v.lower() in line.lower():
                vendor = v
                break
        if vendor:
            break
    if not vendor:
        # Heuristic: look for line after "INVOICE" or "Invoice"
        for i, line in enumerate(lines):
            if "invoice" in line.lower():
                # Look for next non-empty, non-date, non-number line
                for next_line in lines[i+1:i+4]:
                    if not re.search(r'\d', next_line) and not re.search(r'date', next_line.lower()):
                        vendor = next_line
                        break
                if vendor:
                    break
    if not vendor and lines:
        vendor = lines[0]

    # Date: try all patterns, use dateutil for parsing, fallback to month-year and year
    for pattern in DATE_PATTERNS:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    # Try normal parse
                    date = date_parser.parse(match.group(1), dayfirst=True).strftime('%Y-%m-%d')
                    break
                except Exception:
                    # Try parsing month-year as first of month
                    try:
                        date = date_parser.parse('01 ' + match.group(1)).strftime('%Y-%m-%d')
                        break
                    except Exception:
                        # Try parsing just year if present
                        try:
                            year_match = re.search(r'(20\d{2})', match.group(1))
                            if year_match:
                                date = f'{year_match.group(1)}-01-01'
                                break
                        except Exception:
                            continue
        if date:
            break

    # Amount: look for keywords, then largest value
    found_amounts = []
    for pattern in AMOUNT_PATTERNS:
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                amt_str = match.group(0)
                # Extract currency
                for sym, curr in CURRENCY_SYMBOLS.items():
                    if sym in amt_str:
                        currency = curr
                        amt_str = amt_str.replace(sym, '')
                amt_str = amt_str.replace(',', '').replace('Total', '').replace('Amount Due', '').replace('Grand Total', '').replace(':', '').replace('-', '').strip()
                try:
                    amt = float(re.findall(r'[\d.]+', amt_str)[0])
                    found_amounts.append(amt)
                except Exception:
                    continue
    if found_amounts:
        amount = max(found_amounts)  # Use the largest value as total

    # Category: map from vendor
    if vendor and vendor in VENDOR_CATEGORY_MAP:
        category = VENDOR_CATEGORY_MAP[vendor]
    else:
        category = 'Other'

    # Do NOT raise error if fields are missing; just return what you have
    return {
        'vendor': vendor,
        'date': date,
        'amount': amount,
        'category': category,
        'currency': currency or 'Unknown'
    } 