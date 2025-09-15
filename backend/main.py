from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from agent import AdvancedRAGRetriever
from retriever import QueryRequest
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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

@app.post("/query/stream")
async def query_stream_endpoint(request: QueryRequest):
    try:
        retriever = AdvancedRAGRetriever()
        result_generator = retriever.retrieve_and_answer(request.query, stream=True)

        async def event_generator():
            for chunk in result_generator:
                text = getattr(chunk, "content", str(chunk))
                yield f"data: {json.dumps({'content': text})}\n\n"
                await asyncio.sleep(0)

            # End of stream signal
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing streaming query")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)