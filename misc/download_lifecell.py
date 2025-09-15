#!/usr/bin/env python3
import json
import requests
import os
import hashlib
import re
from bs4 import BeautifulSoup

def download_html_files(json_file="lifecell_blog_links.json", output_dir="html_downloads"):
    """Download and parse HTML files, extracting only main content div"""
    
    # Load links
    with open(json_file, 'r') as f:
        data = json.load(f)
    links = data['links']
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup session
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; downloader/1.0)'})
    
    success = 0
    
    for i, link in enumerate(links, 1):
        url = link['url']
        title = link['title']

        if not "/stem-cells/" in url:
            continue
        
        try:
            # Create filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            safe_title = re.sub(r'[^\w\s-]', '', title)[:30].replace(' ', '_')
            filename = f"{url_hash}_{safe_title}.html"
            filepath = os.path.join(output_dir, filename)
            
            # Skip if exists
            if os.path.exists(filepath):
                print(f"[{i}/{len(links)}] SKIP: {title[:40]}")
                success += 1
                continue
            
            print(f"[{i}/{len(links)}] GET: {title[:40]}")
            
            # Download
            response = session.get(url, timeout=20)
            response.raise_for_status()
            
            # Parse HTML and extract main content
            soup = BeautifulSoup(response.text, 'html.parser')
            main_div = soup.find('div', {
                'data-content-type': 'row',
                'data-appearance': 'contained',
                'data-element': 'main'
            })
            
            if main_div:
                content = str(main_div)
            else:
                print(f"    Warning: Main content div not found, saving full page")
                content = response.text
            
            # Save extracted content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            success += 1
            
        except Exception as e:
            print(f"[{i}/{len(links)}] FAIL: {title[:40]} - {e}")
    
    print(f"\nCompleted: {success}/{len(links)} files downloaded to {output_dir}/")
    print(f"Content parsed: Only main content div stored")

if __name__ == "__main__":
    download_html_files()