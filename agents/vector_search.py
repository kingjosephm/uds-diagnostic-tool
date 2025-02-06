import os
from dotenv import load_dotenv



from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings


load_dotenv()

def initialize_vector_store():
    vector_store_path = "./uds/vector_store"
    embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")
    if os.path.exists(vector_store_path):
        vector_store = Chroma(
            persist_directory=vector_store_path,
            embedding_function=embedding_model
        )
    else:
        raise FileNotFoundError(f"Vector store not found at {vector_store_path}. Please ensure the vector store is properly saved to disk.")
    return vector_store


def initialize_vector_search_agent():
    memory = ConversationBufferMemory(return_messages=True)
    vector_store = initialize_vector_store()

    def vector_search(query):
        result = vector_store.similarity_search(query)
        memory.add_user_message(query)
        memory.add_ai_message(str(result))
        return result

    vector_search_tool = Tool(
        name="VectorSearch",
        func=vector_search,
        description="Search the UDS descriptions in the vector database."
    )

    return vector_search_tool, memory