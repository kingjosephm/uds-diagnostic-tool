from flask import Flask, render_template, request, jsonify
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults

from utils import instantiate_llm

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


##################################################
#####       Flask App Configuration         ######
##################################################

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "some-secure-and-random-secret-key"  # Replace with a secure key in production

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

# -------------------
# Main Entry Point
# -------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
