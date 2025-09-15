from dotenv import load_dotenv
load_dotenv()
from llm import get_embedding
from fastapi import  HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from db.mongodb import db 
import logging
from bson import ObjectId
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    query: str

class QueryRequest(BaseModel):
    query: str

class ChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    enriched_content: str = None
    metadata: Dict[str, Any] = None
    score: float

# Custom JSON encoder for MongoDB ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

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


def check_collection_status():
    """Debug function to check collection and index status"""
    try:
        # Check if chunks collection exists and has data
        chunk_count = db.chunks.count_documents({})
        print(f"Total chunks in collection: {chunk_count}")
        
        # Check if any documents have embeddings
        docs_with_embeddings = db.chunks.count_documents({"embedding": {"$exists": True, "$ne": None}})
        print(f"Documents with embeddings: {docs_with_embeddings}")
        
        # Get a sample document to check structure
        sample_doc = db.chunks.find_one({})
        if sample_doc:
            print(f"Sample document keys: {list(sample_doc.keys())}")
            if 'embedding' in sample_doc:
                embedding_len = len(sample_doc['embedding']) if sample_doc['embedding'] else 0
                print(f"Sample embedding length: {embedding_len}")
        
        # List indexes
        indexes = list(db.chunks.list_indexes())
        index_names = [idx['name'] for idx in indexes]
        print(f"Available indexes: {index_names}")
        
        return chunk_count > 0 and docs_with_embeddings > 0
        
    except Exception as e:
        logger.error(f"Error checking collection status: {str(e)}")
        return False

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
                    "enriched_content": 1,
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
