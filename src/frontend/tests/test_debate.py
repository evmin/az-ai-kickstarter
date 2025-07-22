import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from semantic_kernel.contents.chat_message_content import ChatMessageContent

from profile.debate import DebateOrchestrator
from utils import load_dotenv_from_azd, get_model_deployment
import os
from azure.identity.aio import DefaultAzureCredential


# Initialize environment and logging
load_dotenv_from_azd()

console = Console()

@pytest.fixture()
def orchestrator(mocker):
    mocker.patch(
        "semantic_kernel.core_plugins.time_plugin.TimePlugin.date",
        return_value="Sunday, 12 January, 2031",
    )
    return DebateOrchestrator(
        endpoint=os.getenv("AI_FOUNDRY_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        executor_deployment_name=get_model_deployment("gpt-4.1").name,
        utility_deployment_name=get_model_deployment("gpt-4o-mini").name,
        credential=DefaultAzureCredential(),
    )


async def test_blog_generation(orchestrator):
    conversation_messages = [
        {
            "role": "user",
            "content": "A blog about cookies",
        }
    ]

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

    final_response = await collect_chunks()

    assert final_response is not None
    assert "01/12/2031" in final_response

    console.rule()
    console.print(Panel(Markdown(final_response), title="Final Response"))
