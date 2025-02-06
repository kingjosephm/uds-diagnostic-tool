from typing import Literal
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from utils import instantiate_llm
from .state import State

# Initialize the LLM model
llm = instantiate_llm()


internet_search_agent = create_react_agent(
    llm, tools=[TavilySearchResults(max_results=1)], prompt="You are a researcher that searches the internet and returns results. Do not do any analysis."
)

def internet_search_node(state: State) -> Command[Literal["supervisor"]]:
    result = internet_search_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="internet_search")
            ]
        },
        goto="supervisor",
    )