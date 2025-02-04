import os
from typing import Literal

import pandas as pd

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.types import Command, interrupt
from langgraph.prebuilt import create_react_agent

from utils import instantiate_llm, convert_session_log_to_str
from .state import State

# Initialize the LLM model
llm = instantiate_llm()

# -------------------
# Configuration
# -------------------
UPLOAD_FOLDER = "uploads"

# -------------------
# Tool for PCAP Analyzer Agent
# -------------------
@tool
def select_and_read_csv(state: State) -> str:
    """
    Searches for a CSV file in the UPLOAD_FOLDER:
      - If no CSV is found, returns an error message.
      - If more than one CSV file is found, interrupts to prompt the user for a selection.
      - Otherwise, reads the CSV (as a pandas DataFrame), converts it via
        `convert_session_log_to_str`, and returns the string representation.
    """
    csv_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.csv')]
    
    if not csv_files:
        return "Error: No CSV files found in the uploads directory. Have you uploaded a PCAP file?"
    
    if len(csv_files) > 1:
        # Interrupt to ask the user which CSV file to process.
        selected_file = interrupt({
            "message": "Multiple CSV files found. Please select one to process:",
            "options": csv_files
        })
    else:
        selected_file = csv_files[0]
    
    csv_path = os.path.join(UPLOAD_FOLDER, selected_file)
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return f"Error reading CSV file '{selected_file}': {e}"
    
    return convert_session_log_to_str(df)

# -------------------
# Prompt Template for Analysis
# -------------------
def analysis_prompt(pcap_content: str = "<CSV content not loaded>") -> str:
    """
    Returns the analysis prompt. If the CSV content is missing,
    the prompt instructs the agent to call the 'select_and_read_csv' tool.
    Once CSV content is provided, the agent should produce a concise (max. 25-word)
    summary diagnosis of the UDS protocol messages.
    """
    return f"""You are a diagnostic analyst specializing in Unified Diagnostic Services (UDS) logs.
        If the CSV content is not already provided, call the tool `select_and_read_csv` to load a CSV file.
        
        Once you have the CSV messages, analyze the log and provide a concise summary (max. 25 words)
        that highlights what is happening and notes any potential errors.
        
        Note - Each row represents a request message sent from the diagnostic tool and the ECU's response. The service ID codes (SIDs) and their descriptions are included in the log. Descriptions of the negative response codes (NRCs), if any, are included to the right of the '//'.

        CSV Messages:
        {pcap_content}
        """        

# -------------------
# PCAP Analyzer Agent
# -------------------
# Create the React agent. Note that initially no CSV content is provided,
# so the prompt instructs the agent to use the select_and_read_csv tool.
pcap_analyzer_agent = create_react_agent(
    llm,
    tools=[select_and_read_csv],
    prompt=analysis_prompt()
)


# -------------------
# PCAP Analyzer Node
# -------------------
def pcap_analyzer_node(state: State) -> Command[Literal["supervisor"]]:
    """
    This node invokes the PCAP analyzer agent, which will:
      1. Use the `select_and_read_csv` tool to obtain the CSV PCAP content.
      2. Combine that CSV content with a diagnostic prompt.
      3. Return a concise analysis of the UDS log.
    
    The final message is then sent to the supervisor.
    """
    result = pcap_analyzer_agent.invoke(state)
    # Assume the agent’s result is a dict with a "messages" list;
    # the last message is the final answer.
    final_message = result["messages"][-1]
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=final_message.content, name="pcap_analyzer")
            ]
        },
        goto="supervisor",
    )