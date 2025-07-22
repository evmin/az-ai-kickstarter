import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from semantic_kernel.contents.chat_message_content import ChatMessageContent

from profile.foundry_debate import FoundryDebateOrchestrator
from utils import load_dotenv_from_azd, get_model_deployment
import os
from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.agents import (
    AzureAIAgent,
)

# Initialize environment and logging
load_dotenv_from_azd()

console = Console()


@pytest.fixture()
async def orchestrator(mocker):
    mocker.patch(
        "semantic_kernel.core_plugins.time_plugin.TimePlugin.date",
        return_value="Sunday, 12 January, 2031",
    )
    project_client = AzureAIAgent.create_client(credential=DefaultAzureCredential())
    agent_definitions = [
        definition
        async for definition in project_client.agents.list_agents()
        if definition.name in ["Writer", "Critic"]
    ]
    return FoundryDebateOrchestrator(
        endpoint=os.getenv("AI_FOUNDRY_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        deployment_name=get_model_deployment("gpt-4.1").name,
        credential=DefaultAzureCredential(),
        agent_definitions=agent_definitions,
    )


async def test_blog_generation(orchestrator):
    conversation_messages = [
        {
            "role": "user",
            "content": "A blog about cookies",
        }
    ]

    async def agent_response_callback(message: ChatMessageContent) -> None:
        """Callback function to retrieve agent responses."""
        print(f"**{message.name}**\n{message.content}")

    async with AzureAIAgent.create_client(
        credential=DefaultAzureCredential()
    ) as project_client:
        final_message = await orchestrator.process_conversation(
            project_client,
            "test_user",
            conversation_messages,
            agent_response_callback=agent_response_callback,
        )

    assert final_message is not None
    assert "01/12/2031" in final_message.content

    console.rule()
    console.print(Panel(Markdown(final_message.content), title="Final Response"))
