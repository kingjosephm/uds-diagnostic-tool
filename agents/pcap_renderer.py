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
def render_dataframe_head(state: State) -> str:
    """
    Loads the PCAP CSV file and renders ONLY the first 5 rows as HTML.
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

@tool
def render_dataframe_full(state: State) -> str:
    """
    Loads the PCAP CSV file and renders the FULL DATAFRAME as HTML.
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
    
    html = df.to_html(classes="dataframe", index=False)
    
    return html

def renderer_prompt() -> str:
    """
    Returns the prompt for the PCAP Renderer Agent.
    """
    return (
        "You are a file viewer agent whose sole responsibility is to render a PCAP file (as a CSV) as HTML. Your output must contain ONLY the HTML representation of the CSV file and nothing else."
        "\n"
        "You have two tools at your disposal: `render_dataframe_head` and `render_dataframe_full`. The former renders only the first 5 rows of the CSV file, while the latter renders the entire CSV file."
        "Use `render_dataframe_head` by default, otherwise `render_dataframe_full` if the user requests to view the full PCAP file using words like 'full', 'all', or 'complete'."
    )

# -------------------
# PCAP Renderer Agent Creation
# -------------------
llm = instantiate_llm()

pcap_renderer_agent = create_react_agent(
    llm,
    tools=[render_dataframe_head, render_dataframe_full],
    prompt=renderer_prompt()
)

def pcap_renderer_node(state: State) -> Command[Literal["supervisor"]]:
    """
    This node invokes the PCAP renderer agent.
    It calls either the `render_dataframe_head` tool by default, or if the user asks to view the full PCAP file using words like 'full', 'all', or 'complete' the `render_dataframe_full` tool. If you are confused, ask the user to clarify.
    """
    result = pcap_renderer_agent.invoke(state)
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="pcap_renderer")
            ]
        },
        goto="supervisor",
    )
