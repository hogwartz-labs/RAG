"""
Advanced RAG Retriever
Generates subqueries, retrieves relevant chunks, and provides comprehensive answers
"""

import logging
import asyncio
from typing import List, Dict, Any, Set
from dataclasses import dataclass
import json
import hashlib
from datetime import datetime
import re

# Import your existing modules
from llm import llm
from db import retrieve_relevant_chunks, get_documents_by_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """Data class for query results"""
    original_query: str
    subqueries: List[str]
    context: str
    final_answer: str

class AdvancedRAGRetriever:
    """Advanced RAG retriever with subquery generation and deduplication"""
    
    def __init__(self, top_k_per_subquery: int = 5, max_context_length: int = 128000):
        self.top_k_per_subquery = top_k_per_subquery
        self.max_context_length = max_context_length
        
    def generate_subqueries(self, original_query: str) -> List[str]:
        """Generate 3 diverse subqueries for comprehensive retrieval"""
        
        subquery_prompt = f"""
      Generate 3 search queries to search for to answer the user's question. \
These search queries should be diverse in nature - do not generate \
repetitive ones.

<original_query>
{original_query}
</original_query>

<instructions>
- Generate exactly 3 subqueries
- Each subquery should be a complete, standalone question
- Vary the language and terminology used
- Consider different angles: definitions, applications, mechanisms, examples, etc.
- Keep each subquery focused and specific
- Output as list of strings.
</instructions>

<output_format>
["Your first subquery here","Your second subquery here","Your third subquery here"]
</output_format>

Generate the subqueries now:
"""
        
        try:
            logger.info(f"Generating subqueries for: '{original_query}'")
            response = llm.invoke(subquery_prompt)
            subqueries = response.content
            subqueries = json.loads(subqueries)
            
            if len(subqueries) < 3:
                logger.warning(f"Only generated {len(subqueries)} subqueries, expected 3")
                # Fallback: create simple variations
                while len(subqueries) < 3:
                    subqueries.append(f"{original_query} - variation {len(subqueries) + 1}")
            
            logger.info(f"Generated subqueries: {subqueries}")
            return subqueries
            
        except Exception as e:
            logger.error(f"Error generating subqueries: {str(e)}")
            # Fallback to simple variations
            return[original_query]
    
    def retrieve_for_subqueries(self, subqueries: List[str]) -> List[Dict[str, Any]]:
        """Retrieve chunks for all subqueries"""
        all_chunks = []
        
        for i, subquery in enumerate(subqueries, 1):
            try:
                logger.info(f"Retrieving for subquery {i}: '{subquery}'")
                chunks = retrieve_relevant_chunks(subquery, top_k=self.top_k_per_subquery)
                
                # Add subquery metadata to each chunk
                for chunk in chunks:
                    chunk['source_subquery'] = subquery
                    chunk['subquery_index'] = i
                
                all_chunks.extend(chunks)
                logger.info(f"Retrieved {len(chunks)} chunks for subquery {i}")
                
            except Exception as e:
                logger.error(f"Error retrieving for subquery '{subquery}': {str(e)}")
                continue
        
        logger.info(f"Total chunks retrieved: {len(all_chunks)}")
        return all_chunks
    
    def deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate chunks based on content similarity and chunk_id"""
        if not chunks:
            return []
        
        unique_chunks = []
        seen_chunk_ids: Set[str] = set()
        seen_content_hashes: Set[str] = set()
        
        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            content = chunk.get('content', '')
            
            # Skip if we've seen this chunk_id
            if chunk_id and chunk_id in seen_chunk_ids:
                logger.debug(f"Skipping duplicate chunk_id: {chunk_id}")
                continue
            
            # Create content hash for similarity detection
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Skip if we've seen very similar content
            if content_hash in seen_content_hashes:
                logger.debug(f"Skipping duplicate content: {content[:50]}...")
                continue
            
            # Add to unique collection
            unique_chunks.append(chunk)
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            seen_content_hashes.add(content_hash)
        
        # Sort by relevance score (highest first)
        unique_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        logger.info(f"Deduplicated {len(chunks)} chunks to {len(unique_chunks)} unique chunks")
        return unique_chunks
    
    def truncate_context(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Truncate context to fit within max_context_length"""
        if not chunks:
            return []
        
        total_length = 0
        truncated_chunks = []
        
        for chunk in chunks:
            # Use enriched_content if available, otherwise content
            content = chunk.get('content', '')
            content_length = len(content)
            
            if total_length + content_length <= self.max_context_length:
                truncated_chunks.append(chunk)
                total_length += content_length
            else:
                logger.info(f"Truncated context at {len(truncated_chunks)} chunks ({total_length} chars)")
                break
        
        return truncated_chunks
    
    def build_context_string(self, chunks: List[Dict[str, Any]]) -> str:
        """Build formatted context string from chunks"""
        if not chunks:
            return "No relevant context found."
        
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            score = chunk.get('score', 0)
            source = chunk.get('metadata', {}).get('url', 'Unknown Source')
            title = chunk.get('metadata', {}).get('title', 'Unknown Title')
            
            context_part = f"""
<context_chunk id="{i}" score="{score:.3f}" source_url="{source}" title="{title}">
{content}
</context_chunk>"""
            
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def generate_final_answer(self, original_query: str, subqueries: List[str], context: str,stream:False) -> str:
        """Generate comprehensive answer using retrieved context"""
        
        answer_prompt = f"""
<task>
Your are an expert research assistant working for The Graph is a blockchain data solution that powers applications, analytics, and AI on 90+ chains.\
The Graph's core products include the Token API for web3 apps, Subgraphs for indexing smart contracts, \
and Substreams for real-time and historical data streaming.
</task>

<instructions>
1. Synthesize information from ALL relevant context chunks
2. Provide a comprehensive answer that addresses the original query
3. Include specific details, examples, and explanations where available
4. Structure your response clearly with appropriate sections/paragraphs
5. If the context contains conflicting information, acknowledge and explain the differences
6. Be factual and cite specific information from the context when relevant
7. If the context is insufficient to fully answer the query, acknowledge this limitation
8. Use a professional but accessible tone
9. **inline citations are must in format [title](URL)**
10. If title cannot be drawn, generate a short title based on the content
11. Return the final response as string
</instructions>

<output_format>
Your comprehensive answer here, well-structured and drawing from the provided context with inline citations.
</output_format>

<retrieved_context>
{context}
</retrieved_context>

<original_query>
{original_query}
</original_query>

Generate your response now:
"""
        
        try:
            logger.info("Generating final answer...")
            if stream:
                # assume llm.stream returns an iterator of tokens/chunks
                return llm.stream(answer_prompt)  
            else:
                response = llm.invoke(answer_prompt)
                answer = response.content
                logger.info("Final answer generated successfully")
                return answer
            
        except Exception as e:
            logger.error(f"Error generating final answer: {str(e)}")
            return f"I apologize, but I encountered an error while generating the final answer: {str(e)}"

    def retrieve_and_answer(self, query: str, stream=False) -> QueryResult:
        """Main method: generate subqueries, retrieve, deduplicate, and answer"""
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting advanced retrieval for query: '{query}'")
            subqueries = self.generate_subqueries(query)
            all_chunks = self.retrieve_for_subqueries(subqueries)

            unique_chunks = self.deduplicate_chunks(all_chunks)
            unique_docs = self.get_full_docs(unique_chunks)

            final_chunks = self.truncate_context(unique_docs)
            context_string = self.build_context_string(final_chunks)

            final_answer = self.generate_final_answer(query, subqueries, context_string, stream=stream)

        
            if stream:
                return final_answer

            processing_time = (datetime.now() - start_time).total_seconds()

            return QueryResult(
                original_query=query,
                subqueries=subqueries,
                final_answer=final_answer,
                context=context_string
            )

            result = QueryResult(
                original_query=query,
                subqueries=subqueries,
                final_answer=final_answer,
                context=context_string
            )
            
            logger.info(f"Advanced retrieval completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in retrieve_and_answer: {str(e)}")
            
            # Return error result
            return QueryResult(
                original_query=query,
                subqueries=[],
                chunks=[],
                unique_chunks=[],
                final_answer=f"I apologize, but I encountered an error while processing your query: {str(e)}",
                metadata={"error": str(e), "timestamp": datetime.now().isoformat()}
            )
        
    def get_full_docs(self, chunk_ids):
        doc_ids = list(set([chunk.get('document_id', '') for chunk in chunk_ids]))
        return get_documents_by_ids(doc_ids)

# Convenience functions for easy usage
def quick_answer(query: str, top_k_per_subquery: int = 5) -> str:
    """Quick function to get just the final answer"""
    retriever = AdvancedRAGRetriever(top_k_per_subquery=top_k_per_subquery)
    result = retriever.retrieve_and_answer(query)
    return result.final_answer

def test_retriever():
    """Test the advanced retriever"""
    test_queries = [
        "What are stem cells?",
    ]
    
    retriever = AdvancedRAGRetriever()
    
    for query in test_queries:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing query: {query}")
        logger.info(f"{'='*50}")
        
        result = retriever.retrieve_and_answer(query)
        logger.info(f"Original Query: {result.final_answer}")

# if __name__ == "__main__":
#     # Run test
#     test_retriever()