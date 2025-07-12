import chainlit as cl
import datetime
from azure.ai.projects.aio import AIProjectClient
from opentelemetry.trace import get_tracer
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)
from azure.identity.aio import DefaultAzureCredential

from .debate import DebateOrchestrator


class AIFoundryAgentProfile:
    def __init__(self, agent: dict):
        self.agent = agent

    @property
    def name(self) -> str:
        return self.agent["name"]

    @property
    def description(self) -> str:
        return self.agent["description"]

    @property
    def markdown_description(self) -> str:
        return f"**Foundry Agent**: {self.description or 'No description available.'}"

    async def run(
        self, client: AIProjectClient, message: cl.Message, response: cl.Message
    ) -> None:
        agent = AzureAIAgent(client=client, definition=self.agent)
        thread: AzureAIAgentThread = cl.user_session.get("thread", None)
        if not thread:
            thread = await client.agents.threads.create_thread(agent_id=agent.id)
            cl.user_session.set("thread", thread)
        
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span(agent.id):
            agent_response = await agent.get_response(
                messages=message.content, thread=thread
            )

        response.content = agent_response.content.content
        await response.update()


class DebateProfile:
    def __init__(
        self,
        endpoint: str,
        api_version: str,
        executor_deployment_name: str,
        utility_deployment_name: str,
        credential: DefaultAzureCredential,
    ):
        self.orchestrator = DebateOrchestrator(
            endpoint=endpoint,
            api_version=api_version,
            executor_deployment_name=executor_deployment_name,
            utility_deployment_name=utility_deployment_name,
            credential=credential,
        )

    @property
    def name(self) -> str:
        return "Debate"

    @property
    def description(self) -> str:
        return "A profile for debating topics with multiple perspectives."

    @property
    def markdown_description(self) -> str:
        return (
            "**Debate Profile**: Engage in structured debates on various topics, "
            "encouraging critical thinking and diverse viewpoints."
        )

    async def run(
        self, client: AIProjectClient, message: cl.Message, response: cl.Message
    ) -> None:
        final_step = None
        async for step in self.orchestrator.process_conversation(
            "default_user",  # TODO
            [{"role": "user", "name": "user", "content": message.content}],
        ):
            if step["type"] == "status_update":
                await response.stream_token(f"\n* {step['description']}\n")
            final_step = step

        response.content = final_step["content"]
        await response.update()
