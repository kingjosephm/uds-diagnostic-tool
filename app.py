import os
from typing import Literal
from typing_extensions import TypedDict

import nest_asyncio
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END

from utils import instantiate_llm, pcap_transformation_wrapper
from agents.state import State
from agents.internet_search import internet_search_node
from agents.pcap_analyzer import pcap_analyzer_node
from agents.pcap_renderer import pcap_renderer_node

nest_asyncio.apply()  # Needed for running async functions with Flask

# -------------------
# Configuration
# -------------------
UPLOAD_FOLDER = "uploads"  # Folder to store PCAP files
ALLOWED_EXTENSIONS = {"pcap"}

# Initialize Flask app
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = "some-secure-and-random-secret-key"  # Required for session storage

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Delete existing PCAP and CSV files on startup
for file in os.listdir(UPLOAD_FOLDER):
    file_path = os.path.join(UPLOAD_FOLDER, file)
    if os.path.isfile(file_path) and file.lower().endswith((".pcap", ".csv")):
        os.remove(file_path)

# -------------------
# In-Memory Chat History Storage
# -------------------
chat_histories = {}  # This dictionary will store chat history per session

WELCOME_MESSAGE = {
    "role": "assistant",
    "content": "Hi! How can I help you? Options include uploading a PCAP file, asking a question about UDS Codes, or requesting to view a file."
}

# -------------------
# LangGraph Supervisor Agent Setup
# -------------------

# Initialize the LLM model
llm = instantiate_llm()  # No streaming for single query functionality

# Update the list of nodes to include the new "df_renderer" agent.
nodes = ["internet_search", "pcap_analyzer", "pcap_renderer"]
options = nodes + ["FINISH"]

class Router(TypedDict):
    """Worker to route to next. If no worker is needed, route to FINISH."""
    next: Literal[*options]

def supervisor_node(state: MessagesState) -> Command[Literal[*nodes, "__end__"]]:
    system_prompt = (
        "You are a supervisor tasked with managing a conversation between the following workers: "
        f"{nodes}. The conversation context may include an active PCAP file or a request to view  PCAP file. "
        "If a user asks about the active PCAP file, respond with its filename as stored in the conversation context. "
        "If the user's request is ambiguous, ask clarifying questions instead of echoing the query. "
        "Based on the conversation below, determine the next worker to act and respond with that worker's name. "
        "When finished, respond with FINISH."
    )
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]
    if goto == "FINISH":
        goto = END
    return Command(goto=goto)

# Initialize memory saver (could be replaced with SQLite)
memory = MemorySaver()

# Create the state graph
builder = StateGraph(State)
builder.add_edge(START, "supervisor")
builder.add_node("supervisor", supervisor_node)
builder.add_node("internet_search", internet_search_node)
builder.add_node("pcap_analyzer", pcap_analyzer_node)
builder.add_node("pcap_renderer", pcap_renderer_node)
graph = builder.compile(checkpointer=memory, debug=True)
graph.get_graph().draw_mermaid_png(output_file_path='./graph.png')  # generates plot of the graph, saving to root directory

# -------------------
# Flask Routes
# -------------------

@app.before_request
def initialize_chat():
    """Ensures chat history is initialized per session in memory."""
    session_id = session.get("session_id")
    if session_id is None:
        session_id = os.urandom(16).hex()
        session["session_id"] = session_id
    
    if session_id not in chat_histories:
        chat_histories[session_id] = [WELCOME_MESSAGE]
        session.pop("uploaded_file_info", None)

@app.route("/", methods=["GET"])
def index():
    """Render the main chat interface."""
    return render_template("index.html")

@app.route("/history", methods=["GET"])
def chat_history():
    """Retrieve the stored chat history for the session."""
    session_id = session.get("session_id")
    return jsonify({"history": chat_histories.get(session_id, [WELCOME_MESSAGE])})

@app.route("/chat", methods=["POST"])
def chat():
    """Handles chat messages and stores them in memory per session."""
    session_id = session.get("session_id")
    data = request.get_json()
    user_message = data.get("message", "").strip()

    try:
        # Include the full conversation history to provide context.
        conversation = chat_histories[session_id] + [{"role": "user", "content": user_message}]
        inputs = {"messages": conversation}
        result = graph.invoke(inputs, config={"configurable": {"thread_id": 42}, "recursion_limit": 5})
        assistant_response = result["messages"][-1].content

        chat_histories[session_id].append({"role": "user", "content": user_message})
        chat_histories[session_id].append({"role": "assistant", "content": assistant_response})

        return jsonify({"response": assistant_response})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["GET"])
def reset_chat():
    """Clears chat history for the current session and re-adds the welcome message."""
    session_id = session.get("session_id")
    chat_histories[session_id] = [WELCOME_MESSAGE]
    session.pop("uploaded_file_info", None)
    return jsonify({"message": "Chat history cleared."})

def allowed_file(filename):
    """Check if the uploaded file has a .pcap extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=["POST"])
def upload_file():
    """Endpoint for uploading PCAP files."""
    session_id = session.get("session_id")
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Delete any existing PCAP or CSV files in the UPLOAD_FOLDER.
        for f in os.listdir(app.config["UPLOAD_FOLDER"]):
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], f)
            if os.path.isfile(file_path) and f.lower().endswith((".pcap", ".csv")):
                os.remove(file_path)
        
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        
        # Process the PCAP file and write out its CSV version.
        df = pcap_transformation_wrapper(filepath)
        csv_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename.split('.')[0]}.csv")
        df.to_csv(csv_path, index=False)

        # Update the session with the new file's name.
        session["uploaded_file_info"] = filename

        # Reset the conversation context so that the new file is clearly active.
        chat_histories[session_id] = [
            {"role": "assistant", "content": f"Active PCAP file is now '{filename}'."}
        ]
        # Automatically trigger analysis for the new file using the pcap_analyzer.
        inputs = {"messages": chat_histories[session_id] + [{"role": "user", "content": "Please analyze the uploaded PCAP file."}]}
        result = graph.invoke(inputs, config={"configurable": {"thread_id": 42}})
        analysis_response = result["messages"][-1].content
        chat_histories[session_id].append({"role": "assistant", "content": analysis_response})

        return jsonify({"message": f"File {filename} uploaded successfully", "filepath": filepath})

    return jsonify({"error": "Invalid file type. Only .pcap files are allowed."}), 400

# -------------------
# Main Entry Point
# -------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
