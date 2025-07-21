import os
import shutil
import sqlite3
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from typing import Optional
from receipt.utils.ocr import extract_text_easyocr, parse_receipt_text
from receipt.database.models import init_db
import statistics
import csv
import io

logging.basicConfig(level=logging.INFO)
app = FastAPI()
UPLOAD_DIR = 'receipt/uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event('startup')
def startup_event():
    init_db()

@app.post('/upload/')
async def upload_receipt(
    file: UploadFile = File(...),
    lang: str = 'en'
):
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.pdf', '.txt']:
            raise HTTPException(status_code=400, detail='Unsupported file type')
        save_path = f'{UPLOAD_DIR}/{file.filename}'
        with open(save_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
        if ext == '.txt':
            with open(save_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            text = extract_text_easyocr(save_path, lang=lang)
        parsed = parse_receipt_text(text)
        parsed['filename'] = file.filename
        conn = sqlite3.connect('receipt/receipts_final.db')
        c = conn.cursor()
        try:
            c.execute('ALTER TABLE receipts ADD COLUMN currency TEXT')
        except Exception:
            pass
        c.execute('INSERT OR IGNORE INTO receipts (vendor, date, amount, category, filename, currency) VALUES (?, ?, ?, ?, ?, ?)',
                  (parsed['vendor'], parsed['date'], parsed['amount'], parsed['category'], parsed['filename'], parsed['currency']))
        conn.commit()
        conn.close()
        return {'filename': file.filename, 'parsed': parsed}
    except Exception as e:
        logging.exception('Error in upload_receipt')
        raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')

@app.get('/receipts/')
def list_receipts(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: str = 'asc',
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    vendor: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    try:
        conn = sqlite3.connect('receipt/receipts_final.db')
        c = conn.cursor()
        query = 'SELECT id, vendor, date, amount, category, filename, currency FROM receipts WHERE 1=1'
        params = []
        if search:
            query += ' AND (vendor LIKE ? OR category LIKE ? OR filename LIKE ?)'
            params += [f'%{search}%'] * 3
        if vendor:
            query += ' AND vendor = ?'
            params.append(vendor)
        if min_amount is not None:
            query += ' AND amount >= ?'
            params.append(min_amount)
        if max_amount is not None:
            query += ' AND amount <= ?'
            params.append(max_amount)
        if date_from:
            query += ' AND date >= ?'
            params.append(date_from)
        if date_to:
            query += ' AND date <= ?'
            params.append(date_to)
        if category:
            query += ' AND category = ?'
            params.append(category)
        if currency:
            query += ' AND currency = ?'
            params.append(currency)
        if sort_by in ['amount', 'date', 'vendor', 'category', 'currency']:
            query += f' ORDER BY {sort_by} {"ASC" if order=="asc" else "DESC"}'
        offset = (page - 1) * page_size
        query += f' LIMIT ? OFFSET ?'
        params += [page_size, offset]
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return [
            {'id': r[0], 'vendor': r[1], 'date': r[2], 'amount': r[3], 'category': r[4], 'filename': r[5], 'currency': r[6]} for r in rows
        ]
    except Exception as e:
        logging.exception('Error in list_receipts')
        raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')

@app.get('/receipts/export/')
def export_receipts(format: str = 'csv', **filters):
    receipts = list_receipts(**filters, page=1, page_size=10000)
    if format == 'json':
        return receipts
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=receipts[0].keys() if receipts else [])
    writer.writeheader()
    writer.writerows(receipts)
    output.seek(0)
    return StreamingResponse(output, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=receipts.csv'})

@app.get('/receipts/aggregate/')
def aggregate_receipts():
    try:
        conn = sqlite3.connect('receipt/receipts_final.db')
        c = conn.cursor()
        c.execute('SELECT amount, vendor, date, category FROM receipts')
        rows = c.fetchall()
        conn.close()
        amounts = [r[0] for r in rows if r[0] is not None]
        vendors = [r[1] for r in rows if r[1]]
        dates = [r[2] for r in rows if r[2]]
        categories = [r[3] for r in rows if r[3]]
        result = {}
        if amounts:
            result['sum'] = sum(amounts)
            result['mean'] = statistics.mean(amounts)
            result['median'] = statistics.median(amounts)
            try:
                result['mode'] = statistics.mode(amounts)
            except:
                result['mode'] = None
        freq = {}
        for v in vendors:
            freq[v] = freq.get(v, 0) + 1
        result['vendor_frequency'] = freq
        cat_spend = {}
        for r in rows:
            if r[3] and r[0]:
                cat_spend[r[3]] = cat_spend.get(r[3], 0) + r[0]
        result['category_spend'] = cat_spend
        from collections import defaultdict
        import datetime
        monthly = defaultdict(float)
        for r in rows:
            if r[2] and r[0]:
                try:
                    dt = datetime.datetime.strptime(r[2], '%Y-%m-%d')
                    key = dt.strftime('%Y-%m')
                    monthly[key] += r[0]
                except:
                    continue
        result['monthly_spend'] = dict(monthly)
        return result
    except Exception as e:
        logging.exception('Error in aggregate_receipts')
        raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')

@app.patch('/receipts/{receipt_id}/')
def update_receipt(receipt_id: int, data: dict = Body(...)):
    try:
        allowed_fields = {'vendor', 'date', 'amount', 'category', 'currency', 'filename'}
        fields = []
        values = []
        for k, v in data.items():
            if k in allowed_fields:
                fields.append(f'{k} = ?')
                values.append(v)
        if not fields:
            raise HTTPException(status_code=400, detail='No valid fields to update')
        values.append(receipt_id)
        conn = sqlite3.connect('receipt/receipts_final.db')
        c = conn.cursor()
        c.execute(f'UPDATE receipts SET {", ".join(fields)} WHERE id = ?', values)
        conn.commit()
        conn.close()
        return {'status': 'success', 'updated_fields': list(data.keys())}
    except Exception as e:
        logging.exception('Error in update_receipt')
        raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}') 