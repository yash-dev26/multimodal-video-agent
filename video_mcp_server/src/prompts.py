from langsmith import Client
from loguru import logger

client = Client()

logger = logger.bind(name="Prompts")

# Rocky needs to determine whether the user needs to perform an operation on a video.
ROUTING_SYSTEM_PROMPT = """
You are a routing assistant responsible for determining whether the user needs 
to perform an operation on a video.

Given a conversation history, between the user and the assistant, your task is
to determine if the user needs help with any of the following tasks:

- Extracting a clip from a specific moment in the video
- Retrieving information about a particular detail in the video

If the last message by the user is asking for either of these tasks, a tool should be used.

Your output should be a boolean value indicating whether tool usage is required.
"""

# Rocky needs to determine which tool to use based on the user query (if any).
TOOL_USE_SYSTEM_PROMPT = """
Your name is Rocky, a tool use assistant in charge
of a video processing application. 

You need to determine which tool to use based on the user query (if any).

The tools available are:

- 'get_video_clip_from_user_query': This tool is used to get a clip from the video based on the user query.
- 'get_video_clip_from_image': This tool is used to get a clip from the video based on an image provided by the user.
- 'ask_question_about_video': This tool is used to get some information about the video. The information needs to be retrieved from the 'video_context'

# Additional rules:
- If the user has provided an image, you should always use the 'get_video_clip_from_image' tool.

# Current information:
- Is image provided: {is_image_provided}
"""

GENERAL_SYSTEM_PROMPT = """
You are Rocky, a friendly assistant in charge of a multimodal video RAG application.

Your name is inspired by the intelligent and friendly alien from "Project Hail Mary", and you share his curiosity, helpfulness, and enthusiasm for solving problems.

You know a lot about films in general and about video processing techniques, and you will provide quotes and references to popular movies and directors to make the conversation more engaging and interesting.
"""


def routing_system_prompt() -> str:
    _prompt_id = "routing-system-prompt"
    try:
        prompt = client.get_prompt(_prompt_id)
        if prompt is None:
            prompt = client.create_prompt(
                name=_prompt_id,
                prompt=ROUTING_SYSTEM_PROMPT,
            )
            logger.info(f"System prompt created. \n {prompt.commit=} \n {prompt.prompt=}")
        return prompt.prompt
    except Exception:
        logger.warning("Couldn't retrieve prompt from Langsmith, check credentials! Using hardcoded prompt.")
        logger.warning(f"Using hardcoded prompt: {ROUTING_SYSTEM_PROMPT}")
        prompt = ROUTING_SYSTEM_PROMPT
    return prompt


def tool_use_system_prompt() -> str:
    _prompt_id = "tool-use-system-prompt"
    try:
        prompt = client.get_prompt(_prompt_id)
        if prompt is None:
            prompt = client.create_prompt(
                name=_prompt_id,
                prompt=TOOL_USE_SYSTEM_PROMPT,
            )
            logger.info(f"System prompt created. \n {prompt.commit=} \n {prompt.prompt=}")
        return prompt.prompt
    except Exception:
        logger.warning("Couldn't retrieve prompt from Langsmith, check credentials! Using hardcoded prompt.")
        logger.warning(f"Using hardcoded prompt: {TOOL_USE_SYSTEM_PROMPT}")
        prompt = TOOL_USE_SYSTEM_PROMPT
    return prompt


def general_system_prompt() -> str:
    _prompt_id = "general-system-prompt"
    try:
        prompt = client.get_prompt(_prompt_id)
        if prompt is None:
            prompt = client.create_prompt(
                name=_prompt_id,
                prompt=GENERAL_SYSTEM_PROMPT,
            )
            logger.info(f"System prompt created. \n {prompt.commit=} \n {prompt.prompt=}")
        return prompt.prompt
    except Exception:
        logger.warning("Couldn't retrieve prompt from Langsmith, check credentials! Using hardcoded prompt.")
        logger.warning(f"Using hardcoded prompt: {GENERAL_SYSTEM_PROMPT}")
        prompt = GENERAL_SYSTEM_PROMPT
    return prompt