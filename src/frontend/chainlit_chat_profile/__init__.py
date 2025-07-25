import chainlit as cl
import datetime
from azure.ai.agents.models import Agent
from azure.ai.projects.aio import AIProjectClient
from opentelemetry.trace import get_tracer
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.contents import ChatMessageContent

from pattern.debate import DebateOrchestrator
from pattern.foundry_debate import FoundryDebateOrchestrator


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

        tracer = get_tracer(__name__)
        with tracer.start_as_current_span(
            agent.id + "-" + datetime.datetime.now().isoformat()
        ):
            agent_response = await agent.get_response(
                messages=message.content, thread=thread
            )
        cl.user_session.set("thread", agent_response.thread)

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


class FoundryDebateProfile:
    def __init__(
        self,
        endpoint: str,
        api_version: str,
        deployment_name: str,
        agent_definitions: list[Agent],
        credential: DefaultAzureCredential,
    ):
        self.orchestrator = FoundryDebateOrchestrator(
            endpoint=endpoint,
            api_version=api_version,
            deployment_name=deployment_name,
            credential=credential,
            agent_definitions=agent_definitions,
        )
        self.credentials = credential

    @property
    def name(self) -> str:
        return "FoundryDebate"

    @property
    def description(self) -> str:
        return "A profile for debating topics with multiple perspectives."

    @property
    def markdown_description(self) -> str:
        return (
            "**Foundry Debate Profile**: Engage in structured debates on various topics, "
            "encouraging critical thinking and diverse viewpoints. Using Foundry Agent Service agents."
        )

    async def run(
        self, client: AIProjectClient, message: cl.Message, response: cl.Message
    ) -> None:
        async def call_back(message: ChatMessageContent) -> None:
            # await response.stream_token(f"**{message.name}**\n{message.content}")
            async with cl.Step(name=f"Agent {message.name}") as step:
                step.output = message.content
                                 
        # See https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-types/azure-ai-agent
        async with AzureAIAgent.create_client(
            credential=self.credentials
        ) as project_client:
            final_message = await self.orchestrator.process_conversation(
                project_client=project_client,
                user_id="default_user",  # TODO
                conversation_messages=[
                    {"role": "user", "name": "user", "content": message.content}
                ],
                agent_response_callback=call_back,
            )

            final_response = cl.Message(
                content=final_message.content,
                author=final_message.name,
            )
            await final_response.send()
