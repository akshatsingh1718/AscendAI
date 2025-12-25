from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .base import Base

class Lead(Base):
    """SQLAlchemy model for storing leads"""
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(100))
    description = Column(Text)
    why_payu = Column(Text)
    source_url = Column(String(500))
    company_size = Column(String(50))
    search_query = Column(String(255))
    lead_score = Column(Float, default=0.0)
    status = Column(String(50), default='new')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_data = Column(Text)  # Store original JSON
    
    def __repr__(self):
        return f"<Lead(company_name='{self.company_name}', industry='{self.industry}')>"
