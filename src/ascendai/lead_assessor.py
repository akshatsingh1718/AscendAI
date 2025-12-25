import os
import json
import logging
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm import BedrockLLM
from models.lead import Lead
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
load_dotenv(override=True)


class SerperClient:
    """Minimal Serper (https://serper.dev) client used to run web searches."""

    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            raise RuntimeError("SERPER_API_KEY not set in environment")

    def search(self, q: str, num_results: int = 3) -> List[Dict[str, Any]]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": q, "num": num_results}
        try:
            resp = requests.post(self.ENDPOINT, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # Serper returns items under 'organic' for standard responses
            results = data.get("organic") or data.get("results") or []
            return results[:num_results]
        except Exception as e:
            logger.warning("Serper search failed for query '%s': %s", q, e)
            return []


class LeadAssessor:
    """Assess leads from the database using Serper web search and Bedrock LLM.

    The assessor will search the web for signals related to a lead and then ask the
    LLM to produce a structured JSON with the requested factors and numeric scores.
    """

    FACTOR_KEYS = [
        "tech_stack",
        "business_age_months",
        "merchant_category",
        "company_scale",
        "integration_readiness_score",
        "transaction_intent_score",
        "digital_maturity_score",
        "web_presence_quality",
        "fraud_risk_pattern_score",
        "traffic_check",
        "brand_search_volume",
    ]

    def __init__(self, db_url: Optional[str] = None, serper_api_key: Optional[str] = None):
        db_url = db_url or os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL must be set to connect to the leads database")
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        # Use Serper for one-factor-at-a-time searches
        self.serp = SerperClient(api_key=serper_api_key)
        self.llm = BedrockLLM()

    def _search_for_factor(self, lead: Lead, factor: str, num_results: int = 3) -> List[Dict[str, Any]]:
        """Run a focused web search for a single factor for the given lead and return snippets.

        The query is built to be search-engine-friendly (SEO-style): it includes the
        quoted company name and a set of factor-specific keywords combined with OR,
        and when a `source_url` is available it constrains the search to that site.
        """
        from urllib.parse import urlparse

        def _seo_query_for_factor(name: str, industry: Optional[str], source_url: Optional[str], factor: str) -> str:
            quoted_name = f'"{name}"' if name else ""
            domain = ""
            if source_url:
                try:
                    domain = urlparse(source_url).netloc
                except Exception:
                    domain = source_url

            keywords_map = {
                "tech_stack": ["built on", "powered by", "Shopify", "WooCommerce", "WordPress", "Magento", "bigcommerce", "platform"],
                "business_age_months": ["founded", "established", "since", "founded in", "incorporated", "year"],
                "merchant_category": ["subscription", "SaaS", "services", "e-commerce", "online store", "marketplace"],
                "company_scale": ["employees", "team of", "headcount", "startup", "enterprise", "SMB", "small business"],
                "integration_readiness_score": ["API", "integrations", "developer docs", "plugins", "extensions", "Zapier", "webhooks"],
                "transaction_intent_score": ["checkout", "buy now", "pricing", "add to cart", "purchase", "orders", "payment"],
                "digital_maturity_score": ["analytics", "Google Analytics", "tracking", "mobile friendly", "responsive", "PWA", "SEO"],
                "web_presence_quality": ["press", "blog", "mentions", "backlinks", "domain authority", "traffic", "social"],
                "fraud_risk_pattern_score": ["chargeback", "fraud", "complaint", "scam", "refund", "lawsuit", "security breach"],
                "traffic_check": ["monthly visits", "traffic", "SimilarWeb", "Alexa", "semrush", "traffic estimate"],
                "brand_search_volume": ["search volume", "brand searches", "Google Trends", "searches for"],
            }

            kws = keywords_map.get(factor, [factor, "website", "reviews"])[:6]
            # build OR clause
            or_clause = " OR ".join([f'"{k}"' if " " in k else k for k in kws])
            parts = [p for p in [quoted_name, or_clause] if p]
            q = f"({' '.join(parts)})"
            if industry:
                q = f"{q} {industry}"
            if domain:
                q = f"{q} site:{domain}"
            return q

        name = (lead.company_name or "").strip()
        industry = (lead.industry or "").strip()
        source_url = lead.source_url

        q = _seo_query_for_factor(name, industry, source_url, factor)

        results = self.serp.search(q, num_results=num_results)
        snippets: List[Dict[str, Any]] = []
        for r in results:
            title = r.get("title") or r.get("position") or r.get("snippet_title") or ""
            snippet = r.get("snippet") or r.get("summary") or r.get("description") or r.get("snippet_text") or ""
            link = r.get("link") or r.get("url") or r.get("source") or ""
            snippets.append({"query": q, "title": title, "snippet": snippet, "link": link})
        return snippets

    def _build_factor_prompt(self, lead: Lead, factor: str, snippets: List[Dict[str, Any]]) -> str:
        """Build a concise prompt asking the LLM to infer the value for one factor using snippets."""
        prompt = (
            f"You are an assistant that inspects web search results and extracts one field for a company.\n"
            f"Field: {factor}\n"
            f"Allowed output: Return a single JSON object with keys: \"{factor}\" and optional \"rationale\".\n"
            f"If the field is a score, return a float between 0 and 1. If it is a categorical value, return one of the allowed categories.\n"
            f"Return ONLY valid JSON (no markdown).\n\n"
        )
        lead_info = {
            "company_name": lead.company_name,
            "source_url": lead.source_url,
            "industry": lead.industry,
        }
        prompt += f"LEAD:\n{json.dumps(lead_info, ensure_ascii=False)}\n\nSEARCH_SNIPPETS:\n{json.dumps(snippets, ensure_ascii=False)}\n"
        return prompt

    def _estimate_factor_with_llm(self, lead: Lead, factor: str, snippets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ask the LLM to estimate a factor value when evidence is insufficient.

        The LLM is explicitly allowed to provide an estimate (and should mark it with
        `estimated: true` in the returned object). Return a parsed dict or empty dict.
        """
        prompt = (
            f"You did not find explicit evidence in the provided snippets. Using the lead information and the snippets, "
            f"provide a best-effort ESTIMATE for the field `{factor}` for the company.\n"
            f"Return a JSON object with keys: \"{factor}\" (value), optional \"rationale\" explaining why, and \"estimated\": true.\n"
            f"If the value is a score, return a float between 0 and 1. If categorical, return one of the allowed categories.\n"
            f"Return ONLY valid JSON (no markdown).\n\n"
        )
        lead_info = {"company_name": lead.company_name, "source_url": lead.source_url, "industry": lead.industry}
        prompt += f"LEAD:\n{json.dumps(lead_info, ensure_ascii=False)}\n\nSEARCH_SNIPPETS:\n{json.dumps(snippets, ensure_ascii=False)}\n"
        try:
            res = self.llm.generate_json(prompt, maxTokens=600)
            parsed = {}
            if isinstance(res, list) and res:
                parsed = res[0] if isinstance(res[0], dict) else {}
            elif isinstance(res, dict):
                parsed = res
            return parsed
        except Exception:
            return {}

    def _build_prompt(self, lead: Lead, search_snippets: str) -> str:
        prompt = (
            "You are an assistant that analyzes a company's web footprint and outputs a JSON object.\n"
            "Given the lead information and a set of web search snippets, return a single JSON object with the following keys:\n"
        )
        prompt += ", ".join(self.FACTOR_KEYS) + ", and lead_score (0-100).\n"

        prompt += (
            "Requirements:\n"
            "- `tech_stack`: one of 'Shopify', 'WooCommerce', 'WordPress', 'Custom', or 'Unknown'.\n"
            "- `business_age_months`: integer months (estimate).\n"
            "- `merchant_category`: one of 'Subscription', 'Services', 'E-commerce', 'SaaS', or 'Other'.\n"
            "- `company_scale`: one of 'SMB', 'Medium', 'Enterprise'.\n"
            "- The following scores must be floats between 0 and 1: `integration_readiness_score`, `transaction_intent_score`, `digital_maturity_score`, `web_presence_quality`, `fraud_risk_pattern_score`, `traffic_check` (0-1), `brand_search_volume` (0-1).\n"
            "- `lead_score`: integer 0-100 summarizing suitability for PayU.\n"
            "- Include a short `rationale` string briefly explaining the major signals used.\n"
            "- Return ONLY valid JSON (no surrounding markdown or explanation).\n\n"
        )

        lead_info = {
            "company_name": lead.company_name,
            "source_url": lead.source_url,
            "industry": lead.industry,
            "description": (lead.description or '')[:2000],
        }

        prompt += f"LEAD:\n{json.dumps(lead_info, ensure_ascii=False)}\n\nSEARCH_SNIPPETS:\n{search_snippets}\n"

        return prompt

    def assess_lead(self, lead: Lead) -> Dict[str, Any]:
        """Assess a single Lead record and return the parsed JSON from the LLM."""
        try:
            logger.info("Asking LLM to assess lead: %s", lead.company_name)
            assessment: Dict[str, Any] = {}
            raw_search_snippets: Dict[str, Any] = {}
            rationales: Dict[str, str] = {}

            for factor in self.FACTOR_KEYS:
                snippets = self._search_for_factor(lead, factor, num_results=3)
                raw_search_snippets[factor] = snippets
                prompt = self._build_factor_prompt(lead, factor, snippets)
                try:
                    res = self.llm.generate_json(prompt, maxTokens=800)
                except Exception as e:
                    logger.warning("LLM failed for factor %s: %s", factor, e)
                    continue

                parsed_factor: Dict[str, Any] = {}
                if isinstance(res, list) and res:
                    parsed_factor = res[0] if isinstance(res[0], dict) else {}
                elif isinstance(res, dict):
                    parsed_factor = res

                # try common keys
                value = parsed_factor.get(factor)
                if value is None:
                    value = parsed_factor.get("value") or parsed_factor.get("score") or parsed_factor.get("result")

                if value is not None:
                    assessment[factor] = value

                if parsed_factor.get("rationale"):
                    rationales[factor] = parsed_factor.get("rationale")

            # normalize numeric types and compute final score if missing
            numeric_scores = []
            for k in [
                "integration_readiness_score",
                "transaction_intent_score",
                "digital_maturity_score",
                "web_presence_quality",
                "fraud_risk_pattern_score",
                "traffic_check",
                "brand_search_volume",
            ]:
                v = assessment.get(k)
                try:
                    if v is None:
                        continue
                    fv = float(v)
                    fv = max(0.0, min(1.0, fv))
                    assessment[k] = fv
                    numeric_scores.append(fv)
                except Exception:
                    continue

            if "lead_score" not in assessment:
                assessment["lead_score"] = int(round((sum(numeric_scores) / len(numeric_scores)) * 100)) if numeric_scores else 0

            assessment["rationales"] = rationales
            assessment["raw_search_snippets"] = raw_search_snippets
            return assessment
        except Exception as e:
            logger.exception("Failed to assess lead %s: %s", lead.company_name, e)
            return {"error": str(e)}

    def persist_assessment(self, lead: Lead, assessment: Dict[str, Any]) -> None:
        try:
            # attach assessment to raw_data (merge with existing JSON if present)
            existing = {}
            if lead.raw_data:
                try:
                    existing = json.loads(lead.raw_data)
                except Exception:
                    existing = {"raw": lead.raw_data}

            existing["assessment"] = assessment
            lead.raw_data = json.dumps(existing, ensure_ascii=False)

            # update lead_score if present
            if isinstance(assessment.get("lead_score"), (int, float)):
                lead.lead_score = float(assessment.get("lead_score"))

            lead.status = "assessed"
            self.session.add(lead)
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.exception("Failed to persist assessment for lead %s", lead.company_name)

    def assess_all_leads(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Assess all leads (or up to `limit`) and persist results. Returns list of assessments."""
        q = self.session.query(Lead).filter(Lead.status != "assessed").order_by(Lead.created_at)
        if limit:
            q = q.limit(limit)
        leads = q.all()
        results = []
        for lead in leads:
            assessment = self.assess_lead(lead)
            self.persist_assessment(lead, assessment)
            results.append({"lead_id": lead.id, "company_name": lead.company_name, "assessment": assessment})
        return results


if __name__ == "__main__":
    # Simple CLI invocation for local runs
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Please set DATABASE_URL environment variable to run the assessor")
    else:
        assessor = LeadAssessor(db_url=db_url)
        out = assessor.assess_all_leads(limit=1)
        print(json.dumps(out, indent=2, ensure_ascii=False))
