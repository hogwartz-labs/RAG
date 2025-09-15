import os
import re
import concurrent.futures
import requests
import logging
from bs4 import BeautifulSoup
import html2text

from classes import MarkdownPage

UNWANTED_TAGS = [
    "nav",
    "header",
    "footer",
    "script",
    "style",
    "aside",
    "iframe",
    "noscript",
    "svg",
    "img",
    "form",
    "button",
    "input",
    "textarea",
    "select",
    "video",
    "audio",
]

def safe_filename(title: str) -> str:
    """Generate a safe filename from the title or URL."""
    filename = re.sub(r'[^a-zA-Z0-9_-]', '_', title.strip())
    return filename[:100]

def parse_sitemap(sitemap_url: str):
    response = requests.get(sitemap_url)
    if response.status_code == 404:
        logging.error(f"Sitemap not found at {sitemap_url}")
    
    response.raise_for_status()
    sitemap_xml = response.text
    soup = BeautifulSoup(sitemap_xml, "xml")
    urls = [loc.text for loc in soup.find_all("loc")]
    return urls

def extract_markdown_page(url: str, content: bytes) -> MarkdownPage:
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.string if soup.title and soup.title.string else url

    main_content = soup.main or soup.body

    content_to_process = main_content if main_content else soup
    for unwanted in content_to_process.find_all(UNWANTED_TAGS):
        unwanted.decompose()

    markdown_content = html2text.html2text(str(content_to_process))

    return MarkdownPage(url=url, title=title, content=markdown_content)

def fetch_sitemap_pages(sitemap_url: str, output_dir: str) -> list[MarkdownPage]:
    os.makedirs(output_dir, exist_ok=True)

    urls = parse_sitemap(sitemap_url)
    if not urls:
        logging.error("No URLs found in sitemap.")
        return []

    pages: list[MarkdownPage] = []

    def fetch(url: str) -> MarkdownPage | None:
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            page = extract_markdown_page(url, response.content)

            # Save as markdown file
            filename = safe_filename(page.title or url) + ".md"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {page.title}\n\n{page.content}")

            return page
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

    # Use ThreadPoolExecutor for parallel requests
    max_workers = min(32, len(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                pages.append(result)

    return pages

if __name__ == "__main__":
    pages = fetch_sitemap_pages(sitemap_url="https://www.xml-sitemaps.com/download/thegraph.com-dab32797b/sitemap.xml?view=1", 
                        output_dir="markdown_pages")
