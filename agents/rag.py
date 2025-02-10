import os
from typing import Literal

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from utils import instantiate_llm
from agents.state import State  # Adjust this import if your state module is elsewhere

# Initialize the LLM model
llm = instantiate_llm()

# -------------------
# UDS Code Vector Store & Retrieval Tool
# -------------------

def initialize_vector_store():
    """
    Loads the Chroma vector store containing UDS code information.
    Expects the vector store to be saved at './uds/vector_store'.
    """
    vector_store_path = "./uds/vector_store"
    embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")
    if os.path.exists(vector_store_path):
        vector_store = Chroma(
            persist_directory=vector_store_path,
            embedding_function=embedding_model
        ).as_retriever(search_type="mmr", search_kwargs={'k': 5})
    else:
        raise FileNotFoundError(
            f"Vector store not found at {vector_store_path}. "
            "Please ensure the vector store is properly saved to disk."
        )
    return vector_store

@tool
def vector_search(query: str) -> str:
    """
    Tool for retrieving UDS code information.
    Given a query, it queries the Chroma vector store and returns relevant documents.
    """
    vector_store = initialize_vector_store()
    results = vector_store.get_relevant_documents(query)
    # Return the results as a string; you can adjust formatting as needed.
    return str(results)

# -------------------
# RAG Prompt & React Agent for UDS Codes
# -------------------

def rag_prompt() -> str:
    """
    Returns the prompt for the UDS Code RAG agent.
    This prompt instructs the agent to answer user queries about Unified Diagnostic Service codes.
    It should use the provided `vector_search` tool when detailed retrieval is needed.
    """
    return (
        "You are an expert on Unified Diagnostic Service (UDS) codes. "
        "Your job is to answer user queries about UDS codes (e.g., 'list all of the UDS service codes', "
        "'tell me more about the code 0x22'). When needed, use the provided `vector_search` tool to query "
        "the vector store containing detailed UDS code information. Provide clear, concise answers."
    )

uds_code_search_agent = create_react_agent(
    llm,
    tools=[vector_search],
    prompt=rag_prompt()
)

# -------------------
# UDS Code Search Node
# -------------------

def uds_code_search_node(state: State) -> Command[Literal["supervisor"]]:
    """
    Processes a UDS code query by:
      1. Delegating the query to the UDS code RAG agent.
      2. Retrieving the agent’s response.
      3. Constructing a command to update the supervisor with the result.
    
    The `state` parameter contains the user’s query and additional context.
    """
    result = uds_code_search_agent.invoke(state)
    
    # Extract the final answer from the agent's response
    answer = result["messages"][-1].content

    return Command(
        update={
            "messages": [
                HumanMessage(content=answer, name="uds_code_search")
            ]
        },
        goto="supervisor",
    )
