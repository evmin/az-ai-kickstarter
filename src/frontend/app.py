"""
Chainlit frontend application for our multiagentic application.
"""

import logging

import chainlit as cl
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentThread,
)
from utils import load_dotenv_from_azd, setup_telemetry

from profile import AIFoundryAgentProfile
from profile.debate import DebateProfile

load_dotenv_from_azd()
tracer = setup_telemetry(__name__)
logger = logging.getLogger(__name__)

credential = DefaultAzureCredential()

# profiles = []

# for profile in Path(__file__).parent.joinpath("profile").glob("*.py"):
#     profile_name = profile.stem
#     if profile_name == "__init__":
#         continue
#     logger.info(f"Loading chat profile: '{profile_name}'")
#     profile_module = __import__(f"profile.{profile_name}", fromlist=[""])
#     class_name = f"{profile_name.capitalize()}Profile"
#     profile_class = getattr(profile_module, class_name, None)
#     if not profile_class:
#         raise ValueError(
#             f"Profile class {class_name} not found in {profile_name}.py"
#         )
#     profiles.append(profile_class())


profiles = [
    DebateProfile(),
]

@cl.set_chat_profiles
async def chat_profile():
    logger.info("Loading chat profiles...")
    async with AzureAIAgent.create_client(credential=credential) as client:
        # List all agents and log their names
        agents = [
            AIFoundryAgentProfile(agent) async for agent in client.agents.list_agents()
        ]
        logger.info(f"Found {len(agents)} agents")
        return [
            cl.ChatProfile(
                name=agent.name,
                markdown_description=agent.markdown_description
                if agent.description
                else "No description available.",
            )
            for agent in agents + profiles
        ]


@cl.on_chat_start
async def on_chat_start():
    logger.info("Starting chat session...")
    message = cl.Message(content="Loading agent... Please wait.")
    await message.send()

    client: AIProjectClient = AzureAIAgent.create_client(credential=credential)
    cl.user_session.set("client", client)

    # List all Foundry agents
    agents = [AIFoundryAgentProfile(agent) async for agent in client.agents.list_agents()]
    cl.user_session.set("profiles", agents + profiles)

    profile_name = cl.user_session.get("chat_profile")
    message.content = f"Starting chat using agent **«{profile_name}»**."
    await message.send()
    cl.user_session.set(
        "profile",
        next(
            (
                profile
                for profile in (agents + profiles)
                if profile.name == profile_name
            ),
            None,
        ),
    )


@cl.on_message
async def on_message(message: cl.Message):
    logger.debug(f"Received message: {message.content}...")

    client: AIProjectClient = cl.user_session.get("client")
    profile = cl.user_session.get("profile")

    if not client or not profile:
        await cl.Message(
            content="No profile selected or client not initialized. Please start a chat session.",
        ).send()
        return
    with tracer.start_as_current_span("chatbot"):
        await profile.run(client=client, message=message)


@cl.on_chat_end
async def on_chat_end():
    logger.info("Ending chat session...")
    client: AIProjectClient = cl.user_session.get("client")
    if client:
        await client.close()
