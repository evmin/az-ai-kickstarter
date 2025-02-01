import os
import logging
from typing import ClassVar
import datetime

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
from semantic_kernel.functions import KernelPlugin, KernelFunctionFromPrompt, KernelArguments

from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
# from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
# from azure.ai.inference.aio import ChatCompletionsClient
# from azure.identity.aio import DefaultAzureCredential
# from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from opentelemetry.trace import get_tracer

from pydantic import Field
import util

class SemanticOrchestrator:
    
    def __init__(self):

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("Semantic Orchestrator Handler init")

        self.logger.info("Creating - %s", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        api_key = os.getenv("aoaikeysecret", None)
        
        # Not used - waiting for the fix with o1
        # credential = AzureKeyCredential(api_key) if api_key else DefaultAzureCredential()
        # inference_service = AzureAIInferenceChatCompletion(
        #     ai_model_id="o1-mini",
        #     service_id="SERVICE_MODEL",
        #     instruction_role="developer",
        #     client=ChatCompletionsClient(
        #         endpoint=f"{str(endpoint).strip('/')}/openai/deployments/{deployment_name}",
        #         credential=credential,
        #         credential_scopes=["https://cognitiveservices.azure.com/.default"],
        #     ))
        
        print(f"API Version: {api_version}")
        
        if (api_key):
            inference_srv = AzureChatCompletion(
                service_id="SERVICE_MODEL",
                instruction_role="developer",
                endpoint=endpoint,
                deployment_name=deployment_name,
                api_version=api_version,
                api_key=api_key)
        else:
            inference_srv = AzureChatCompletion(
                service_id="SERVICE_MODEL",
                instruction_role="developer",
                endpoint=endpoint,
                deployment_name=deployment_name,
                api_version=api_version,
                ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(),"https://cognitiveservices.azure.com/.default"))
        
        self.kernel = Kernel(
            # services=[inference_service],
            services=[inference_srv],
            plugins=[
                KernelPlugin.from_object(plugin_instance=TimePlugin(), plugin_name="time")
            ])
        
        # Utility Execution Settings: speaker selector, terminator
        # self.utility_settings = AzureChatPromptExecutionSettings(service_id="SERVICE_MODEL", temperature=0)
        self.utility_settings = AzureChatPromptExecutionSettings(service_id="SERVICE_MODEL")
        
        self.resourceGroup = os.getenv("AZURE_RESOURCE_GROUP")
        

    # --------------------------------------------
    # Create Agent Group Chat
    # --------------------------------------------
    def create_agent_group_chat(self):

        self.logger.debug("Creating chat")

        writer = util.create_agent_from_yaml(service_id="SERVICE_MODEL",
                                        kernel=self.kernel,
                                        definition_file_path="agents/writer.yaml")
        critic = util.create_agent_from_yaml(service_id="SERVICE_MODEL",
                                        kernel=self.kernel,
                                        definition_file_path="agents/critic.yaml")
        agents=[writer, critic]

        agent_group_chat = AgentGroupChat(
                agents=agents,
                selection_strategy=self.create_selection_strategy(agents, critic),
                termination_strategy = self.create_termination_strategy(
                                         agents=[critic],
                                         maximum_iterations=6))

        return agent_group_chat

    # --------------------------------------------
    # Speaker Selection Strategy
    # --------------------------------------------
    def create_selection_strategy(self, agents, default_agent):
        """Speaker selection strategy for the agent group chat."""
        definitions = "\n".join([f"{agent.name}: {agent.description}" for agent in agents])
        # settings = AzureChatPromptExecutionSettings(temperature=0,service_id="gpt-4o")
        
        selection_function = KernelFunctionFromPrompt(
                function_name="SpeakerSelector",
                prompt_execution_settings=self.utility_settings,
                prompt=fr"""
                    You are the next speaker selector.

                    - You MUST return ONLY agent name from the list of available agents below.
                    - You MUST return the agent name and nothing else.
                    - The agent names are case-sensitive and should not be abbreviated or changed.
                    - Check the history, and decide WHAT agent is the best next speaker
                    - You MUST call CRITIC agent to evaluate WRITER RESPONSE
                    - YOU MUST OBSERVE AGENT USAGE INSTRUCTIONS.

# AVAILABLE AGENTS

{definitions}

# CHAT HISTORY

{{{{$history}}}}
""")

        # Could be lambda. Keeping as function for clarity
        def parse_selection_output(output):
            self.logger.info("------- Speaker selected: %s", output)
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
            
            iteration: int = Field(default=0)
            kernel: ClassVar[Kernel] = self.kernel
            
            termination_function: ClassVar[KernelFunctionFromPrompt] = KernelFunctionFromPrompt(
                function_name="TerminationEvaluator",
                prompt_execution_settings=self.utility_settings,
                prompt=fr"""
                    You are a data extraction assistant.
                    Check the provided evaluation and return the evalutation score.
                    It MUST be a single number only, for example - for 6/10 return 6.
                    {{{{$evaluation}}}}
                """)

            async def should_agent_terminate(self, agent, history):
                """Terminate if the evaluation score is more then the passing score."""
                
                self.iteration += 1
                self.logger.info(f"Iteration: {self.iteration} of {self.maximum_iterations}")
                
                arguments = KernelArguments()
                arguments["evaluation"] = history[-1].content 

                res_val = await self.kernel.invoke(function=self.termination_function, arguments=arguments)
                self.logger.info(f"Critic Evaluation: {res_val}")

                try:
                    # 9 is a relatively high score. Set to 8 for stable result.
                    should_terminate = float(str(res_val)) >= 8.0        
                except ValueError:
                    self.logger.error(f"Should terminate error: {ValueError}")
                    should_terminate = False
                    
                self.logger.info(f"Should terminate: {should_terminate}")
                return should_terminate

        return CompletionTerminationStrategy(agents=agents,
                                             maximum_iterations=maximum_iterations)

    async def process_conversation(self, user_id, conversation_messages):
        agent_group_chat = self.create_agent_group_chat()
       
        # Load chat history
        chat_history = [
            ChatMessageContent(
                role=AuthorRole(d.get('role')),
                name=d.get('name'),
                content=d.get('content')
            ) for d in filter(lambda m: m['role'] in ("assistant", "user"), conversation_messages)
        ]

        await agent_group_chat.add_chat_messages(chat_history)

        tracer = get_tracer(__name__)
        
        # UNIQUE SESSION ID is a must
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        session_id = f"{user_id}-{current_time}"
        
        with tracer.start_as_current_span(session_id):
            # async for _ in agent_group_chat.invoke():
                #     pass
            async for a in agent_group_chat.invoke():
                self.logger.info("Agent: %s", a)

        response = list(reversed([item async for item in agent_group_chat.get_chat_messages()]))

        # Writer response, as we run termination evaluation on Critic, ther last message will be from Critic
        reply = [r for r in response if r.name == "Writer"][-1].to_dict()
        
        return reply