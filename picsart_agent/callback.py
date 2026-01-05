import logging
import google.cloud.logging
import hashlib
from google.genai import types

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest


def log_query_to_model(callback_context: CallbackContext, llm_request: LlmRequest):
    if llm_request.contents and llm_request.contents[-1].role == "user":
        if llm_request.contents[-1].parts[-1].text:
            last_user_message = llm_request.contents[-1].parts[-1].text
            logging.info(
                f"[query to {callback_context.agent_name}]: " + last_user_message
            )


def log_model_response(callback_context: CallbackContext, llm_response: LlmResponse):
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text:
                logging.info(
                    f"[response from {callback_context.agent_name}]: " + part.text
                )
            elif part.function_call:
                logging.info(
                    f"[function call from {callback_context.agent_name}]: "
                    + part.function_call.name
                )

async def save_upload_as_artifact(llm_request: LlmRequest, callback_context: CallbackContext, **kwargs):
    """
    1. Checks Session State to see if we already saved this image.
    2. If NEW: Saves to Artifact Service & adds hash to Session State.
    3. ALWAYS: Removes heavy bytes from the request to prevent echoes.
    """
    if not llm_request.contents:
        return None

    # 1. Initialize our Session State list if it doesn't exist
    if "processed_images" not in callback_context.session.state:
        callback_context.session.state["processed_images"] = []
    
    # We copy it to a local var for easier reading
    processed_list = callback_context.session.state["processed_images"]
    
    for content in llm_request.contents:
        for part in content.parts:
            
            # Check for file data
            if part.inline_data:
                data = getattr(part.inline_data, 'data', None) or part.inline_data.get('data')
                mime_type = part.inline_data.mime_type

                if data:
                    # Generate ID
                    data_hash = hashlib.md5(data).hexdigest()
                    filename = f"upload_{data_hash}"
                    
                    # 2. CHECK SESSION STATE: Have we seen this hash?
                    if data_hash not in processed_list:
                        print(f"DEBUG: New image detected! Saving {filename}...")

                        stored_part = types.Part.from_bytes(
                            data=data,
                            mime_type=mime_type
                            )
                        
                        # Save the actual file
                        await callback_context.save_artifact(
                            filename=filename,
                            artifact=stored_part 
                        )
                        
                        # Update Session State so we don't save it again
                        processed_list.append(data_hash)
                        callback_context.session.state["processed_images"] = processed_list
                    else:
                        print(f"DEBUG: Skipping save for {filename} (Already in Session State)")

                    # 3. THE CLEANUP (Must happen every time)
                    # We replace the bytes with text so the model knows the file exists
                    # but doesn't get overwhelmed by the raw data.
                    part.text = f"\n[System: User uploaded file available as artifact: {filename}]\n"
                    part.inline_data = None 

    # Return None so the pipeline continues to the Model
    return None