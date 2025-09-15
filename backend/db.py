# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from typing import List, Dict, Any

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_connections():
    """Initialize MongoDB and Azure OpenAI connections from environment variables"""
    global mongo_client, db
    
    # MongoDB configuration
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    database_name = os.getenv('DATABASE_NAME', 'rag_system')
        
    # Initialize connections
    mongo_client = MongoClient(mongo_url)
    db = mongo_client[database_name]
        
    logger.info(f"Connected to MongoDB: {database_name}")

def create_indexes():
    """Create MongoDB indexes for better query performance"""
    try:
        # Document indexes
        db.documents.create_index("document_id", unique=True)
        
        # Chunk indexes
        db.chunks.create_index("document_id")
        db.chunks.create_index("chunk_id", unique=True)
        # db.chunks.create_index("chunk_index")
        # db.chunks.create_index([("embedding", "2dsphere")])  # For vector similarity
        
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"Error creating indexes: {e}")

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
    
def save_document_to_mongo(document_data: Dict) -> str:
    """Save document to MongoDB and return document_id"""
    try:
        result = db.documents.insert_one(document_data)
        logger.info(f"Document saved with ID: {document_data['document_id']}")
        return 'created'
    except DuplicateKeyError:
        logger.warning(f"Document {document_data['document_id']} already exists")
        return 'duplicate'
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        return 'failed'

def close_connections():
    """Close database connections"""
    global mongo_client
    if mongo_client:
        mongo_client.close()
