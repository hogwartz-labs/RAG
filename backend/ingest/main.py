#!/usr/bin/env python3
"""
MongoDB Vector Search Service with Flask API
"""

import os
from typing import List, Dict
from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from llm import get_embedding
from db import db

load_dotenv()

app = Flask(__name__)


def vector_search_chunks(query_vector: List[float], limit: int = 10) -> List[Dict]:
    """Perform MongoDB vector search and join with documents"""
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": limit * 10,
                    "limit": limit
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            },
            {
                "$lookup": {
                    "from": "documents",
                    "localField": "document_id",
                    "foreignField": "document_id",
                    "as": "document"
                }
            },
            {
                "$unwind": {
                    "path": "$document",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$project": {
                    "chunk_id": 1,
                    "document_id": 1,
                    "content": 1,
                    "enriched_content": 1,
                    "metadata": 1,
                    "score": 1,
                    "document": {
                        "document_id": "$document.document_id",
                        "title": "$document.title",
                        "content": "$document.content",
                        "metadata": "$document.metadata"
                    }
                }
            }
        ]
        
        return list(db.chunks.aggregate(pipeline))
        
    except Exception:
        return []



@app.route('/search', methods=['POST'])
def search():
    """
    Search endpoint
    POST /search
    Body: {"query": "search text", "limit": 10}
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = min(int(data.get('limit', 10)), 50)
        
        if not query:
            return jsonify({'error': 'Query required'}), 400
        
        # Get embedding
        query_vector = get_embedding(query)
        if not query_vector:
            return jsonify({'error': 'Failed to generate embedding'}), 500
        
        # Try vector search first, fallback to cosine similarity
        results = vector_search_chunks(query_vector, limit)
        
        # Format response
        formatted_results = []
        for chunk in results:
            formatted_results.append({
                'chunk_id': chunk.get('chunk_id', ''),
                'document_id': chunk.get('document_id', ''),
                'score': chunk.get('score', 0.0),
                'content': chunk.get('content', ''),
                'enriched_content': chunk.get('enriched_content', ''),
                'metadata': chunk.get('metadata', {})
            })
        
        return jsonify({
            'query': query,
            'results': formatted_results,
            'count': len(formatted_results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_PORT', '5000')))