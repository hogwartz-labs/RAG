# Load environment variables
from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
import os
import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.schema import Document
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from openai import AzureOpenAI
import logging
from llm import get_embedding



# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for connections
mongo_client = None
db = None
openai_client = None

def initialize_connections():
    """Initialize MongoDB and Azure OpenAI connections from environment variables"""
    global mongo_client, db, openai_client
    
    # MongoDB configuration
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    database_name = os.getenv('DATABASE_NAME', 'rag_system')
    
    # Azure OpenAI configuration
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_api_version = os.getenv('AZURE_API_VERSION', '2023-05-15')
    
    if not azure_endpoint or not azure_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in environment variables")
    
    # Initialize connections
    mongo_client = MongoClient(mongo_url)
    db = mongo_client[database_name]
    
    openai_client = AzureOpenAI(
        api_key=azure_key,
        api_version=azure_api_version,
        azure_endpoint=azure_endpoint
    )
    
    logger.info(f"Connected to MongoDB: {database_name}")
    logger.info("Connected to Azure OpenAI")

def create_indexes():
    """Create MongoDB indexes for better query performance"""
    try:
        # Document indexes
        db.documents.create_index("document_id", unique=True)
        db.documents.create_index("url_hash")
        db.documents.create_index("created_at")
        
        # Chunk indexes
        db.chunks.create_index("document_id")
        db.chunks.create_index("chunk_id", unique=True)
        db.chunks.create_index("chunk_index")
        db.chunks.create_index([("embedding", "2dsphere")])  # For vector similarity
        
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"Error creating indexes: {e}")

