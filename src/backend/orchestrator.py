import os
import logging
import yaml
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from semantic_kernel.kernel import Kernel
from semantic_kernel.agents import AgentGroupChat
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies import KernelFunctionSelectionStrategy
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.core_plugins.time_plugin import TimePlugin
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.functions import KernelPlugin, KernelFunctionFromPrompt, KernelArguments
from typing import ClassVar

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SemanticOrchestrator:
    def __init__(self):

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.debug("Semantic Orchestrator Handler init")

        self.logger.info(f"Creating - {os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")}")

        gpt4o_service = AzureChatCompletion(service_id="gpt-4o",
                                            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                                            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                                            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                                            ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(),"https://cognitiveservices.azure.com/.default"))

        self.kernel = Kernel(
            services=[gpt4o_service],
            plugins=[
                KernelPlugin.from_object(plugin_instance=TimePlugin(), plugin_name="time")
            ]
        )

    # --------------------------------------------
    # Create Agent Group Chat
    # --------------------------------------------
    def create_agent_group_chat(self):

        self.logger.debug("Creating chat")

        writer = self.create_agent(service_id="gpt-4o",
                                        kernel=self.kernel,
                                        definition_file_path="agents/writer.yaml")
        critic = self.create_agent(service_id="gpt-4o",
                                            kernel=self.kernel,
                                            definition_file_path="agents/critic.yaml")

        agents=[writer, critic]

        agent_group_chat = AgentGroupChat(
                agents=agents,
                
                selection_strategy=self.create_selection_strategy(agents, critic),
                termination_strategy = self.create_termination_strategy(
                                         agents=[critic],
                                         maximum_iterations=8))

        return agent_group_chat

    # --------------------------------------------
    # Speaker Selection Strategy
    # --------------------------------------------
    def create_selection_strategy(self, agents, default_agent):
        """Speaker selection strategy for the agent group chat."""
        definitions = "\n".join([f"{agent.name}: {agent.description}" for agent in agents])
        selection_function = KernelFunctionFromPrompt(
                function_name="selection",
                prompt_execution_settings=AzureChatPromptExecutionSettings(
                    temperature=0),
                prompt=fr"""
                    You are the next speaker selector.

                    - You MUST return ONLY agent name from the list of available agents below.
                    - You MUST return the agent name and nothing else.
                    - Check the history, and decide WHAT agent is the best next speaker
                    - Make sure to call CRITIC agent to evaluate WRITER RESPONSE
                    - The names are case-sensitive and should not be abbreviated or changed.
                    - YOU MUST OBSERVE AGENT USAGE INSTRUCTIONS.

# AVAILABLE AGENTS

{definitions}

# CHAT HISTORY

{{{{$history}}}}
""")

        # Could be lambda. Keeping as function for clarity
        def parse_selection_output(output):
            self.logger.debug(f"Parsing selection: {output}")
            if output.value is not None:
                return output.value[0].content
            return default_agent.name

        return KernelFunctionSelectionStrategy(
                    kernel=self.kernel,
                    function=selection_function,
                    result_parser=parse_selection_output,
                    agent_variable_name="agents",
                    history_variable_name="history")

    # --------------------------------------------
    # Termination Strategy
    # --------------------------------------------
    def create_termination_strategy(self, agents, maximum_iterations):
        """
        Create a chat termination strategy that terminates when the Critic is satisfied
        params:
            agents: List of agents to trigger termination evaluation (critic only)
            maximum_iterations: Maximum number of iterations before termination
        """

        class CompletionTerminationStrategy(TerminationStrategy):
            logger: ClassVar[logging.Logger] = logging.getLogger(__name__)
            
            kernel: ClassVar[Kernel] = self.kernel
            
            termination_function: ClassVar[KernelFunctionFromPrompt] = KernelFunctionFromPrompt(
                function_name="termination",
                prompt_execution_settings=AzureChatPromptExecutionSettings(temperature=0),
                prompt=fr"""
                    You are a data extraction assistant.
                    Check the provided evaluation and return the evalutation score.
                    It MUST be a single number only, for example - for 6/10 return 6.
                    {{{{$evaluation}}}}
                """)

            async def should_agent_terminate(self, agent, history):
                """Terminate if the evaluation score is more then the passing score."""
                
                arguments = KernelArguments()
                arguments["evaluation"] = history[-1].content 
                
                res_val = await self.kernel.invoke(function=self.termination_function, arguments=arguments)
                logger.info(f"Critic Evaluation: {res_val}")
                
                try:
                    should_terminate = float(str(res_val)) >= 8.0         # Using 8 for demo purposes. Try setting to 9.
                except ValueError:
                    logger.error(f"Should terminate error: {ValueError}")
                    should_terminate = False
                    
                logger.info(f"Should terminate: {should_terminate}")
                return should_terminate

        return CompletionTerminationStrategy(agents=agents,
                                             maximum_iterations=maximum_iterations)

    async def process_conversation(self, conversation_messages):
        agent_group_chat = self.create_agent_group_chat()

        # Load chat history - allow only assistant and user messages
        chat_history = [
            ChatMessageContent(
                role=AuthorRole(d.get('role')),
                name=d.get('name'),
                content=d.get('content')
            ) for d in filter(lambda m: m['role'] in ("assistant", "user"), conversation_messages)
        ]

        await agent_group_chat.add_chat_messages(chat_history)

        # async for _ in agent_group_chat.invoke():
        #     pass
        async for a in agent_group_chat.invoke():
            logger.info(f"Agent: {a}")

        response = list(reversed([item async for item in agent_group_chat.get_chat_messages()]))

        # Writer response, as we run termination evaluation on Critic only, so expecting Critic response to be the last
        reply = response[-2].to_dict()

        return reply

    # --------------------------------------------
    # UTILITY - CREATES an agent based on YAML definition
    # --------------------------------------------
    def create_agent(self, kernel, service_id, definition_file_path):

        with open(definition_file_path, 'r') as file:
            definition = yaml.safe_load(file)

        return ChatCompletionAgent(
            service_id=service_id,
            kernel=kernel,
            name=definition['name'],
            execution_settings=AzureChatPromptExecutionSettings(
                temperature=definition.get('temperature', 0.5),
                function_choice_behavior=FunctionChoiceBehavior.Auto(
                    filters={"included_plugins": definition.get('included_plugins', [])}
                )
            ),
            description=definition['description'],
            instructions=definition['instructions']
        )
