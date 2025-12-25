"""
FastAPI application exposing lead generation and lead assessment endpoints.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import threading

from lead_generation import PayULeadGenerator
from lead_assessor import LeadAssessor
from models.lead import Lead
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(override=True)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app
app = FastAPI(
    title="AscendAI Lead Management API",
    description="API for generating and assessing leads using AI",
    version="0.1.0"
)

# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class LeadGenerationRequest(BaseModel):
    """Request model for initiating lead generation."""
    search_queries: Optional[List[str]] = Field(
        None, 
        description="Optional custom search queries. If not provided, defaults will be used."
    )
    limit: Optional[int] = Field(
        10,
        description="Maximum number of leads to generate"
    )


class LeadGenerationResponse(BaseModel):
    """Response model for lead generation."""
    status: str
    message: str
    leads_count: int
    leads: List[Dict[str, Any]]


class LeadAssessmentRequest(BaseModel):
    """Request model for assessing leads."""
    lead_ids: Optional[List[int]] = Field(
        None,
        description="Specific lead IDs to assess. If not provided, assesses all unassessed leads."
    )
    limit: Optional[int] = Field(
        5,
        description="Maximum number of leads to assess"
    )


class LeadAssessmentResponse(BaseModel):
    """Response model for lead assessment."""
    status: str
    message: str
    assessments_count: int
    assessments: List[Dict[str, Any]]


class LeadDetailResponse(BaseModel):
    """Response model for retrieving a single lead with assessment."""
    id: int
    company_name: str
    industry: str
    source_url: str
    description: str
    lead_score: float
    status: str
    assessment: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Lead Generation Endpoints
# ============================================================================

@app.post("/leads/generate", response_model=LeadGenerationResponse)
async def generate_leads(request: LeadGenerationRequest) -> LeadGenerationResponse:
    """
    Generate new leads using AI-powered search and analysis.
    
    This endpoint uses the PayULeadGenerator to search the web, identify potential
    PayU customers, and save them to the database.
    
    Args:
        request: LeadGenerationRequest with optional custom search queries and limit
        
    Returns:
        LeadGenerationResponse with status and list of generated leads
    """
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise HTTPException(
                status_code=500,
                detail="DATABASE_URL environment variable not set"
            )
        
        generator = PayULeadGenerator(db_path= os.environ.get("DATABASE_PATH", "payu_leads.db"))
        
        # Use custom queries if provided, otherwise use defaults
        # queries = request.search_queries or generator.search_queries()
        
        leads = []
        # for query in queries[:request.limit]:
        #     logger.info(f"Generating leads for query: {query}")
        #     try:
                # Call the generator's main method if available, or search_with_serper
            #     result = generator.run_lead_generation(max_queries=1, delay=3)
            #     if result:
            #         leads.extend(result)
            # except Exception as e:
            #     logger.warning(f"Failed to generate leads for query '{query}': {e}")
            #     continue
        # start generation in a background thread so the request returns immediately
        def _bg_run(max_queries: int, delay: int):
            try:
                logger.info("Background lead generation started: max_queries=%s", max_queries)
                result = generator.run_lead_generation(max_queries=max_queries, delay=delay)
                total = len(result.get('leads', [])) if isinstance(result, dict) else 0
                logger.info("Background lead generation finished: generated=%s", total)
            except Exception:
                logger.exception("Background lead generation failed")

        thread = threading.Thread(target=_bg_run, args=(request.limit, 3), daemon=True)
        thread.start()

        return LeadGenerationResponse(
            status="started",
            message="Lead generation has been started in background",
            leads_count=0,
            leads=[]
        )
    except Exception as e:
        logger.exception("Lead generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Lead generation failed: {str(e)}"
        )


# ============================================================================
# Lead Assessment Endpoints
# ============================================================================

@app.post("/leads/assess", response_model=LeadAssessmentResponse)
async def assess_leads(request: LeadAssessmentRequest) -> LeadAssessmentResponse:
    """
    Assess leads using web research and LLM analysis.
    
    This endpoint evaluates leads on multiple factors including tech stack,
    business age, company scale, and various readiness/quality scores.
    
    Args:
        request: LeadAssessmentRequest with optional lead_ids and limit
        
    Returns:
        LeadAssessmentResponse with status and list of assessments
    """
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise HTTPException(
                status_code=500,
                detail="DATABASE_URL environment variable not set"
            )
        
        assessor = LeadAssessor(db_url=db_url)
        
        # If specific lead IDs provided, assess only those; otherwise assess all unassessed
        if request.lead_ids:
            assessments = []
            for lead_id in request.lead_ids:
                lead = assessor.session.query(Lead).filter(Lead.id == lead_id).first()
                if not lead:
                    logger.warning(f"Lead with ID {lead_id} not found")
                    continue
                assessment = assessor.assess_lead(lead)
                assessor.persist_assessment(lead, assessment)
                assessments.append({
                    "lead_id": lead.id,
                    "company_name": lead.company_name,
                    "assessment": assessment
                })
        else:
            assessments = assessor.assess_all_leads(limit=request.limit)
        
        logger.info(f"Assessed {len(assessments)} leads")
        return LeadAssessmentResponse(
            status="success",
            message=f"Successfully assessed {len(assessments)} leads",
            assessments_count=len(assessments),
            assessments=assessments
        )
    except Exception as e:
        logger.exception("Lead assessment failed")
        raise HTTPException(
            status_code=500,
            detail=f"Lead assessment failed: {str(e)}"
        )


# ============================================================================
# Lead Retrieval Endpoints
# ============================================================================

@app.get("/leads/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(lead_id: int) -> LeadDetailResponse:
    """
    Retrieve a single lead with its assessment details.
    
    Args:
        lead_id: ID of the lead to retrieve
        
    Returns:
        LeadDetailResponse with lead and assessment information
    """
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise HTTPException(
                status_code=500,
                detail="DATABASE_URL environment variable not set"
            )
        
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=404,
                detail=f"Lead with ID {lead_id} not found"
            )
        
        # Parse assessment from raw_data if available
        assessment = None
        if lead.raw_data:
            try:
                raw = json.loads(lead.raw_data)
                assessment = raw.get("assessment")
            except Exception:
                pass
        
        return LeadDetailResponse(
            id=lead.id,
            company_name=lead.company_name,
            industry=lead.industry or "",
            source_url=lead.source_url or "",
            description=lead.description or "",
            lead_score=lead.lead_score or 0.0,
            status=lead.status or "new",
            assessment=assessment,
            created_at=lead.created_at.isoformat() if lead.created_at else "",
            updated_at=lead.updated_at.isoformat() if lead.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve lead {lead_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve lead: {str(e)}"
        )


@app.get("/leads", response_model=Dict[str, Any])
async def list_leads(
    status: Optional[str] = Query(None, description="Filter by lead status (new, assessed)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of leads to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
) -> Dict[str, Any]:
    """
    List all leads with optional filtering.
    
    Args:
        status: Optional filter by lead status
        limit: Maximum number of leads to return
        offset: Offset for pagination
        
    Returns:
        Dict with leads and metadata
    """
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise HTTPException(
                status_code=500,
                detail="DATABASE_URL environment variable not set"
            )
        
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        query = session.query(Lead)
        if status:
            query = query.filter(Lead.status == status)
        
        total = query.count()
        leads_data = query.offset(offset).limit(limit).all()
        
        leads = []
        for lead in leads_data:
            assessment = None
            if lead.raw_data:
                try:
                    raw = json.loads(lead.raw_data)
                    assessment = raw.get("assessment")
                except Exception:
                    pass
            
            leads.append({
                "id": lead.id,
                "company_name": lead.company_name,
                "industry": lead.industry,
                "source_url": lead.source_url,
                "lead_score": lead.lead_score,
                "status": lead.status,
                "assessment": assessment,
                "created_at": lead.created_at.isoformat() if lead.created_at else None
            })
        
        return {
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "leads": leads
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list leads")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list leads: {str(e)}"
        )


# ============================================================================
# Status and Stats Endpoints
# ============================================================================

@app.get("/stats", response_model=Dict[str, Any])
async def get_stats() -> Dict[str, Any]:
    """
    Get statistics about leads in the database.
    
    Returns:
        Dict with lead counts by status and average scores
    """
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise HTTPException(
                status_code=500,
                detail="DATABASE_URL environment variable not set"
            )
        
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        total_leads = session.query(Lead).count()
        assessed_leads = session.query(Lead).filter(Lead.status == "assessed").count()
        new_leads = session.query(Lead).filter(Lead.status == "new").count()
        
        # Calculate average lead score for assessed leads
        avg_score = 0.0
        if assessed_leads > 0:
            scores = session.query(Lead.lead_score).filter(Lead.status == "assessed").all()
            valid_scores = [s[0] for s in scores if s[0] is not None]
            if valid_scores:
                avg_score = sum(valid_scores) / len(valid_scores)
        
        return {
            "status": "success",
            "total_leads": total_leads,
            "assessed_leads": assessed_leads,
            "new_leads": new_leads,
            "average_lead_score": round(avg_score, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get stats")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
