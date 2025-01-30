import os
import nest_asyncio
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults
nest_asyncio.apply()  # Needed for running the async function with Flask
from utils import instantiate_llm, pcap_transformation_wrapper

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

# Delete existing PCAP files on startup
for file in os.listdir(UPLOAD_FOLDER):
    file_path = os.path.join(UPLOAD_FOLDER, file)
    if os.path.isfile(file_path) and file.endswith((".pcap", ".csv")):
        os.remove(file_path)

# -------------------
# In-Memory Chat History Storage
# -------------------
chat_histories = {}  # This dictionary will store chat history per session

WELCOME_MESSAGE = {"role": "assistant", "content": "Hi! How can I help you? Options include uploading a PCAP file, or asking a question about e.g. UDS Codes."}

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
agent = create_react_agent(model=llm, tools=tools, checkpointer=checkpointer, prompt=None, debug=True)

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
        chat_histories[session_id] = [WELCOME_MESSAGE]  # Start session with welcome message

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
        # Use uploaded file context if applicable
        uploaded_file_context = ""
        if "uploaded_file_info" in session:
            uploaded_file_context = f"Analyzing the file {session['uploaded_file_info']}. "
        
        full_message = uploaded_file_context + user_message
        
        inputs = {"messages": [{"role": "user", "content": full_message}]}
        result = agent.invoke(inputs, config={"configurable": {"thread_id": 42}})
        assistant_response = result["messages"][-1].content

        # Store messages in memory for the session
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
    session.pop("uploaded_file_info", None)  # Clear uploaded file context
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
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        
        df  = pcap_transformation_wrapper(filepath)
        # Convert DataFrame to an HTML table
        df_html = df.head().to_html(classes="dataframe", index=False)

        # Add DataFrame HTML to chat history
        chat_histories[session_id].append({
            "role": "assistant",
            "content": f"Here's a preview of the uploaded PCAP file:<br>{df_html}"
        })
        chat_histories[session_id].append({
            "role": "assistant",
            "content": "Let me know if you'd like to proceed with further analysis."
        })
        
        # Save DataFrame as CSV
        csv_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename.split('.')[0]}.csv")
        df.to_csv(csv_path, index=False)

        # Store file info in session for context
        session["uploaded_file_info"] = filename

        return jsonify({"message": f"File {filename} uploaded successfully", "filepath": filepath})

    return jsonify({"error": "Invalid file type. Only .pcap files are allowed."}), 400

# -------------------
# Main Entry Point
# -------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
