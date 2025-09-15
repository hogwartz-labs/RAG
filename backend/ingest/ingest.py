from download import fetch_sitemap_pages
from chunker import chunk_markdown_page
from datetime import datetime
from llm import get_embedding
from backend.db import save_chunk_to_mongo, initialize_connections, create_indexes, save_document_to_mongo

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CHUNK_SIZE = 1000

def main():
    initialize_connections()
    create_indexes()

    pages = fetch_sitemap_pages(sitemap_url="https://www.xml-sitemaps.com/download/thegraph.com-dab32797b/sitemap.xml?view=1", 
                        output_dir="markdown_pages")
    for page in pages:
        page.generate_doc_id()

        # Check if the page is already ingested
        # save document
        document_data = {
                    'document_id': page.id,
                    'title': page.title,
                    'url': page.url,
                    'content': page.content,
                    'created_at': datetime.utcnow(),
        }
        status = save_document_to_mongo(document_data)
        logger.info(f"save document: {page.url} => {status}")

        if status in ['failed', 'duplicate']:
            continue

        extracted_docs = chunk_markdown_page(page, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_SIZE/3)
        for idx, chunk in enumerate(extracted_docs):
            # Create chunk metadata
            chunk_id = f"{chunk.doc_id}_{idx}"

            # Create metadata
            metadata = {
                'url': chunk.url,
                'title': chunk.title,
                'chunk_index': idx,
            }

            # generate chunk
            chunk_data = {
                'chunk_id': chunk_id,
                'document_id': chunk.doc_id,
                'content': chunk.content,
                'metadata': metadata,
                'created_at': datetime.utcnow(),
                # 'embedding': get_embedding(f"{chunk.title}\n{chunk.content}") #embed enriched content
            }

            # done = save_chunk_to_mongo(chunk_data)
            # if done:
            #     logger.info(f"Saved chunk: {idx} for {chunk.url}")
            # else:
            #     logger.info(f"Failed to save chunk: {idx} for {chunk.url}")
    
if __name__ == "__main__":
    main()