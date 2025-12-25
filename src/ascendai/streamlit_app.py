import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from typing import List, Any

st.set_page_config(page_title="AscendAI — Leads", layout="wide")

st.sidebar.title("AscendAI")
api_base = st.sidebar.text_input("API base URL", value="http://localhost:8000")

st.sidebar.markdown("---")
action = st.sidebar.radio("Action", ["Generate Leads", "Assess Leads", "List Leads", "Lead Detail", "Stats"])

col1, col2 = st.columns([3, 1])

def post_json(path: str, payload: dict) -> Any:
    try:
        r = requests.post(f"{api_base}{path}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_json(path: str, params: dict = None) -> Any:
    try:
        r = requests.get(f"{api_base}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

with col1:
    st.title("AscendAI — Lead Tools")
    st.write("Minimalist UI to call the lead generation and assessment API.")

    if action == "Generate Leads":
        st.header("Generate Leads")
        limit = st.number_input("Limit (queries)", min_value=1, max_value=50, value=5)
        custom_queries = st.text_area("Optional custom queries (one per line)")
        if st.button("Generate"):
            body = {"limit": limit}
            if custom_queries.strip():
                body["search_queries"] = [q.strip() for q in custom_queries.splitlines() if q.strip()]
            resp = post_json("/leads/generate", body)
            st.subheader("Response")
            st.json(resp)

    if action == "Assess Leads":
        st.header("Assess Leads")
        limit = st.number_input("Limit (leads)", min_value=1, max_value=100, value=5)
        lead_ids_text = st.text_input("Optional lead IDs (comma separated)")
        if st.button("Assess"):
            body = {"limit": limit}
            if lead_ids_text.strip():
                try:
                    ids = [int(x.strip()) for x in lead_ids_text.split(",") if x.strip()]
                    body["lead_ids"] = ids
                except Exception:
                    st.error("Invalid lead IDs")
                    ids = []
            resp = post_json("/leads/assess", body)
            st.subheader("Response")
            st.json(resp)

    if action == "List Leads":
        st.header("List Leads")
        status = st.selectbox("Status", options=["", "new", "assessed"], index=0)
        limit = st.number_input("Limit", min_value=1, max_value=200, value=20)
        offset = st.number_input("Offset", min_value=0, value=0)
        if st.button("List"):
            params = {"limit": limit, "offset": offset}
            if status:
                params["status"] = status
            resp = get_json("/leads", params=params)
            st.subheader("Results")
            if isinstance(resp, dict) and resp.get("leads"):
                leads = resp.get("leads")
                if not leads:
                    st.info("No leads found")
                else:
                    # Render cards with a green accent
                                        card_css = """
                                        <style>
                                        .card-grid{display:grid;grid-template-columns:1fr;gap:16px}
                                        .lead-card{display:flex;gap:16px;align-items:flex-start;background:#fbf7ff;border-left:6px solid #7c3aed;padding:14px;border-radius:10px;box-shadow:0 4px 12px rgba(124,58,237,0.08)}
                                        .lead-image{width:120px;height:120px;border-radius:8px;object-fit:cover;flex:0 0 120px;background:#efe6ff}
                                        .lead-content{flex:1;min-width:0}
                                        .lead-title{font-weight:800;color:#4c1d95;font-size:20px;margin-bottom:6px}
                                        .lead-meta{color:#5b21b6;font-size:13px;margin-bottom:8px}
                                        .lead-desc{color:#312e81;font-size:14px;margin-bottom:8px}
                                        .lead-footer{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
                                        .lead-score{background:#f3e8ff;color:#4c1d95;padding:6px 10px;border-radius:999px;font-weight:800}
                                        .lead-link{color:#6d28d9;text-decoration:none;font-weight:700}
                                        </style>
                                        """

                                        html = card_css + '<div class="card-grid">'
                                        for lead in leads:
                                                name = lead.get('company_name') or '—'
                                                industry = lead.get('industry') or ''
                                                score = lead.get('lead_score') if lead.get('lead_score') is not None else ''
                                                url = lead.get('source_url') or ''
                                                status = lead.get('status') or ''
                                                desc = (lead.get('description') or '')[:260]
                                                # try to extract short rationale
                                                assessment = lead.get('assessment') or {}
                                                rationale = ''
                                                if isinstance(assessment, dict):
                                                        ras = assessment.get('rationales') or assessment.get('rationale') or ''
                                                        if isinstance(ras, dict):
                                                                parts = [f"{k}: {v}" for k, v in list(ras.items())[:2]]
                                                                rationale = ' ; '.join(parts)
                                                        else:
                                                                rationale = str(ras)[:220]

                                                # image fallback: use provided image or favicon of source_url
                                                img = lead.get('image') or 'https://img.freepik.com/premium-vector/illustration-vector-graphic-cartoon-character-company_516790-299.jpg'
                                                if not img and url:
                                                        try:
                                                                from urllib.parse import urlparse
                                                                parsed = urlparse(url)
                                                                img = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
                                                        except Exception:
                                                                img = ''

                                                img_attr = f'<img class="lead-image" src="{img}" alt="logo" onerror="this.style.display=\'none\'"/>' if img else '<div class="lead-image"></div>'

                                                html += f"""
                                                <div class="lead-card">
                                                    {img_attr}
                                                    <div class="lead-content">
                                                        <div class="lead-title">{name}</div>
                                                        <div class="lead-meta">{industry} {('• ' + status) if status else ''}</div>
                                                        <div class="lead-desc">{desc}</div>
                                                        <div class="lead-footer">
                                                            <div class="lead-score">{score}</div>
                                                            <div><a class="lead-link" href="{url}" target="_blank">Website</a></div>
                                                        </div>
                                                        {f'<div style="margin-top:8px;color:#4c1d95;font-size:13px">Reason: {rationale}</div>' if rationale else ''}
                                                    </div>
                                                </div>
                                                """
                                        html += '</div>'
                                        # height: one card per row, calculate rows
                                        rows = len(leads)
                                        height = min(1600, 160 * rows + 80)
                                        components.html(html, height=height, scrolling=True)
                                        st.caption(f"Showing {len(leads)} leads")
            else:
                st.json(resp)

    if action == "Lead Detail":
        st.header("Lead Detail")
        lead_id = st.number_input("Lead ID", min_value=1, value=1)
        if st.button("Get Lead"):
            resp = get_json(f"/leads/{lead_id}")
            if isinstance(resp, dict) and resp.get("id"):
                lead = resp
                # Prepare fields
                name = lead.get("company_name") or "—"
                industry = lead.get("industry") or ""
                url = lead.get("source_url") or ""
                score = lead.get("lead_score") if lead.get("lead_score") is not None else ""
                status = lead.get("status") or ""
                desc = (lead.get("description") or "")
                assessment = lead.get("assessment") or {}

                # Build factor list HTML (as vertical list, not chips)
                factors_html = ""
                if isinstance(assessment, dict):
                    # show known factor keys and scores
                    keys = [k for k in assessment.keys() if k not in ("rationales", "raw_search_snippets", "rationale")]
                    if keys:
                        factors_html += "<ul style=\"margin-top:8px;list-style-type:none;padding:0\">"
                        for k in keys:
                            v = assessment.get(k)
                            # format floats nicely
                            disp = f"{v:.2f}" if isinstance(v, float) else str(v)
                            factors_html += f'<li style="padding:8px 0;border-bottom:1px solid #e9d5ff"><strong style="color:#4c1d95">{k}:</strong> <span style="color:#6b21a8">{disp}</span></li>'
                        factors_html += '</ul>'

                # rationales
                rationale_html = ""
                ras = assessment.get("rationales") or assessment.get("rationale")
                if ras:
                    if isinstance(ras, dict):
                        parts = [f"<li><strong>{k}:</strong> {v}</li>" for k, v in ras.items()]
                        rationale_html = f"<ul style='margin-top:8px'>{''.join(parts)}</ul>"
                    else:
                        rationale_html = f"<p style='margin-top:8px'>{str(ras)}</p>"

                # image handling
                img = lead.get('image') or 'https://img.freepik.com/free-vector/organic-flat-people-business-training-illustration_52683-59856.jpg'
                if not img and url:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        img = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
                    except Exception:
                        img = ''

                img_tag = f'<img src="{img}" alt="logo" style="width:100%;max-width:280px;height:auto;border-radius:8px" onerror="this.style.display=\'none\'"/>' if img else '<div style="width:280px;height:180px;border-radius:8px;background:#efe6ff"></div>'

                detail_html = f"""
                <div style="font-family:Inter,Segoe UI,Arial;margin:12px;padding:18px;background:#ffffff;border-radius:10px;box-shadow:0 6px 24px rgba(16,24,40,0.06);">
                  <div style="display:flex;flex-direction:column;gap:16px">
                    <div style="text-align:center">{img_tag}</div>
                    <div style="flex:1;min-width:0">
                      <div style="color:#4c1d95;font-size:26px;font-weight:800">{name}</div>
                      <div style="color:#6b21a8;margin-top:6px;font-size:14px">{industry} {('• ' + status) if status else ''}</div>
                      <div style="color:#0f172a;margin-top:12px;font-size:15px">{desc}</div>
                      {f'<div style="margin-top:12px"><a href="{url}" target="_blank" style="color:#6d28d9;font-weight:700">Visit Website</a></div>' if url else ''}
                      <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center">
                        <div style="font-weight:800;background:#fbf7ff;color:#4c1d95;padding:8px 12px;border-radius:999px">Lead score: {score}</div>
                      </div>
                      {f'<div style="margin-top:12px"><strong>Factors:</strong>{factors_html}</div>' if factors_html else ''}
                      {f'<div style="margin-top:12px"><strong>Rationales:</strong>{rationale_html}</div>' if rationale_html else ''}
                    </div>
                  </div>
                </div>
                """

                components.html(detail_html, height=620)
            else:
                st.error("Lead not found or API error")

    if action == "Stats":
        st.header("Stats")
        if st.button("Get Stats"):
            resp = get_json("/stats")
            st.json(resp)

with col2:
    st.markdown("## Quick Links")
    st.markdown("- API docs: `/docs` on your API server")
    st.markdown("- Health: `/health`")
    st.markdown("---")
    st.markdown("## Last response snapshot")
    # small area reserved to show last responses if desired

st.sidebar.markdown("---")
st.sidebar.markdown("Streamlit UI — Minimalist by design")

# Footer
st.markdown("---")
st.caption("AscendAI — use the sidebar to switch actions. Ensure the API server is running at the configured base URL.")
