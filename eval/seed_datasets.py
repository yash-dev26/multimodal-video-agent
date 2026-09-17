"""
Creates the five LangSmith datasets and seeds each with a handful of examples.
"""
from __future__ import annotations

from langsmith import Client
from dotenv import load_dotenv

load_dotenv()

from schemas import e2e_example, qa_example, retrieval_example, router_example, tool_selection_example

VIDEO_PATH = "shared_media/example_video.mp4"

client = Client()


def _create_or_get(name: str, description: str):
    existing = list(client.list_datasets(dataset_name=name))
    if existing:
        return existing[0]
    return client.create_dataset(dataset_name=name, description=description)


def seed_router_dataset():
    ds = _create_or_get("router-eval", "Binary needs_tool gate (router.py)")
    examples = [
        router_example("Can you get me a clip of the scene where he says the code word?", True),
        router_example("What does she say right after the door opens?", True),
        router_example("What's your favorite movie about space travel?", False),
        router_example("Thanks, that clip was perfect!", False),
        # Edge case: implicit tool need without an explicit clip/question verb.
        router_example("There's a part where the lighting changes dramatically, remind me what happens there", True),
        # Edge case: video-adjacent but no retrieval needed.
        router_example("How does video captioning even work under the hood?", False),
    ]
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"Seeded {len(examples)} examples into {ds.name}")


def seed_tool_selection_dataset():
    ds = _create_or_get("tool-selection-eval", "3-way tool choice (tool_agent.py)")
    examples = [
        tool_selection_example("Grab me the clip where he opens the door", "get_video_clip_from_user_query"),
        tool_selection_example(
            "Find the moment that looks like this", "get_video_clip_from_image", image_provided=True
        ),
        tool_selection_example("What does he say about the mission timeline?", "ask_question_about_video"),
        # The genuinely ambiguous pair called out in the eval plan:
        tool_selection_example("Show me where he says the code word", "get_video_clip_from_user_query"),
        tool_selection_example("What does he say about the code word?", "ask_question_about_video"),
        # Image provided should always win per TOOL_USE_SYSTEM_PROMPT's rule --
        # even if the text also reads like a query-based clip request.
        tool_selection_example(
            "Get me the clip that matches this scene", "get_video_clip_from_image", image_provided=True
        ),
        # No video active -- current code relies on tool_agent's own guard,
        # not tool selection, but worth tracking whether the LLM still tries.
        tool_selection_example(
            "What happens in the video?", "ask_question_about_video", video_active=False
        ),
    ]
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"Seeded {len(examples)} examples into {ds.name}")


def seed_retrieval_dataset():

    ds = _create_or_get("retrieval-eval", "Per-modality moment retrieval (video_search_service.py)")
    examples = [

        retrieval_example(
            VIDEO_PATH,
            "Joker tells Murray that he is awful",
            "speech",
            gt_windows=[(168.0, 176.0)],
        ),

        retrieval_example(
            VIDEO_PATH,
            "Murray talks about the riots and the two policemen being in critical condition",
            "speech",
            gt_windows=[(188.0, 200.0)],
        ),

        retrieval_example(
            VIDEO_PATH,
            "Joker says how about another joke Murray",
            "speech",
            gt_windows=[(204.5, 211.0)],
        ),

        retrieval_example(
            VIDEO_PATH,
            "Joker pulls out a gun and shoots Murray on the live television set",
            "caption",
            gt_windows=[(218.5, 225.0)],
        ),

    ]
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"Seeded {len(examples)} examples into {ds.name}")


def seed_qa_dataset():

    ds = _create_or_get("qa-eval", "ask_question_about_video answer quality")
    examples = [

        qa_example(
            VIDEO_PATH,
            "Why does Murray say that Arthur is awful?",
            reference_answer="Murray says Arthur is awful because he believes Arthur is making excuses for killing the three young men and because Arthur's actions have led to violence and unrest in the city.",
            supporting_snippets=[
                "You sound like you're making excuses for killing those young men",
                "There are riots out there",
                "Two policemen are in critical condition",
                "Someone was killed today, because of what you did",
            ],
        ),

    ]
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"Seeded {len(examples)} examples into {ds.name}")


def seed_e2e_dataset():

    ds = _create_or_get("e2e-eval", "Full graph, judged end-to-end")
    examples = [

        e2e_example(
            "What is happening in this scene?",
            expected_kind="general",
        ),

        e2e_example(
            "Grab me the clip where Joker asks Murray for another joke",
            expected_kind="video_clip",
            video_path=VIDEO_PATH,
            gt_windows=[(204.5, 211.0)],
        ),

        e2e_example(
            "What does Murray say about the consequences of Arthur's actions?",
            expected_kind="qa",
            video_path=VIDEO_PATH,
            reference_answer="Murray says that Arthur's actions have caused riots, left two policemen in critical condition, and resulted in someone being killed.",
        ),

    ]
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"Seeded {len(examples)} examples into {ds.name}")
if __name__ == "__main__":
    seed_router_dataset()
    seed_tool_selection_dataset()
    seed_retrieval_dataset()
    seed_qa_dataset()
    seed_e2e_dataset()
