from fastmcp import settings

from multimodal_agent.src.multimodal_agent.models import GeneralResponseModel


def _respond_general(self, message: str) -> str:
        chat_history = self._build_chat_history(self.general_system_prompt, message)
        return self.instructor_client.chat.completions.create(
            model=settings.GROQ_GENERAL_MODEL,
            messages=chat_history,
            response_model=GeneralResponseModel,
        )