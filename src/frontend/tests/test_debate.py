import asyncio
import json

import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from semantic_kernel.contents.chat_message_content import ChatMessageContent

from profile.debate import DebateOrchestrator
from utils import load_dotenv_from_azd


# Initialize environment and logging
load_dotenv_from_azd()

@pytest.fixture()
def orchestrator(mocker):
    mocker.patch('semantic_kernel.core_plugins.time_plugin.TimePlugin.date', return_value="Sunday, 12 January, 2031")
    return DebateOrchestrator()

def test_blog_generation(orchestrator):
    conversation_messages = [
        {
            "role": "user",
            "content": "A blog about cookies",

        }
    ]
    console = Console()

    async def collect_chunks() -> ChatMessageContent:
        last_step = None
        async for step in orchestrator.process_conversation(
            "test_user", conversation_messages
        ):
            last_step = step
            console.rule()
            if step["type"] == "status_update":
                console.print(f"Status Update: {step['description']}")
            elif step["type"] == "final_response":
                console.print(f"Final Response: {step['content']}")
            else:
                raise ValueError(f"Unknown step type for {step}")
        return last_step["content"]

    final_response = asyncio.run(collect_chunks())

    assert final_response is not None


    console.rule()
    console.print(Panel(Markdown(final_response), title="Final Response"))