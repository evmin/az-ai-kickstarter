import chainlit as cl
from azure.ai.projects.aio import AIProjectClient
from opentelemetry.trace import get_tracer
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)

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

    async def run(self, client: AIProjectClient, message: cl.Message) -> AzureAIAgent:
        agent = AzureAIAgent(client=client, definition=self.agent)
        thread: AzureAIAgentThread = cl.user_session.get("thread", None)
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span(thread.id):
            response = await agent.get_response(messages=message.content, thread=thread)
        thread = response.thread
        cl.user_session.set("thread", thread)
        await cl.Message(content=response.content.content).send()

class DebateProfile:
    def __init__(self):
        self.orchestrator = DebateOrchestrator()

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
    

    async def run(self, client: AIProjectClient, message: cl.Message) -> None:
        final_step = None
        async for step in self.orchestrator.process_conversation(
            "default_user", # TODO
            [{'role': 'user', 'name': 'user', 'content': message.content}],
        ):
            if step["type"] == "status_update":
                await message.stream_token(f"\n* {step['description']}\n")
            final_step = step

        message.content = final_step["content"]
        await message.update()