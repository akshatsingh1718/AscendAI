"""
Ignore this file for now. It is just for testing purposes.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import html2text

def soup_to_raw_data(soup):
         # Build a cleaned text snippet to send to the LLM (truncate to avoid huge payloads)
        paragraphs = [p.get_text(separator=' ', strip=True) for p in soup.find_all('p')]
        headings = [h.get_text(separator=' ', strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
        # Extract list items
        list_items = [li.get_text(separator=' ', strip=True) for li in soup.find_all('li')]
        # Extract tables into a simple text/markdown representation
        tables = []
        for table in soup.find_all('table'):
            rows = []
            # headers
            ths = [th.get_text(separator=' ', strip=True) for th in table.find_all('th')]
            if ths:
                rows.append(' | '.join(ths))
                rows.append(' | '.join(['---'] * len(ths)))
            # body rows
            for tr in table.find_all('tr'):
                cols = [c.get_text(separator=' ', strip=True) for c in tr.find_all(['td', 'th'])]
                if cols:
                    rows.append(' | '.join(cols))
            if rows:
                tables.append('\n'.join(rows))
        meta_desc = ''
        md = soup.find('meta', attrs={'name': 'description'})
        if md and md.get('content'):
            meta_desc = md.get('content').strip()

        # Compose page text including headings, paragraphs, lists and tables so the LLM sees tabular data
        page_sections = []
        if meta_desc:
            page_sections.append(meta_desc)
        if headings:
            page_sections.append('\n'.join(headings))
        if paragraphs:
            page_sections.append('\n'.join(paragraphs))
        if list_items:
            page_sections.append('LIST ITEMS:\n' + '\n'.join(list_items[:200]))
        if tables:
            # include up to first 5 tables
            page_sections.append('TABLES:\n' + '\n\n'.join(tables[:5]))

        page_text = '\n\n'.join(page_sections)
        return page_text

def url_to_markdown_js(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        page.goto(url, wait_until="networkidle")

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

# Example
# print(url_to_markdown("https://techcrunch.com/2025/11/26/here-are-the-49-us-ai-startups-that-have-raised-100m-or-more-in-2025/"))
print(url_to_markdown_js("https://fundraiseinsider.com/blog/funded-startups-united-states/")) # url 1