from fastmcp import settings

from multimodal_agent.src.multimodal_agent.models import RoutingResponseModel


def _should_use_tool(self, message: str) -> bool:
        messages = [
            {"role": "system", "content": self.routing_system_prompt},
            {"role": "user", "content": message},
        ]
        response = self.instructor_client.chat.completions.create(
            model=settings.GROQ_ROUTING_MODEL,
            response_model=RoutingResponseModel,
            messages=messages,
            max_completion_tokens=20,
        )
        return response.tool_use