from fastapi import FastAPI, HTTPException,Depends, Header
from pydantic import BaseModel
from typing import List
from agent import AdvancedRAGRetriever
from retriever import QueryRequest
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from db import initialize_connections,verify_company_exists,save_conversation_details,ConversationDetails,is_rate_limited

from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import asyncio
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚡ For development use "*" or specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Initialize DB connections on startup."""
    try:
        logger.info("Initializing database connections...")
        initialize_connections()
        logger.info("Database connections initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Optional: close DB connections on shutdown if needed."""
    logger.info("Shutting down application...")

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/query")
def query_endpoint(request: QueryRequest):
    try:
        print(f"Received query: {request.query}")
        retriever = AdvancedRAGRetriever()
        results = retriever.retrieve_and_answer(request.query)
        return {"results": results}
    except HTTPException as e:
        logger.error(f"HTTP error occurred: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing query")
    
from fastapi.responses import StreamingResponse
import json
import asyncio

def verify_api_key(x_api_key: str = Header(None)):
    print(x_api_key)
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key is required")
    if x_api_key and verify_company_exists(x_api_key):
        return x_api_key
    else:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/query/stream")
async def query_stream_endpoint(request: QueryRequest, api_key: str = Depends(verify_api_key)):
    try:
        if is_rate_limited(api_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        
        start_time = datetime.now()
        retriever = AdvancedRAGRetriever()
        result_generator = retriever.retrieve_and_answer(request.query, stream=True)
        

        async def event_generator():
            for chunk in result_generator:
                text = getattr(chunk, "content", str(chunk))
                yield f"data: {json.dumps({'content': text})}\n\n"
                await asyncio.sleep(0)

            # End of stream signal
            yield "data: [DONE]\n\n"
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            token_count = getattr(retriever.conversation_details, 'token_usage', 0)
            estimated_cost = getattr(retriever.conversation_details, 'estimated_cost', 0.0)
            response = getattr(retriever.conversation_details, 'response', '')

            conversation_details = ConversationDetails(
                response=response,
                token_usage=token_count,
                estimated_cost=estimated_cost,
                query=request.query,
                companyId=api_key,
                timestamp=datetime.now().isoformat(),
                total_time=processing_time
            )
            # Run this as a background process
            asyncio.create_task(save_conversation_details(conversation_details.__dict__))

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing streaming query")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)