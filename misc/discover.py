#!/usr/bin/env python3
"""
LifeCell Blog Link Extractor
Extracts all blog article links from https://www.lifecell.in/blog
Handles dynamic content loading with infinite scroll
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    """Set up Chrome WebDriver with optimal settings"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Uncomment the next line if you want to run headless
    # chrome_options.add_argument("--headless")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Execute script to remove webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def scroll_and_load_content(driver, max_scrolls=20, scroll_pause=2):
    """
    Scroll down the page to load dynamic content
    Returns True if new content was loaded, False otherwise
    """
    print("Starting to scroll and load content...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    no_new_content_count = 0
    
    while scroll_count < max_scrolls:
        print(f"Scroll {scroll_count + 1}/{max_scrolls}")
        
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait for new content to load
        time.sleep(scroll_pause)
        
        # Check if new content has loaded
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            no_new_content_count += 1
            print(f"No new content loaded (attempt {no_new_content_count})")
            
            # If no new content for 3 consecutive attempts, break
            if no_new_content_count >= 3:
                print("No new content detected after 3 attempts. Stopping scroll.")
                break
        else:
            no_new_content_count = 0
            print(f"New content loaded. Page height: {last_height} -> {new_height}")
        
        last_height = new_height
        scroll_count += 1
        
        # Additional wait for any lazy-loaded content
        time.sleep(1)
    
    print(f"Completed scrolling. Total scrolls: {scroll_count}")
    return scroll_count > 0

def extract_blog_links(driver):
    """Extract all blog article links from the page"""
    print("Extracting blog links...")
    
    # Wait for the page to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )
    except TimeoutException:
        print("Timeout waiting for links to load")
        return []
    
    # Find all anchor tags
    links = driver.find_elements(By.TAG_NAME, "a")
    
    blog_links = []
    seen_urls = set()
    
    for link in links:
        try:
            href = link.get_attribute("href")
            text = link.text.strip()
            
            # Filter for blog links and avoid duplicates
            if (href and 
                "/blog/" in href and 
                href not in seen_urls and
                text):  # Only include links with text
                
                blog_links.append({
                    "url": href,
                    "title": text,
                    "html": link.get_attribute("outerHTML")
                })
                seen_urls.add(href)
                
        except Exception as e:
            print(f"Error processing link: {e}")
            continue
    
    print(f"Found {len(blog_links)} unique blog links")
    return blog_links

def save_links_to_file(links, filename="lifecell_blog_links.txt"):
    """Save extracted links to a text file"""
    print(f"Saving links to {filename}...")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("LifeCell Blog Links\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total links found: {len(links)}\n")
        f.write(f"Extracted on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for i, link in enumerate(links, 1):
            f.write(f"{i}. {link['title']}\n")
            f.write(f"   URL: {link['url']}\n")
            f.write(f"   HTML: {link['html']}\n")
            f.write("-" * 80 + "\n")
    
    print(f"Links saved to {filename}")

def save_links_to_json(links, filename="lifecell_blog_links.json"):
    """Save extracted links to a JSON file for structured data"""
    print(f"Saving links to {filename}...")
    
    data = {
        "extraction_date": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_links": len(links),
        "source_url": "https://www.lifecell.in/blog",
        "links": links
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Links saved to {filename}")

def main():
    """Main function to orchestrate the scraping process"""
    print("LifeCell Blog Link Extractor")
    print("=" * 40)
    
    driver = None
    try:
        # Set up the driver
        print("Setting up Chrome WebDriver...")
        driver = setup_driver()
        
        # Navigate to the blog page
        print("Navigating to LifeCell blog page...")
        driver.get("https://www.lifecell.in/blog")
        
        # Wait for initial page load
        time.sleep(3)
        
        # Scroll and load dynamic content
        scroll_and_load_content(driver, max_scrolls=30, scroll_pause=2)
        
        # Extract blog links
        blog_links = extract_blog_links(driver)
        
        if blog_links:
            # Save to both text and JSON formats
            save_links_to_file(blog_links)
            save_links_to_json(blog_links)
            
            print(f"\nExtraction completed successfully!")
            print(f"Found {len(blog_links)} blog links")
            print("Files created:")
            print("- lifecell_blog_links.txt (human-readable format)")
            print("- lifecell_blog_links.json (structured data)")
        else:
            print("No blog links found. The page structure might have changed.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        if driver:
            print("Closing browser...")
            driver.quit()

if __name__ == "__main__":
    main()