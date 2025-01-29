import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults

from utils import instantiate_llm

# -------------------
# Configuration
# -------------------

UPLOAD_FOLDER = "uploads"  # Folder to store PCAP files
ALLOWED_EXTENSIONS = {"pcap"}

# Initialize Flask app
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.secret_key = "some-secure-and-random-secret-key"  # Replace with a secure key in production

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------
# LangGraph Agent Setup
# -------------------

# Initialize memory saver (could be replaced with SQLite)
memory = MemorySaver()

# Initialize the LLM model
llm = instantiate_llm()  # No streaming for single query functionality

# Provide agent tools
tools = [TavilySearchResults(max_results=1)]

# Create the checkpointer for memory saving
checkpointer = MemorySaver()

# Create the React agent
agent = create_react_agent(model=llm, 
                           tools=tools, 
                           checkpointer=checkpointer, 
                           prompt=None, debug=True)

# -------------------
# Flask Routes
# -------------------

@app.route("/", methods=["GET"])
def index():
    """Render the main chat interface."""
    return render_template("index.html")

@app.route("/welcome", methods=["GET"])
def welcome():
    """
    Endpoint to send a welcome message.
    This should be called by the front end when the chat interface loads.
    """
    return jsonify({"response": "Hi! How can I help you?"})

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint for processing a single user message.
    Accepts a JSON payload with a single user message.
    """
    data = request.get_json()
    user_message = data.get("message", "").strip()
    
    try:
        # Create a state with the user's message
        inputs = {"messages": [{"role": "user", "content": user_message}]}
        
        # Run the graph to generate the response
        result = agent.invoke(inputs, config={"configurable": {"thread_id": 42}})
        
        return jsonify({"response": result["messages"][-1].content})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def allowed_file(filename):
    """Check if the uploaded file has a .pcap extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Endpoint for uploading PCAP files.
    Only allows .pcap files and stores them in the 'uploads' directory.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # TODO: Process PCAP file (e.g., parsing, analyzing network traffic)
        
        return jsonify({"message": f"File {filename} uploaded successfully", "filepath": filepath})

    return jsonify({"error": "Invalid file type. Only .pcap files are allowed."}), 400

# -------------------
# Main Entry Point
# -------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
