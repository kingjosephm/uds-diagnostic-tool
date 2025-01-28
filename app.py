import uuid
from flask import Flask, render_template, request, jsonify, session, Response

# LangGraph and LangChain imports
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from utils import instantiate_llm


# Initialize the LLM model
llm = instantiate_llm()

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}
    
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()

def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)

# -------------------
# Helper Function to Get or Create thread_id
# -------------------

def get_thread_id():
    """
    Retrieves the thread_id from the user's session.
    If it doesn't exist, generates a new UUID and stores it in the session.
    """
    if 'thread_id' not in session:
        session['thread_id'] = str(uuid.uuid4())
    return session['thread_id']


# -------------------
# Flask Routes
# -------------------

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
    return jsonify({"response": "H! How can I help you?"})

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint to handle chat messages.
    Streams each word as it is being generated using LangGraph's graph.stream().
    """
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"response": "Please enter a message."}), 400

    # Retrieve or create a unique thread_id for the session
    thread_id = get_thread_id()

    def generate():
        try:
            inputs = {"messages": [{"role": "user", "content": user_message}]}
            for event in graph.stream(inputs, stream_mode="messages"):                
                # Unpack the tuple returned by the event
                if isinstance(event, tuple) and len(event) == 2:
                    ai_message_chunk, metadata = event
                    # Ensure the chunk has non-empty content
                    if ai_message_chunk.content.strip():
                        for chunk in ai_message_chunk.content.splitlines(keepends=True):  # Split by lines, preserving newlines
                            yield chunk  # Yield each line directly
                    else:
                        continue
                else:
                    print(f"Unexpected event structure: {event}")
        except Exception as e:
            print(f"Error during graph stream: {e}")
            yield "Sorry, something went wrong processing your request."

    return Response(generate(), content_type="text/plain")



# -------------------
# Main Entry Point
# -------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)
