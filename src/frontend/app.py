"""
Chainlit frontend application for our multiagentic application.
"""

import logging
import os

import chainlit as cl
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import (
    AzureAIAgent,
)
from utils import load_dotenv_from_azd, setup_telemetry, get_model_deployment

from chainlit_chat_profile import AIFoundryAgentProfile, DebateProfile, FoundryDebateProfile

load_dotenv_from_azd()
credential = DefaultAzureCredential(exclude_managed_identity_credential=True)
tracer = setup_telemetry(__name__)
logger = logging.getLogger(__name__)


profiles = []


@cl.set_chat_profiles
async def chat_profile():
    logger.info("Loading chat profiles...")
    async with AzureAIAgent.create_client(credential=credential) as client:
        azure_ai_agents = [agent async for agent in client.agents.list_agents()]
        global profiles
        profiles = [AIFoundryAgentProfile(agent) for agent in azure_ai_agents]
        profiles.append(
            DebateProfile(
                endpoint=os.getenv("AI_FOUNDRY_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                executor_deployment_name=get_model_deployment("gpt-4.1").name,
                utility_deployment_name=get_model_deployment("gpt-4o-mini").name,
                credential=credential,
            ),
        )
        profiles.append(
            FoundryDebateProfile(
                endpoint=os.getenv("AI_FOUNDRY_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                deployment_name=get_model_deployment("gpt-4.1").name,
                credential=credential,
                agent_definitions=[
                    definition
                    async for definition in client.agents.list_agents()
                    if definition.name in ["Writer", "Critic"]
                ],
            ),
        )
        logger.info(f"Found {len(profiles)} profiles")
        return [
            cl.ChatProfile(
                name=profile.name,
                markdown_description=profile.markdown_description
                if profile.description
                else "No description available.",
                default=profile.name == "FoundryDebate",
            )
            for profile in profiles
        ]


@cl.on_chat_start
async def on_chat_start():
    logger.info("Starting chat session...")
    message = cl.Message(content="Loading agent... Please wait.")
    await message.send()

    client: AIProjectClient = AzureAIAgent.create_client(credential=credential)
    cl.user_session.set("client", client)

    # List all Foundry agents
    cl.user_session.set("profiles", profiles)

    profile_name = cl.user_session.get("chat_profile")
    message.content = f"Starting chat using profile **«{profile_name}»**."
    await message.send()
    cl.user_session.set(
        "profile",
        next(
            (profile for profile in profiles if profile.name == profile_name),
            None,
        ),
    )


@cl.on_message
async def on_message(message: cl.Message):
    logger.info(f"Received message: {message.content}...")

    client: AIProjectClient = cl.user_session.get("client")
    profile = cl.user_session.get("profile")

    if not client or not profile:
        await cl.Message(
            content="No profile selected or client not initialized. Please start a chat session.",
        ).send()
        return
    logger.info(f"Running profile: {profile.name}")
    response_message = cl.Message(
        content=f"Running profile **«{profile.name}»** with message: «{message.content}»."
    )
    await response_message.send()
    await profile.run(client=client, message=message, response=response_message)


@cl.on_chat_end
async def on_chat_end():
    logger.info("Ending chat session...")
    client: AIProjectClient = cl.user_session.get("client")
    if client:
        await client.close()
