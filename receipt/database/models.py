from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, create_engine, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from pydantic import BaseModel
from typing import Optional, List
import datetime
import sqlite3

DATABASE_URL = "sqlite:///./receipt/receipts.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Receipt table schema for SQLite
CREATE_RECEIPT_TABLE = '''
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    filename TEXT,
    currency TEXT,
    UNIQUE(vendor, date, amount)
);
'''
CREATE_VENDOR_INDEX = 'CREATE INDEX IF NOT EXISTS idx_vendor ON receipts(vendor);'
CREATE_DATE_INDEX = 'CREATE INDEX IF NOT EXISTS idx_date ON receipts(date);'

def init_db():
    conn = sqlite3.connect('receipt/receipts_final.db')
    c = conn.cursor()
    # Drop the table if it exists (removes all data)
    c.execute('DROP TABLE IF EXISTS receipts;')
    c.execute(CREATE_RECEIPT_TABLE)
    c.execute(CREATE_VENDOR_INDEX)
    c.execute(CREATE_DATE_INDEX)
    conn.commit()
    conn.close()

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    receipts = relationship("Receipt", back_populates="vendor")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    receipts = relationship("Receipt", back_populates="category")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    date = Column(Date)
    amount = Column(Float)
    file_path = Column(String)
    vendor = relationship("Vendor", back_populates="receipts")
    category = relationship("Category", back_populates="receipts")

# Pydantic Schemas
class ReceiptCreate(BaseModel):
    vendor: str
    date: datetime.date
    amount: float
    category: Optional[str]
    file_path: str

class ReceiptResponse(BaseModel):
    id: int
    vendor: str
    date: datetime.date
    amount: float
    category: Optional[str]
    file_path: str
    model_config = {
        "from_attributes": True
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_vendor(db: Session, name: str):
    vendor = db.query(Vendor).filter_by(name=name).first()
    if not vendor:
        vendor = Vendor(name=name)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
    return vendor

def get_or_create_category(db: Session, name: Optional[str]):
    if not name:
        return None
    category = db.query(Category).filter_by(name=name).first()
    if not category:
        category = Category(name=name)
        db.add(category)
        db.commit()
        db.refresh(category)
    return category

def create_receipt(db: Session, data: dict):
    vendor = get_or_create_vendor(db, data["vendor"])
    category = get_or_create_category(db, data.get("category"))
    receipt = Receipt(
        vendor_id=vendor.id,
        category_id=category.id if category else None,
        date=data["date"],
        amount=data["amount"],
        file_path=data["file_path"]
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return ReceiptResponse(
        id=receipt.id,
        vendor=vendor.name,
        date=receipt.date,
        amount=receipt.amount,
        category=category.name if category else None,
        file_path=receipt.file_path
    )

def search_receipts(db: Session, q: Optional[str]):
    query = db.query(Receipt, Vendor, Category).join(Vendor).outerjoin(Category)
    if q:
        query = query.filter(Vendor.name.ilike(f"%{q}%"))
    results = []
    for receipt, vendor, category in query.all():
        results.append(ReceiptResponse(
            id=receipt.id,
            vendor=vendor.name,
            date=receipt.date,
            amount=receipt.amount,
            category=category.name if category else None,
            file_path=receipt.file_path
        ))
    return results

def sort_receipts(receipts: List[ReceiptResponse], sort_by: Optional[str], order: Optional[str]):
    reverse = order == "desc"
    if sort_by:
        receipts.sort(key=lambda x: getattr(x, sort_by), reverse=reverse)
    return receipts

def aggregate_receipts(db: Session):
    total = db.query(func.sum(Receipt.amount)).scalar() or 0
    mean = db.query(func.avg(Receipt.amount)).scalar() or 0
    # Median and mode require more logic
    amounts = [r.amount for r in db.query(Receipt).all()]
    median = sorted(amounts)[len(amounts)//2] if amounts else 0
    mode = max(set(amounts), key=amounts.count) if amounts else 0
    vendor_counts = db.query(Vendor.name, func.count(Receipt.id)).join(Receipt).group_by(Vendor.id).all()
    return {
        "total": total,
        "mean": mean,
        "median": median,
        "mode": mode,
        "vendor_histogram": dict(vendor_counts)
    } 