from dotenv import load_dotenv
import os, time, requests
from google.genai import types
from google.adk.tools import ToolContext

load_dotenv()
#https://docs.picsart.io/reference/genai-smart-background

PICSART_API_KEY = os.getenv("PICSART_API_KEY")
PICSART_URL = "https://genai-api.picsart.io/v1/painting/replace-background"

async def smart_background(tool_context: ToolContext, filename: str, prompt: str) -> str:
    """
    Uses Picsart GenAI to replace the background of an image artifact based on a text prompt.
    
    Args:
        tool_context: ADK context (Hidden from Gemini).
        filename: The name of the artifact to edit (e.g., 'upload_123').
        prompt: A detailed description of the desired background (e.g., "A sunny beach with a blurred ocean view").
    """
    print(f"--- TOOL: Smart Background | File: {filename} | Prompt: '{prompt[:30]}...' ---")

    if not PICSART_API_KEY:
        return "Error: PICSART_API_KEY not found in environment variables."

    # 1. LOAD ARTIFACT
    try:
        print(f"DEBUG: Loading artifact '{filename}'...")
        artifact_obj = await tool_context.load_artifact(filename)
    except Exception as e:
        return f"Error: Failed to load artifact. {e}"

    if artifact_obj is None:
        return f"Error: Artifact '{filename}' not found."

    # 2. EXTRACT BYTES (Robust Logic)
    image_bytes = None
    if isinstance(artifact_obj, bytes):
        image_bytes = artifact_obj
    elif hasattr(artifact_obj, 'inline_data') and artifact_obj.inline_data:
        image_bytes = artifact_obj.inline_data.data
    elif isinstance(artifact_obj, dict):
        # Handle dict serialization cases
        if 'inline_data' in artifact_obj:
             image_bytes = artifact_obj['inline_data'].get('data')
        elif 'data' in artifact_obj:
             image_bytes = artifact_obj['data']

    if not image_bytes:
        return f"Error: Could not extract image bytes from artifact '{filename}'."

    # 3. CALL PICSART API
    print("   ... Sending request to Picsart API ...")
    
    try:
        # Prepare the multipart/form-data request
        files = {
            # (filename, file_object, content_type)
            "image": (filename, image_bytes, "image/jpeg") 
        }
        
        payload = {
            "prompt": prompt,
            "format": "JPG",
            "mode": "sync", # Wait for the result
            "count": "1"    # Just get one result for the demo
        }
        
        headers = {
            "accept": "application/json",
            "X-Picsart-API-Key": PICSART_API_KEY
        }

        # Make the POST request
        response = requests.post(PICSART_URL, data=payload, files=files, headers=headers)
        
        # Check for errors
        if response.status_code != 200:
            return f"Error from Picsart API ({response.status_code}): {response.text}"
            
        result_json = response.json()
        
        # Extract the result URL
        # The API returns: { "data": [ { "url": "..." } ] }
        if not result_json.get("data"):
            return f"Error: API returned success but no image data: {result_json}"
            
        result_url = result_json["data"][0]["url"]
        print(f"DEBUG: Generated Image URL: {result_url}")

        # 4. DOWNLOAD THE RESULT
        img_response = requests.get(result_url)
        if img_response.status_code != 200:
            return "Error: Could not download the generated image from Picsart."
            
        result_bytes = img_response.content

    except Exception as e:
        return f"Error during API execution: {e}"

    # 5. SAVE THE RESULT AS ARTIFACT
    new_filename = f"bg_gen_{filename}"
    print(f"DEBUG: Saving result as '{new_filename}'...")

    # Wrap in Part object for ADK compatibility
    new_part = types.Part.from_bytes(
        data=result_bytes,
        mime_type="image/jpeg"
    )

    await tool_context.save_artifact(filename=new_filename, artifact=new_part)

    return f"Success. Background generated using prompt '{prompt}'. Result saved as: {new_filename}"