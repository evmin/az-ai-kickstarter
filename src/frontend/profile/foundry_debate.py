import datetime
import logging
import sys

from azure.ai.agents.models import Agent as AzureAIAgentModel
from azure.ai.inference.aio import ChatCompletionsClient
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from opentelemetry.trace import get_tracer
from semantic_kernel.agents import GroupChatOrchestration
from semantic_kernel.agents.azure_ai.azure_ai_agent import AzureAIAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents.orchestration.group_chat import (
    BooleanResult,
    GroupChatManager,
    MessageResult,
    StringResult,
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.chat_completion_client_base import (
    ChatCompletionClientBase,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.core_plugins.time_plugin import TimePlugin
from semantic_kernel.functions import (
    KernelArguments,
)
from semantic_kernel.kernel import Kernel
from semantic_kernel.prompt_template import KernelPromptTemplate, PromptTemplateConfig

logger = logging.getLogger(__name__)


class ChatCompletionGroupChatManager(GroupChatManager):
    agent_names: list[str]
    topic: str
    service: ChatCompletionClientBase

    termination_prompt: str = "Check the **last** provided evaluation and terminate if the evaluated score is higher or equal to 8. "

    selection_prompt: str = (
        "You are the next speaker selector. \n"
        "  - You MUST return ONLY agent name from the list of available agents below\n"
        "  - You MUST return the agent name and nothing else.\n"
        "  - The agent names are case-sensitive and should not be abbreviated or changed. \n"
        "  - Check the history, and decide WHAT agent is the best next speaker\n"
        "  - You MUST call Critic agent to evaluate Writer RESPONSE\n"
        "  - YOU MUST OBSERVE AGENT USAGE INSTRUCTIONS.\n\n"
    )

    def __init__(
        self,
        topic: str,
        service: ChatCompletionClientBase,
        agent_names: list[str],
        **kwargs,
    ) -> None:
        """Initialize the group chat manager."""
        super().__init__(
            topic=topic, service=service, agent_names=agent_names, **kwargs
        )

    async def filter_results(self, chat_history: ChatHistory) -> MessageResult:
        # Custom logic to filter or summarize chat results
        return MessageResult(
            result=chat_history.messages[-1],
            reason="Previous to last message in chat history (Writer's last response).",
        )

    async def _render_prompt(self, prompt: str, arguments: KernelArguments) -> str:
        """Helper to render a prompt with arguments."""
        prompt_template_config = PromptTemplateConfig(template=prompt)
        prompt_template = KernelPromptTemplate(
            prompt_template_config=prompt_template_config
        )
        return await prompt_template.render(Kernel(), arguments=arguments)


    async def should_request_user_input(
        self, chat_history: ChatHistory
    ) -> BooleanResult:
        # Custom logic to decide if user input is needed
        return BooleanResult(result=False, reason="No user input required.")

    async def should_terminate(self, chat_history: ChatHistory) -> BooleanResult:
        """Provide concrete implementation for determining if the discussion should end.

        The manager will check if the conversation should be terminated after each agent message
        or human input (if applicable).
        """
        should_terminate = await super().should_terminate(chat_history)
        if should_terminate.result:
            return should_terminate

        if chat_history.messages[-1].name not in self.agent_names:
            return BooleanResult(
                result=False,
                reason=f"We check termination only after {self.agent_names}",
            )

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    self.termination_prompt,
                    KernelArguments(topic=self.topic),
                ),
            ),
        )
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER, content="Determine if the discussion should end."
            ),
        )

        response = await self.service.get_chat_message_content(
            chat_history,
            settings=PromptExecutionSettings(response_format=BooleanResult),
        )

        termination_with_reason = BooleanResult.model_validate_json(response.content)

        print("********************* should_terminate *********************")
        print(
            f"Should terminate: {termination_with_reason.result}\nReason: {termination_with_reason.reason}."
        )
        print("*********************")

        return termination_with_reason

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """Provide concrete implementation for selecting the next agent to speak.

        The manager will select the next agent to speak after each agent message
        or human input (if applicable) if the conversation is not terminated.
        """
        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    self.selection_prompt,
                    KernelArguments(
                        topic=self.topic,
                        participants="\n".join(
                            [f"{k}: {v}" for k, v in participant_descriptions.items()]
                        ),
                    ),
                ),
            ),
        )
        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Now select the next participant to speak.",
            ),
        )

        response = await self.service.get_chat_message_content(
            chat_history,
            settings=PromptExecutionSettings(response_format=StringResult),
        )

        participant_name_with_reason = StringResult.model_validate_json(
            response.content
        )

        print("********************* select_next_agent *********************")
        print(
            f"Next participant: {participant_name_with_reason.result}\nReason: {participant_name_with_reason.reason}."
        )
        print("*********************")

        if participant_name_with_reason.result in participant_descriptions:
            return participant_name_with_reason

        raise RuntimeError(f"Unknown participant selected: {response.content}.")


