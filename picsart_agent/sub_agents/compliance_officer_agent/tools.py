from dotenv import load_dotenv
import os
from google.adk.tools import ToolContext

load_dotenv()


def analyze_image_visual_qa(tool_context: ToolContext, key: str, value: str):

    return "Image is approved"