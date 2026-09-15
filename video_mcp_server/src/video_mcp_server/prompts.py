import os

from langsmith import Client
from langchain_core.prompts import PromptTemplate
from loguru import logger
from dotenv import load_dotenv

load_dotenv()
client = Client(
    api_key=os.environ["LANGSMITH_API_KEY"],
)

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
You are Rocky, the tool-use agent for a multimodal video application.

The router has already determined this request needs a video tool. Your
only job on this turn is to pick the right one and call it — or, if a
tool result already in this conversation answers the request, to stop.

Rules:
- Call exactly one tool per turn. Do not greet the user or add commentary.
- If the most recent messages already contain a tool result that answers
  the user's request, do not call another tool — stop.
- Never ask the user for the video path or filename. The active video is
  tracked by the application and is attached to your tool call
  automatically — you do not need to know or produce it yourself.

Available tools:

- get_video_clip_from_user_query
  The user wants to find or extract a specific moment, scene, quote, or
  event from the video, described in words.

- get_video_clip_from_image
  The user has provided an image and wants the matching moment in the
  video. Always use this tool when an image is provided.

- ask_question_about_video
  The user is asking about something said, shown, or happening in the
  video, and wants an answer rather than a clip.

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
        prompt = client.pull_prompt(_prompt_id)
        return getattr(prompt, "template", str(prompt))
    except Exception as exc:
        logger.warning(
            "Couldn't retrieve prompt from LangSmith: {}. Using hardcoded prompt.",
            exc,
        )
        try:
            client.push_prompt(
                _prompt_id,
                object=PromptTemplate.from_template(ROUTING_SYSTEM_PROMPT),
            )
        except Exception as exc:
            logger.warning(
                "Couldn't push hardcoded prompt to LangSmith: {}",
                exc,
            )
        return ROUTING_SYSTEM_PROMPT


def tool_use_system_prompt() -> str:
    _prompt_id = "tool-use-system-prompt"
    try:
        prompt = client.pull_prompt(_prompt_id)
        return getattr(prompt, "template", str(prompt))
    except Exception as exc:
        logger.warning(
            "Couldn't retrieve prompt from LangSmith: {}. Using hardcoded prompt.",
            exc
        )
        try:
            client.push_prompt(
                _prompt_id,
                object=PromptTemplate.from_template(TOOL_USE_SYSTEM_PROMPT),
            )
        except Exception as exc:
            logger.warning(
                "Couldn't push hardcoded prompt to LangSmith: {}",
                exc,
            )
        return TOOL_USE_SYSTEM_PROMPT


def general_system_prompt() -> str:
    _prompt_id = "general-system-prompt"
    try:
        prompt = client.pull_prompt(_prompt_id)
        return getattr(prompt, "template", str(prompt))
    except Exception as exc:
        logger.warning(
            "Couldn't retrieve prompt from LangSmith: {}. Using hardcoded prompt.",
            exc,
        )
        try:
            client.push_prompt(
                _prompt_id,
                object=PromptTemplate.from_template(GENERAL_SYSTEM_PROMPT),
            )
        except Exception as exc:
            logger.warning(
                "Couldn't push hardcoded prompt to LangSmith: {}",
                exc,
            )
        return GENERAL_SYSTEM_PROMPT
