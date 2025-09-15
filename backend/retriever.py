from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel
from typing import List, Dict, Any
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


