import json
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
import html2text
from llm import BedrockLLM

load_dotenv(override=True)

# Set the bearer token environment variable
print(os.environ['AWS_BEARER_TOKEN_BEDROCK'])

# SQLAlchemy setup
from models import Lead, SearchQuery, Base

class PayULeadGenerator:
    """
    AI-powered lead generation system using AWS Bedrock and SQLite
    """
    
    def __init__(self, db_path: str = "payu_leads.db", aws_region: str = "us-east-1"):
        """
        Initialize with AWS Bedrock and SQLite database
        
        Args:
            db_path: Path to SQLite database file
            aws_region: AWS region for Bedrock service
        """
        # Initialize AWS Bedrock
        self.bedrock = BedrockLLM()
        
        # Initialize SQLite database
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        print(f"✅ Initialized with database: {db_path}")
        # print(f"✅ Using AWS Bedrock model: {self.model_id}")
    
    def search_queries(self) -> List[str]:
        """Define search queries to find PayU leads"""
        return [
            # New companies/startups
            "new fintech startups 2024 2025 funding rounds",
            "e-commerce startups launched 2024 payment needs",
            "SaaS companies seeking payment integration",
            "marketplace platforms payment gateway",
            
            # Companies using competitors
            "companies using Stripe payment gateway",
            "Razorpay merchant integration news",
            "PayPal business integration announcement",
            "Square payment processing new clients",
            
            # Industry-specific
            "online education platforms payment solutions",
            "telemedicine healthcare payment gateway",
            "food delivery apps payment integration",
            "travel booking payment processing",
            
            # Growth signals
            "companies raising series A payment infrastructure",
            "digital transformation payment gateway adoption",
            "cross-border payment solution needs",
            "subscription business payment automation"
        ]
    
    def search_with_serper(self, query: str) -> Dict:
        """
        Perform a web search using Serper API
        
        Args:
            query: The search query string
            
        Returns:
            Dict containing search results from Serper API
        """
        url = "https://google.serper.dev/search"

        # simple file cache for serper responses
        cache_dir = Path("cache/serper")
        cache_dir.mkdir(parents=True, exist_ok=True)
        qhash = hashlib.sha256(query.encode('utf-8')).hexdigest()
        cache_file = cache_dir / f"{qhash}.json"

        # return cached response if present
        if cache_file.exists():
            try:
                with cache_file.open('r', encoding='utf-8') as fh:
                    return json.load(fh)
            except Exception as e:
                print(f"⚠️ Failed to read cache for query: {e}")

        payload = json.dumps({
            "q": query
        })

        headers = {
            'X-API-KEY': os.environ.get('SERPER_API_KEY', 'a82e506a1d9965b424c351f90e0396952b5d3c10'),
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            # save to cache (best-effort)
            try:
                with cache_file.open('w', encoding='utf-8') as fh:
                    json.dump(data, fh)
            except Exception as e:
                print(f"⚠️ Failed to write cache file: {e}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Serper API error: {e}")
            return {}
    
    def format_search_results(self, serper_response: Dict) -> str:
        """
        Format Serper API response into a readable string for Claude
        
        Args:
            serper_response: Raw response from Serper API
            
        Returns:
            Formatted string of search results
        """
        formatted_results = []
        
        # Add knowledge graph if available
        if 'knowledgeGraph' in serper_response:
            kg = serper_response['knowledgeGraph']
            formatted_results.append(f"Knowledge Graph: {kg.get('title', '')} - {kg.get('description', '')}")
            if 'attributes' in kg:
                for key, value in kg['attributes'].items():
                    formatted_results.append(f"  {key}: {value}")
        
        # Add organic search results
        if 'organic' in serper_response:
            formatted_results.append("\nSearch Results:")
            for result in serper_response['organic'][:10]:  # Top 10 results
                formatted_results.append(f"\n- Title: {result.get('title', '')}")
                formatted_results.append(f"  URL: {result.get('link', '')}")
                formatted_results.append(f"  Snippet: {result.get('snippet', '')}")
                if 'attributes' in result:
                    for key, value in result['attributes'].items():
                        formatted_results.append(f"  {key}: {value}")
        
        # Add people also ask
        if 'peopleAlsoAsk' in serper_response:
            formatted_results.append("\nRelated Questions:")
            for paa in serper_response['peopleAlsoAsk'][:5]:
                formatted_results.append(f"- {paa.get('question', '')}: {paa.get('snippet', '')}")
        
        return "\n".join(formatted_results)

    def fetch_page_content(self, url: str, timeout: int = 15) -> Optional[str]:
        """Fetch HTML content for a given URL with basic headers and error handling."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; PayU-LeadBot/1.0; +https://payu.in)'
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"⚠️ Failed to fetch {url}: {e}")
            return None

    def _get_page_text_from_url(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()

            page.goto(url, wait_until="domcontentloaded")

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # print(soup_to_raw_data(soup))
        # return
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        cleaned_html = soup.prettify()

        markdown = html2text.html2text(cleaned_html)
        return markdown

    def extract_companies_from_url(self, url: str) -> List[Dict]:
        """Use Bedrock LLM to parse page content and extract structured leads.

        Falls back to simple on-page heuristics when the LLM call fails or returns
        invalid output.
        """
        print(f"🤖 Scraping webpage: {url}")

        # TODO: Read page text from url
        page_text = self._get_page_text_from_url(url)

        # Truncate to ~12000 characters to keep request size reasonable
        truncated = page_text[:12000]

        # Prepare prompt for the LLM
        prompt = (
            f"You are a professional lead finder agent. Read the following page text from {url} "
            "and extract company leads mentioned or clearly described on the page. "
            "Return ONLY a JSON array of objects with these keys: company_name, industry, description, "
            "why_payu, source_url, company_size, lead_score (0-100). If no companies are present, "
            "return an empty JSON array. Use the page content to infer fields; be concise." 
            "\n\nPAGE_TEXT:\n" + truncated
        )

        try:
            leads = self.bedrock.generate_json(prompt, maxTokens=2000)

            # Ensure proper structure & defaults
            valid = []
            for item in (leads if isinstance(leads, list) else []):
                if not isinstance(item, dict):
                    continue
                item.setdefault('company_name', '')
                item.setdefault('industry', '')
                item.setdefault('description', '')
                item.setdefault('why_payu', '')
                item.setdefault('source_url', url)
                item.setdefault('company_size', '')
                item.setdefault('lead_score', 0)
                valid.append(item)

            if valid:
                return valid
        except json.JSONDecodeError as e:
            print(f"⚠️ LLM returned non-JSON content for {url}: {e}")
        except Exception as e:
            print(f"⚠️ LLM extraction failed for {url}: {e}")
        return leads
    
    def call_bedrock_with_search(self, query: str) -> Dict:
        """
        Call AWS Bedrock Claude with real web search results from Serper API
        """
        print(f"\n🔍 Processing query: {query}")
        
        # Step 1: Perform web search using Serper API
        print(f"🌐 Searching the web with Serper API...")
        serper_results = self.search_with_serper(query)
        
        if not serper_results:
            print("⚠️ No search results returned from Serper, proceeding with query-based generation")
            search_context = "No web search results available."
        else:
            # We'll scrape the actual pages from the organic results
            print(f"✅ Retrieved {len(serper_results.get('organic', []))} search results; scraping pages...")

        # Collect URLs from Serper organic results
        urls = []
        for r in serper_results.get('organic', []):
            link = r.get('link') or r.get('url') or r.get('displayLink')
            if link:
                urls.append(link)

        scraped_leads = []
        visited = set()
        for u in urls:
            # normalize
            try:
                parsed = urlparse(u)
                if not parsed.scheme:
                    u = 'https://' + u
            except Exception:
                pass
            if u in visited:
                continue
            visited.add(u)

            # html = self.fetch_page_content(u)
            # if not html:
            #     continue

            leads = self.extract_companies_from_url(u)
            # attach search query context
            for lead in leads:
                lead['search_query'] = query
            scraped_leads.extend(leads)

        print(f"✅ Extracted {len(scraped_leads)} candidate leads from scraped pages")

        # Deduplicate by company_name
        unique = {}
        for l in scraped_leads:
            key = (l.get('company_name') or '').strip().lower()
            if not key:
                continue
            if key not in unique:
                unique[key] = l

        return {
            'query': query,
            'leads': list(unique.values()),
            'raw_response': json.dumps(serper_results),
            'search_results': serper_results
        }
    
    def save_lead_to_db(self, lead_data: Dict, search_query: str) -> Optional[Lead]:
        """Save a lead to the database"""
        try:
            lead = Lead(
                company_name=lead_data.get('company_name', 'Unknown'),
                industry=lead_data.get('industry', ''),
                description=lead_data.get('description', ''),
                why_payu=lead_data.get('why_payu', ''),
                source_url=lead_data.get('source_url', ''),
                company_size=lead_data.get('company_size', ''),
                search_query=search_query,
                lead_score=float(lead_data.get('lead_score', 0)),
                raw_data=json.dumps(lead_data)
            )
            
            self.session.add(lead)
            self.session.commit()
            return lead
        except Exception as e:
            print(f"❌ Error saving lead: {e}")
            self.session.rollback()
            return None
    
    def save_search_query(self, query: str, leads_count: int, raw_response: str):
        """Save search query metadata"""
        try:
            sq = SearchQuery(
                query=query,
                leads_found=leads_count,
                raw_response=raw_response
            )
            self.session.add(sq)
            self.session.commit()
        except Exception as e:
            print(f"⚠️ Error saving search query: {e}")
            self.session.rollback()
    
    def run_lead_generation(self, max_queries: int = 5, delay: int = 3) -> Dict:
        """
        Run lead generation across multiple search queries
        
        Args:
            max_queries: Maximum number of queries to process
            delay: Delay in seconds between queries
        """
        queries = self.search_queries()[:max_queries]
        
        print(f"\n{'='*70}")
        print(f"🚀 PayU Lead Generation System")
        print(f"{'='*70}")
        print(f"📊 Processing {len(queries)} search queries")
        print(f"🗄️  Database: {self.engine.url}\n")
        
        total_leads = 0
        successful_queries = 0
        
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*70}")
            print(f"Query {i}/{len(queries)}: {query}")
            print(f"{'='*70}")
            
            result = self.call_bedrock_with_search(query)
            leads = result.get('leads', [])
            
            # Save search query
            self.save_search_query(query, len(leads), result.get('raw_response', ''))
            
            # Save leads to database
            saved_count = 0
            for lead_data in leads:
                if self.save_lead_to_db(lead_data, query):
                    saved_count += 1
            
            print(f"✅ Found {len(leads)} leads, saved {saved_count} to database")
            
            if saved_count > 0:
                successful_queries += 1
                total_leads += saved_count
                print("\n📋 Sample leads:")
                for lead in leads[:2]:
                    print(f"  • {lead.get('company_name')}: {lead.get('why_payu', '')[:60]}...")
            
            # Rate limiting
            if i < len(queries):
                print(f"\n⏳ Waiting {delay} seconds...")
                time.sleep(delay)
        
        return {
            'total_queries': len(queries),
            'successful_queries': successful_queries,
            'total_leads': total_leads,
            "leads" : leads
        }
    
    def get_all_leads(self, min_score: float = 0.0) -> List[Lead]:
        """Retrieve all leads from database, optionally filtered by score"""
        return self.session.query(Lead).filter(
            Lead.lead_score >= min_score
        ).order_by(Lead.lead_score.desc()).all()
    
    def get_leads_by_industry(self, industry: str) -> List[Lead]:
        """Get leads filtered by industry"""
        return self.session.query(Lead).filter(
            Lead.industry.ilike(f'%{industry}%')
        ).order_by(Lead.lead_score.desc()).all()
    
    def generate_report(self) -> str:
        """Generate a comprehensive report from database"""
        all_leads = self.get_all_leads()
        total_queries = self.session.query(SearchQuery).count()
        # compute average safely
        avg_score = (sum(l.lead_score for l in all_leads) / len(all_leads)) if all_leads else 0.0

        report = f"""
    {'='*70}
    PayU Lead Generation Report
    {'='*70}

    📊 Database Statistics:
    - Total search queries executed: {total_queries}
    - Total leads in database: {len(all_leads)}
    - Average lead score: {avg_score:.1f}

    🎯 Top 10 High-Score Leads:
    """
        
        top_leads = sorted(all_leads, key=lambda x: x.lead_score, reverse=True)[:10]
        for i, lead in enumerate(top_leads, 1):
            report += f"\n{i}. {lead.company_name} (Score: {lead.lead_score})"
            report += f"\n   Industry: {lead.industry}"
            report += f"\n   Why PayU: {lead.why_payu[:80]}..."
            report += f"\n   Source: {lead.source_url}\n"
        
        # Group by industry
        industries = {}
        for lead in all_leads:
            ind = lead.industry or 'Unknown'
            industries[ind] = industries.get(ind, 0) + 1
        
        report += f"\n📈 Leads by Industry:\n"
        for industry, count in sorted(industries.items(), key=lambda x: x[1], reverse=True):
            report += f"   {industry}: {count} leads\n"
        
        return report
    
    def export_to_csv(self, filename: str = "payu_leads.csv"):
        """Export leads to CSV file"""
        import csv
        
        leads = self.get_all_leads()
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Company Name', 'Industry', 'Description', 'Why PayU',
                'Source URL', 'Company Size', 'Lead Score', 'Status', 'Created At'
            ])
            
            for lead in leads:
                writer.writerow([
                    lead.company_name,
                    lead.industry,
                    lead.description,
                    lead.why_payu,
                    lead.source_url,
                    lead.company_size,
                    lead.lead_score,
                    lead.status,
                    lead.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
        
        print(f"📄 Exported {len(leads)} leads to {filename}")
    
    def close(self):
        """Close database session"""
        self.session.close()


def main():
    """
    Main execution function
    
    Setup:
    1. Configure AWS credentials:
       - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
       - Or use AWS CLI: aws configure
    
    2. Install dependencies:
       pip install boto3 sqlalchemy
    
    3. Run the script:
       python payu_lead_gen.py
    """
    
    try:
        # Initialize generator
        generator = PayULeadGenerator(
            db_path="payu_leads.db",
        )
        
        # Run lead generation
        stats = generator.run_lead_generation(max_queries=1, delay=3)
        
        # Generate report
        print("\n" + "="*70)
        report = generator.generate_report()
        print(report)
        
        # Save report
        with open("payu_leads_report.txt", 'w') as f:
            f.write(report)
        print("\n💾 Report saved to payu_leads_report.txt")
        
        # Export to CSV
        generator.export_to_csv("payu_leads.csv")
        
        # Display summary
        print(f"\n{'='*70}")
        print(f"✨ Lead Generation Complete!")
        print(f"{'='*70}")
        print(f"📊 Processed {stats['total_queries']} queries")
        print(f"✅ Generated {stats['total_leads']} leads")
        print(f"🗄️  Database: payu_leads.db")
        print(f"📄 Exports: payu_leads.csv, payu_leads_report.txt")
        
        # Close database connection
        generator.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nSetup Instructions:")
        print("1. Configure AWS credentials:")
        print("   export AWS_ACCESS_KEY_ID='your-key'")
        print("   export AWS_SECRET_ACCESS_KEY='your-secret'")
        print("2. Enable AWS Bedrock in your region")
        print("3. Install: pip install boto3 sqlalchemy")


if __name__ == "__main__":
    main()