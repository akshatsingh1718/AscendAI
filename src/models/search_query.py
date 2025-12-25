from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .base import Base

class SearchQuery(Base):
    """Track search queries executed"""
    __tablename__ = 'search_queries'
    
    id = Column(Integer, primary_key=True)
    query = Column(String(255), nullable=False)
    leads_found = Column(Integer, default=0)
    executed_at = Column(DateTime, default=datetime.utcnow)
    raw_response = Column(Text)
    
    def __repr__(self):
        return f"<SearchQuery(query='{self.query}', leads={self.leads_found})>"

