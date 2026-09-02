from griffe import logger
from traitlets import Any
import json
from multimodal_agent.models import GeneralResponseModel, VideoClipResponseModel
from multimodal_agent.config import get_settings

settings = get_settings()


async def _execute_tool_call(self, tool_call: Any, video_path: str, image_base64: str | None = None) -> str:
        """Execute a single tool call and return its response."""
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        function_args["video_path"] = video_path

        if function_name == "get_video_clip_from_image":
            function_args["user_image"] = image_base64

        logger.info(f"Executing tool: {function_name}")

        try:
            return await self.call_tool(function_name, function_args)
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {str(e)}")
            return f"Error executing tool {function_name}: {str(e)}"

    
async def _run_with_tool(self, message: str, video_path: str, image_base64: str | None = None) -> str:
        """Execute chat completion with tool usage."""
        tool_use_system_prompt = self.tool_use_system_prompt.format(
            is_image_provided=bool(image_base64),
        )
        chat_history = self._build_chat_history(tool_use_system_prompt, message)

        response = (
            self.client.chat.completions.create(
                model=settings.GROQ_TOOL_USE_MODEL,
                messages=chat_history,
                tools=self.tools,
                tool_choice="auto",
                max_completion_tokens=4096,
            )
            .choices[0]
            .message
        )
        tool_calls = response.tool_calls
        logger.info(f"Tool calls: {tool_calls}")

        if not tool_calls:
            logger.info("No tool calls available, returning general response ...")
            return GeneralResponseModel(message=response.content)

        for tool_call in tool_calls:
            function_response = await self._execute_tool_call(tool_call, video_path, image_base64)
            logger.info(f"Function response: {function_response}")
            
            if tool_call.function.name == "get_video_clip_from_image":
                tool_response = f"This is the video context. Use it to answer the user's question: {function_response}"
            else:
                tool_response = function_response
            
            chat_history.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": tool_response,
                }
            )

        response_model = (
            GeneralResponseModel if tool_call.function.name == "ask_question_about_video" else VideoClipResponseModel
        )
        
        logger.info(f"Chat history: {chat_history}")
        
        followup_response = self.instructor_client.chat.completions.create(
            model=settings.GROQ_TOOL_USE_MODEL,
            messages=chat_history,
            response_model=response_model,
        )

        if isinstance(followup_response, VideoClipResponseModel):
            try:
                logger.info("Validating VideoClip response")
                self.validate_video_clip_response(followup_response, tool_response)
                
                logger.info(f"Tracing image from trimmed clip: {followup_response.clip_path}")
                first_image_path = tools.sample_first_frame(followup_response.clip_path)
                opik_context.update_current_trace(
                    attachments=[
                        Attachment(
                            data=first_image_path,
                            content_type="image/png",
                        )
                    ]
                )
            except ValueError as e:
                logger.error(f"Failed to sample first frame from video: {e}")

        return followup_response