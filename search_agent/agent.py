# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import VertexAiSearchTool

import os
import google.auth

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


SEARCH_ENGINE_PATH = f"projects/{project_id}/locations/global/collections/default_collection/engines/navy-federal_1772579176788"
search_ncu_website = VertexAiSearchTool(search_engine_id=SEARCH_ENGINE_PATH)




def get_mortgage_rate():
    """Simulates an internal search for the current mortgage rate.

    Returns:
        Return a string that says the mortgage rate is 6.25%
    """

    return("The current mortgage rate is 6.25%")


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"

search_agent = Agent(
    model='gemini-3-flash-preview',
    name='SearchAgent',
    instruction="""
    You're a specialist in helping customers with Navy Federal Credit Union questions. 
    YOUR TOOL:
    1. 'search_ncu_website': Use this tool to search the Navy Federal Credit Union website for information.

    OUTPUT FORMAT:
    1. If you find the answer to the user's question, respond with the answer.
    2. If you don't find the answer to the user's question, say so.
    """,
    tools=[search_ncu_website],
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-3-flash-preview",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""
    You are a helpful Navy Federal Credit Union assistant designed to provide help with Navy Federal Credit Union questions like mortgage rate information.
    For questions that are  related to mortgage rates delegate to the get_mortgage_rate tool.
    For questions that are related to Navy Federal Credit Union website information delegate to the search_agent tool.
    If you don't know the answer, say so.
    """,
    tools=[AgentTool(agent=search_agent),get_mortgage_rate],
)

app = App(
    root_agent=root_agent,
    name="app",
)
