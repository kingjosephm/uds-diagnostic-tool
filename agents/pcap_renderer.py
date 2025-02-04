import os
from typing import Literal

import pandas as pd

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError

from utils import instantiate_llm
from .state import State

# -------------------
# Configuration
# -------------------
UPLOAD_FOLDER = "uploads"

# -------------------
# Tool for the PCAP Renderer Agent
# -------------------
@tool
def render_dataframe(state: State) -> str:
    """
    Searches for a (PCAP) CSV file in the UPLOAD_FOLDER and renders it as HTML.
    - If the user's latest message contains "whole" or "all", render the entire dataframe.
    - Otherwise, render only the first 5 rows.
    """
    csv_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.csv')]
    if not csv_files:
        return "Error: No CSV file found in the uploads directory."
    
    # For simplicity, if there is more than one CSV, choose the first.
    selected_file = csv_files[0]
    csv_path = os.path.join(UPLOAD_FOLDER, selected_file)
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV file: {e}"
    
    html = df.head().to_html(classes="dataframe", index=False)
    
    return html

def renderer_prompt() -> str:
    """
    Returns the prompt for the PCAP Renderer Agent.
    """
    return (
        "You are a file viewer agent whose sole responsibility is to render a PCAP file (as a CSV) as HTML. "
        "Your output must contain ONLY the HTML representation of the CSV file and nothing else. "
        "When a user requests to view the file, check if the user's query contains the words 'whole' or 'all'. "
        "If it does, display the entire CSV file; otherwise, display only the first 5 rows. "
        "Do not include any extra commentary, apologies, or additional text."
    )

# -------------------
# PCAP Renderer Agent Creation
# -------------------
llm = instantiate_llm()

pcap_renderer_agent = create_react_agent(
    llm,
    tools=[render_dataframe],
    prompt=renderer_prompt()
)

def pcap_renderer_node(state: State) -> Command[Literal["supervisor"]]:
    """
    This node invokes the PCAP renderer agent.
    It calls the `render_dataframe` tool to render the PCAP CSV file as HTML,
    then sends that HTML rendering to the supervisor.
    
    Note: The HTML rendering is NOT stored in the conversation history.
    """
    try:
        result = pcap_renderer_agent.invoke(state, {"recursion_limit": 5})
    except Exception as e:
        # If an error occurs, raise a recursion error (or any appropriate error)
        raise GraphRecursionError("Error in PCAP renderer: " + str(e))
    
    final_message = result["messages"][-1]
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=final_message.content, name="pcap_renderer")
            ]
        },
        goto="supervisor",
    )
