from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import sqlite3
import pandas as pd
from typing import Tuple
import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
openai_api_key = os.getenv('OPENAI_API_KEY')  # Get the OPENAI_API_KEY from environment variables

# Database setup
sqlite_path = './lookup/uds_codes.db'  # Path to your SQLite database
conn = sqlite3.connect(sqlite_path)



# Define query functions for Request (SID) codes
def query_request_code(sid):
    """Query SQLite database for a SID code with 'Service Request' type."""
    query = "SELECT Summary FROM uds_codes WHERE Code = ? AND Type = 'Service Request'"
    result = pd.read_sql_query(query, conn, params=(sid,))
    return result.iloc[0, 0] if not result.empty else "Code not found"

# Define query function for Response (SID/NRC) codes
def query_response_code(reply):
    """Query SQLite database for a Reply code with either 'Service Response' or 'Negative Response Code' types."""
    query = "SELECT Summary FROM uds_codes WHERE Code = ? AND Type IN ('Service Response', 'Negative Response Code')"
    result = pd.read_sql_query(query, conn, params=(reply,))
    return result.iloc[0, 0] if not result.empty else "Code not found"


# Function for the lookup agent to interpret the Excel workbook
def lookup_codes_from_workbook(llm, workbook_path):
    """Read an Excel workbook, look up explanations for each SID Request and SID/NRC Reply code, and return summaries."""
    # Load the workbook
    df = pd.read_excel(workbook_path)
    
    template = """ You are a helpful assistant that summarizes Unified Diagnostic Service (UDS) network communication between a SID request and SID/NRC response.
    
    Use the provided metadata to summarize what is being requested and the system response. Here is the data:
    
    Request: {request}
    Response: {response}
    
    Provide a concise (max. 15 word) summary using only the information given.
    
    """
    
    prompt = PromptTemplate(
        input_variables=["request", "response"],
        template=template,
    )
    
    chain = prompt | llm
    
    
    # Iterate through each row, looking up the SID and Reply explanations and creating a summary
    summaries = []
    for _, row in df.iterrows():
        request_code = row['sid']
        response_code = row['reply']
        
        # Look up explanations
        request = query_request_code(request_code)
        response = query_response_code(response_code)
        
        summary = chain.invoke({"request": request, "response": response}).content
        
        # Append summary for each row
        summaries.append(summary)
        
    for i in summaries:
        print(i)

    return summaries


# Initialize the LangChain agent with the lookup tool
llm = ChatOpenAI(api_key=openai_api_key, temperature=0, model="gpt-4o-mini")



if __name__ == "__main__":

    path = './data/PreconditionCheckNegResp.xlsx'
    summaries = lookup_codes_from_workbook(llm, path)
    
