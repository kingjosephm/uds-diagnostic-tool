import pandas as pd
from typing import Literal
import sqlite3

from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from utils import instantiate_llm
from agents.state import State  # Adjust if needed


# Initialize the LLM model
llm = instantiate_llm()


# -------------------
# SQL Search Tool
# -------------------
@tool
def sql_search(query: str) -> str:
    """
    Tool for querying information about specific UDS codes.
    Given an executable SQL query, this function queries the SQLite database table "descriptions"
    and returns matching records.
    
    Args:
      query (str): The SQL query to execute.
    
    Returns:
      str: A string representation of the matching records, or an error message if the query fails.
    """
    print("Querying database with:", query)
    try:
        # Create a new connection for this function call
        with sqlite3.connect('uds/uds_codes.db') as conn:
            df = pd.read_sql(query, conn)
        if df.empty:
            return "No matching records found."
        return df.to_string(index=False)
    except Exception as e:
        return f"SQL error: {str(e)}"

# -------------------
# Prompt & React Agent for UDS Codes
# -------------------
def prompt() -> str:
    """
    Returns the prompt for the UDS Code agent.
    This prompt instructs the agent to answer user queries about Unified Diagnostic Service (UDS) codes
    by formulating an executable SQL query against the SQLite database table 'descriptions'.
    
    The table schema is as follows:
      - Code: string, a hexadecimal service or NRC code.
      - Type: string, contains "SID" for service or "NRC" for negative response code.
      - Description: string, description about the particular code.
    
    Use ONLY the provided `sql_search` tool to retrieve detailed UDS code information.
    If the executed query returns no results, respond with 
    'I couldn’t find enough details on this in the database.' Always provide clear, concise answers 
    based on the retrieved information.
    """
    return (
        "You are an expert on Unified Diagnostic Service (UDS) codes. Your job is to answer user queries "
        "about UDS codes by formulating an executable SQL query against the SQLite database table 'descriptions'. "
        "The table 'descriptions' has the following schema: "
        "Code (string): a hexadecimal service or NRC code; "
        "Type (string): contains 'SID' for service or 'NRC' for negative response code; "
        "Description (string): a description of the particular code. "
        "Use ONLY the provided `sql_search` tool to retrieve detailed UDS code information. "
        "Always provide clear, concise answers based on the retrieved information."
    )


uds_description_search_agent = create_react_agent(
    llm,
    tools=[sql_search],
    prompt=prompt()
)

# -------------------
# UDS Description Search Node
# -------------------
def uds_description_search_node(state: State) -> Command[Literal["supervisor"]]:
    """
    Processes a query for UDS code information by:
      1. Delegating the query to the UDS description search agent.
      2. Retrieving the agent's response.
      3. Constructing a command to update the supervisor with the result.
    
    The `state` parameter contains the user's query and additional context.
    """
    result = uds_description_search_agent.invoke(state)
    answer = result["messages"][-1].content

    return Command(
        update={
            "messages": [
                HumanMessage(content=answer, name="uds_description_search")
            ]
        },
        goto="supervisor",
    )