def agent_response_callback(message: ChatMessageContent) -> None:
    """Callback function to retrieve agent responses."""
    print(f"**{message.name}**\n{message.content}")

# This pattern demonstrates how a debate between equally skilled models
# can deliver an outcome that exceeds the capability of the model if
# the task is handled as a single request-response in its entirety.
# We focus each agent on the subset of the whole task and thus
# get better results.
class FoundryDebateOrchestrator:
    """
    Orchestrates a debate between AI agents to produce higher quality responses.

    This class sets up and manages a conversation between Writer and Critic agents using
    Semantic Kernel's Agent Group Chat functionality. The debate pattern improves response
    quality by allowing specialized agents to focus on different aspects of the task.
    """

    def __init__(
        self,
        deployment_name: str,
        api_version: str,
        endpoint: str,
        agent_definitions: list[AzureAIAgentModel],
        credential: DefaultAzureCredential,
    ):
        """
        Creates the DebateOrchestrator with necessary services and kernel configurations.

        Sets up Azure OpenAI connections for both executor and utility models,
        configures Semantic Kernel, and prepares execution settings for the agents.
        """

        logger.info("Semantic Kernel Foundry debate orchestrator initialization...")

        self.endpoint = endpoint
        self.agent_definitions = agent_definitions
        self.credential = credential
        self.deployment_name = deployment_name
        self.api_version = api_version

    # --------------------------------------------
    # Run the agent conversation
    # --------------------------------------------
    async def process_conversation(
        self,
        project_client: AIProjectClient,
        user_id,
        conversation_messages: list[dict[str, str]],
    ):
        
        agents = []
        for agent in self.agent_definitions:
            agents.append(AzureAIAgent(client=project_client, definition=agent, plugins=[TimePlugin()]))

        orchestration = GroupChatOrchestration(
            members=agents,
            manager=ChatCompletionGroupChatManager(
                topic=conversation_messages[0]["content"],
                agent_names=["Writer"],
                service=AzureChatCompletion(deployment_name="gpt-4.1-2025-04-14",
                                            base_url=f"{self.endpoint}/openai/deployments/gpt-4.1-2025-04-14",),
            ),
            agent_response_callback=agent_response_callback,
        )

        # 2. Create a runtime and start it
        runtime = InProcessRuntime()
        runtime.start()

        # 3. Invoke the orchestration with a task and the runtime
        orchestration_result = await orchestration.invoke(
            task="Please start the discussion.",
            runtime=runtime,
        )

        tracer = get_tracer(__name__)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        session_id = f"{user_id}-{current_time}"
        with tracer.start_as_current_span(session_id):  # TODO: proper session name
            value = await orchestration_result.get()
            print(value)

        # 5. Stop the runtime after the invocation is complete
        await runtime.stop_when_idle()

        yield {
            "type": "final_response",
            "content": value.content,
        }

        # with tracer.start_as_current_span(session_id):
        #     async for message in agent_group_chat.invoke():
        #         logger.debug("Agent message: %s", message.to_dict())
        #         description = await describe_action(
        #             self.kernel, self.settings_utility, message.name, message.to_dict()
        #         )
        #         logger.debug("Action description: %s", description)
        #         yield {"type": "status_update", "description": str(description)}

        # chat_messages = agent_group_chat.get_chat_messages()
        # await anext(chat_messages)  # ignore last message from CRITIC
