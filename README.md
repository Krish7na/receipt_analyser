# Receipt Analyzer

## Overview
Receipt Analyzer is a full-stack mini-application for uploading receipts and bills (e.g., electricity, internet, groceries). The app extracts structured data using OCR (EasyOCR) and rule-based logic, then presents summarized insights such as total spend, top vendors, and billing trends. It features a robust backend, a user-friendly Streamlit dashboard, and a normalized SQLite database.

## Features
- Upload receipts/bills in `.jpg`, `.png`, `.pdf`, or `.txt` format
- OCR extraction (EasyOCR, multi-language support)
- Rule-based parsing for vendor, date, amount, category, and currency
- SQLite storage with indexing for fast search
- Search, sort, filter, and pagination
- Aggregation: sum, mean, median, mode, vendor frequency, monthly and category spend
- Streamlit dashboard: tabular view, bar/pie/line charts
- Manual correction: edit parsed fields in the UI and update the backend
- Export: download filtered data as CSV/JSON

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd receipt_analyzer
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   - For PDF OCR, install poppler (see pdf2image docs)
   - For EasyOCR, the first run will download models automatically

4. **Run the backend**
   ```bash
   uvicorn backend.app:app --reload
   ```

5. **Run the frontend (Streamlit)**
   ```bash
   streamlit run frontend/app.py
   ```

## Usage

- Upload receipts via the dashboard
- View, search, and sort records
- Edit any field directly in the UI
- Export filtered data as CSV/JSON
- Visualize vendor frequency (bar), category spend (pie), and monthly spend (line)

## Architecture

- **Backend:** FastAPI (file upload, OCR, parsing, DB, search, aggregation)
- **Database:** SQLite (normalized, indexed)
- **OCR:** EasyOCR, pdf2image
- **Frontend:** Streamlit (upload, table, charts)

## Design Choices

- Modular separation: backend, database, utils, frontend
- Native Python algorithms for search, sort, aggregation
- Exception handling for robust UX
- Manual correction for any field

## Limitations & Assumptions

- Rule-based parsing may not extract all fields perfectly
- Date/amount regexes are basic; can be improved
- No authentication (demo scope)
- Multi-currency and multi-language support are stretch goals

## Further Improvements

- Use AI/ML models for field extraction (instead of rules)
- Support for multi-page and scanned receipts with table extraction
- Automatic currency detection and conversion
- Multi-language UI
- Cloud deployment (e.g., Heroku, AWS, Azure)
- User authentication and multi-user support
- Export to more formats (Excel, PDF)
- Integration with accounting software (e.g., QuickBooks)
- Mobile-friendly UI

## Deliverables

- Full codebase (renamed directory, all code, requirements, and README)
- (Optional) Demo video or screenshots
- README with setup, usage, architecture, and improvement suggestions 
