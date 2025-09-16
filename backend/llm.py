import dotenv
dotenv.load_dotenv()

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

import os

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

# os.environ["OPENAI_API_VERSION"] = "2024-08-01-preview"
# os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_OPENAI_ENDPOINT")
# os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
llm = AzureChatOpenAI(
            azure_deployment="gpt-4.1",
            api_version="2025-04-14",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT",""),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT",""),   
    api_key=os.getenv("AZURE_OPENAI_KEY","")
)

def get_embedding(text: str) -> list[float]: # TODO: Cache the embedding results to avoid recalculation
    return embeddings.embed_query(text)