def html_to_markdown(html_content: str) -> str:
    """Convert HTML to clean markdown"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted elements
    for element in soup(['script', 'style', 'nav', 'header', 'footer']):
        element.decompose()
    
    markdown_lines = []
    
    # Process each element
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'blockquote']):
        text = element.get_text(strip=True)
        if not text:
            continue
            
        if element.name.startswith('h'):
            level = int(element.name[1])
            markdown_lines.append(f"{'#' * level} {text}")
        elif element.name == 'p':
            markdown_lines.append(text)
        elif element.name in ['ul', 'ol']:
            for li in element.find_all('li'):
                li_text = li.get_text(strip=True)
                if li_text:
                    markdown_lines.append(f"- {li_text}")
        elif element.name == 'table':
            markdown_lines.append(convert_table_to_markdown(element))
        elif element.name == 'blockquote':
            markdown_lines.append(f"> {text}")
        
        markdown_lines.append("")  # Add blank line
    
    return "\n".join(markdown_lines).strip()

def convert_table_to_markdown(table) -> str:
    """Convert HTML table to markdown format"""
    rows = []
    
    # Get all rows
    for tr in table.find_all('tr'):
        cells = []
        for cell in tr.find_all(['td', 'th']):
            cells.append(cell.get_text(strip=True))
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    
    if not rows:
        return ""
    
    # Add header separator if first row looks like headers
    if len(rows) > 1:
        separator = "| " + " | ".join(["---"] * len(rows[0].split("|")[1:-1])) + " |"
        rows.insert(1, separator)
    
    return "\n".join(rows)

def enrich_chunk_with_headings(chunk_text: str, chunk_metadata: Dict) -> str:
    """Prepend relevant headings to chunk content for enrichment"""
    enriched_content = []
    
    # Add hierarchical headers from metadata if available
    headers = []
    for key in sorted(chunk_metadata.keys()):
        if key.startswith('Header'):
            headers.append(f"{chunk_metadata[key]}")
    
    # Add headers as context
    if headers:
        enriched_content.extend(headers)
        enriched_content.append("---")  # Separator between headers and content
    
    # Add the actual chunk content
    enriched_content.append(chunk_text)
    
    return "\n".join(enriched_content)

def save_document_to_mongo(document_data: Dict) -> str:
    """Save document to MongoDB and return document_id"""
    try:
        result = db.documents.insert_one(document_data)
        logger.info(f"Document saved with ID: {document_data['document_id']}")
        return document_data['document_id']
    except DuplicateKeyError:
        logger.warning(f"Document {document_data['document_id']} already exists")
        return document_data['document_id']
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        return None

def save_chunk_to_mongo(chunk_data: Dict) -> bool:
    """Save chunk to MongoDB"""
    try:
        db.chunks.insert_one(chunk_data)
        return True
    except DuplicateKeyError:
        logger.warning(f"Chunk {chunk_data['chunk_id']} already exists")
        return True
    except Exception as e:
        logger.error(f"Error saving chunk: {e}")
        return False

def load_url_mapping(links_json: str) -> Dict:
    """Load URL mapping from JSON file"""
    url_mapping = {}
    if os.path.exists(links_json):
        with open(links_json, 'r') as f:
            data = json.load(f)
            for link in data.get('links', []):
                url_hash = hashlib.md5(link['url'].encode()).hexdigest()[:8]
                url_mapping[url_hash] = {
                    'url': link['url'],
                    'title': link['title']
                }
    return url_mapping

def process_html_files(input_dir: str = None, output_dir: str = None, 
                      links_json: str = None, save_to_mongo: bool = True) -> List[Document]:
    """Convert HTML files to markdown, create enriched chunks, and save to MongoDB"""
    
    # Get parameters from environment or use defaults
    input_dir = input_dir or os.getenv('INPUT_DIR', 'html_downloads')
    output_dir = output_dir or os.getenv('OUTPUT_DIR', 'markdown_docs')
    links_json = links_json or os.getenv('LINKS_JSON', 'lifecell_blog_links.json')
    save_to_mongo = save_to_mongo and os.getenv('SAVE_TO_MONGO', 'true').lower() == 'true'
    
    # Initialize connections
    initialize_connections()
    if save_to_mongo:
        create_indexes()
    
    # Load URL mapping
    url_mapping = load_url_mapping(links_json)
    
    # Create output directories
    Path(output_dir).mkdir(exist_ok=True)
    Path(f"{output_dir}/markdown").mkdir(exist_ok=True)
    Path(f"{output_dir}/chunks").mkdir(exist_ok=True)
    
    # Setup markdown splitter
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"), 
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    html_files = list(Path(input_dir).glob("*.html"))
    all_chunks = []
    
    logger.info(f"Processing {len(html_files)} HTML files...")
    
    for i, file_path in enumerate(html_files, 1):
        try:
            # Get URL info
            filename = file_path.stem
            url_hash = filename.split('_')[0] if '_' in filename else ''
            url_info = url_mapping.get(url_hash, {})

            if not "/stem-cells/" in url_info.get('url', ''):
                continue
            
            # Generate unique document ID
            document_id = str(uuid.uuid4())
            
            logger.info(f"[{i}/{len(html_files)}] Processing: {file_path.name}")
            
            # Read HTML
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Convert to markdown
            markdown_content = html_to_markdown(html_content)
            
            # Save markdown file
            md_filename = f"{url_hash}_{filename.split('_', 1)[1] if '_' in filename else filename}.md"
            md_path = Path(f"{output_dir}/markdown") / md_filename
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {url_info.get('title', 'Document')}\n\n")
                f.write(f"**Source:** {url_info.get('url', '')}\n\n")
                f.write("---\n\n")
                f.write(markdown_content)
            
            # Save document to MongoDB if enabled
            if save_to_mongo:
                document_data = {
                    'document_id': document_id,
                    'url_hash': url_hash,
                    'title': url_info.get('title', ''),
                    'source_url': url_info.get('url', ''),
                    'file_path': str(file_path),
                    'markdown_path': str(md_path),
                    'content': markdown_content,
                    'created_at': datetime.utcnow(),
                    'file_size': len(html_content),
                    'markdown_size': len(markdown_content)
                }
                save_document_to_mongo(document_data)
            
            # Create chunks using markdown splitter
            md_docs = markdown_splitter.split_text(markdown_content)
            
            # Process each chunk
            for chunk_idx, chunk in enumerate(md_docs):
                # Extract content and metadata
                if hasattr(chunk, 'metadata') and hasattr(chunk, 'page_content'):
                    chunk_metadata = chunk.metadata
                    chunk_content = chunk.page_content
                else:
                    chunk_metadata = {}
                    chunk_content = str(chunk)
                
                # Enrich chunk with headings
                enriched_content = enrich_chunk_with_headings(chunk_content, chunk_metadata)
                
                # Generate embedding
                embedding = []
                if save_to_mongo:
                    logger.info(f"  Generating embedding for chunk {chunk_idx + 1}")
                    embedding = get_embedding(enriched_content)
                
                # Create chunk metadata
                chunk_id = f"{document_id}_{chunk_idx}"
                metadata = {
                    'chunk_id': chunk_id,
                    'document_id': document_id,  # Link to parent document
                    'source': str(file_path),
                    'source_url': url_info.get('url', ''),
                    'title': url_info.get('title', ''),
                    'chunk_index': chunk_idx,
                    'total_chunks': len(md_docs),
                    'file_hash': url_hash,
                    'markdown_file': str(md_path),
                    'created_at': datetime.utcnow()
                }
                
                # Add header metadata from chunk
                metadata.update(chunk_metadata)
                
                # Create Document object with enriched content
                doc = Document(page_content=enriched_content, metadata=metadata)
                all_chunks.append(doc)
                
                # Save chunk to MongoDB if enabled
                if save_to_mongo:
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'document_id': document_id,
                        'content': chunk_content,  # Original content
                        'enriched_content': enriched_content,  # Content with headers
                        'embedding': embedding,
                        'metadata': metadata,
                        'created_at': datetime.utcnow()
                    }
                    save_chunk_to_mongo(chunk_data)
            
            logger.info(f"  ✓ Created {len(md_docs)} chunks with embeddings")
            
        except Exception as e:
            logger.error(f"  ✗ Error processing {file_path.name}: {e}")
    
    # Save all chunks as JSON for backup
    chunks_data = []
    for doc in all_chunks:
        chunks_data.append({
            'content': doc.page_content,
            'metadata': doc.metadata
        })
    
    chunks_file = Path(f"{output_dir}/chunks") / 'all_chunks.json'
    # with open(chunks_file, 'w', encoding='utf-8') as f:
    #     json.dump({
    #         'total_chunks': len(chunks_data),
    #         'chunks': chunks_data
    #     }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✅ Processing complete!")
    logger.info(f"   Markdown files: {output_dir}/markdown/")
    logger.info(f"   Chunks JSON: {chunks_file}")
    logger.info(f"   Total chunks: {len(all_chunks)}")
    if save_to_mongo:
        logger.info(f"   Documents in MongoDB: {db.documents.count_documents({})}")
        logger.info(f"   Chunks in MongoDB: {db.chunks.count_documents({})}")
    
    return all_chunks

def close_connections():
    """Close database connections"""
    global mongo_client
    if mongo_client:
        mongo_client.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Process HTML files to markdown with MongoDB and embeddings')
    parser.add_argument('--input-dir', help='Input directory with HTML files (default: from env INPUT_DIR)')
    parser.add_argument('--output-dir', help='Output directory (default: from env OUTPUT_DIR)')
    parser.add_argument('--links-json', help='Links JSON file (default: from env LINKS_JSON)')
    parser.add_argument('--no-mongo', action='store_true', help='Skip MongoDB saving')
    
    args = parser.parse_args()
    
    try:
        # Process files
        process_html_files(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            links_json=args.links_json,
            save_to_mongo=not args.no_mongo
        )
    finally:
        # Clean up connections
        close_connections()

if __name__ == "__main__":
    main()