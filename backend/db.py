# Load environment variables
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel
load_dotenv()

import os
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from typing import List, Dict, Any, Union
from fastapi import  HTTPException
from bson import ObjectId
import hashlib


# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_client = None
db = None

class ConversationDetails(BaseModel):
    response: str = ""
    token_usage: int = 0
    estimated_cost: float = 0.0
    query: str = ""
    companyId : str = ""
    timestamp: str = ""
    total_time: float = 0.0

executor = ThreadPoolExecutor()

def save_conversation_details_sync(details):
    try:
        result = db.conversations.insert_one(details)
        print(f"Saved conversation with id {result.inserted_id}")
    except Exception as e:
        logger.error(f"Error saving conversation details: {e}")

async def save_conversation_details(details):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, save_conversation_details_sync, details)


#implement rate limit for company
def is_rate_limited(company_id: str) -> bool:
    """Check if a company has exceeded its rate limit"""
    try:
        # Example: Allow max 20 requests per minute
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        
        request_count = db.conversations.count_documents({
            "companyId": company_id,
            "timestamp": {"$gte": one_minute_ago.isoformat()}
        })
        return request_count >= 20
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return False

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

def verify_company_exists(company_id: str) -> bool:
    """Check if a company exists in the MongoDB companies collection"""
    try:
        print(db)
        company = db.companies.find_one({"companyId": company_id})
        print(company)
        return company is not None
    except Exception as e:
        logger.error(f"Error verifying company: {e}")
        return False

def create_company(company_id: str, company_name: str) -> bool:
    """Create a new company in the MongoDB companies collection"""
    try:
        db.companies.insert_one({
            "company_id": company_id,
            "company_name": company_name
        })
        logger.info(f"Company created: {company_id}")
        return True
    except DuplicateKeyError:
        logger.warning(f"Company {company_id} already exists")
        return True

def generate_company_id(company_name: str) -> str:
    """Generate a unique company ID based on the company name"""
    return hashlib.sha256(hashlib.sha256(company_name.encode()).hexdigest().encode()).hexdigest()[:32]

def verify_if_company_present(company_id: str) -> bool:
    """Check if any company exists in the companies collection"""
    try:
        count = db.companies.count_documents({"companyId": company_id})
        return count > 0
    except Exception as e:
        logger.error(f"Error checking companies: {e}")
        return False

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

def serialize_mongodb_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable format"""
    if not doc:
        return doc
    
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, dict):
            serialized[key] = serialize_mongodb_doc(value)
        elif isinstance(value, list):
            serialized[key] = [
                serialize_mongodb_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item
                for item in value
            ]
        else:
            serialized[key] = value
    
    return serialized

def vector_search_chunks(query_vector, limit: int = 10):
    """Perform MongoDB vector search with proper serialization"""
    try:  
        logger.info(f"Starting vector search with query vector length: {len(query_vector)}")
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": max(100, limit * 10),
                    "limit": limit
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            },
            {
                "$project": {
                    "_id": 0,  # Exclude MongoDB's _id field to avoid ObjectId issues
                    "chunk_id": 1,
                    "document_id": 1,
                    "content": 1,
                    "metadata": 1,
                    "score": 1
                }
            }
        ]
        
        logger.info("Executing vector search pipeline...")
        cursor = db.chunks.aggregate(pipeline)
        results = []
        
        for doc in cursor:
            # Serialize the document to handle any remaining ObjectId fields
            serialized_doc = serialize_mongodb_doc(doc)
            results.append(serialized_doc)
        
        logger.info(f"Vector search returned {len(results)} results")
        
        # Log sample results for debugging
        if results:
            for i, result in enumerate(results[:3]):
                score = result.get('score', 'N/A')
                content_preview = result.get('content', '')[:100] + '...' if result.get('content') else 'No content'
                logger.info(f"Result {i+1}: Score={score}, Content={content_preview}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in vector search: {str(e)}")
        return []
    
def retrieve_relevant_chunks(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve relevant chunks from MongoDB based on the query"""
    from llm import get_embedding

    try:
        logger.info(f"Retrieving chunks for query: '{query}'")
        
        # Get embedding
        query_vector = get_embedding(query)
        
        results = vector_search_chunks(query_vector, limit=top_k)
        
        # Ensure all results are properly serialized
        serialized_results = []
        for result in results:
            try:
                # Double-check serialization
                serialized_result = serialize_mongodb_doc(result)
            
                serialized_result.setdefault('chunk_id', 'unknown')
                serialized_result.setdefault('document_id', 'unknown')
                serialized_result.setdefault('content', '')
                serialized_result.setdefault('enriched_content', '')
                serialized_result.setdefault('metadata', {})
                serialized_result.setdefault('score', 0.0)
                
                serialized_results.append(serialized_result)
                
            except Exception as serialize_error:
                logger.error(f"Error serializing result: {serialize_error}")
                # Skip problematic results rather than failing entirely
                continue
        
        logger.info(f"Retrieved {len(serialized_results)} properly serialized chunks for query: '{query}'")
        return serialized_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving relevant chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving relevant chunks: {str(e)}")
    
def get_documents_by_ids(document_ids: Union[List[str], set[str]]):

    try:
        docs = list(db.documents.find({"document_id": {"$in": list(document_ids)}}))
        logger.info(docs)
    except Exception as e:
        return []

    return docs
