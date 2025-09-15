# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from typing import List, Dict, Any
from fastapi import  HTTPException
from bson import ObjectId



# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_client = None
db = None

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
