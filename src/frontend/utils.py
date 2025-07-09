import logging
import os
from io import StringIO
from subprocess import PIPE, run

import yaml
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    # ConsoleLogExporter
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    # ConsoleMetricExporter
)
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    # ConsoleSpanExporter
)
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider
from rich.logging import RichHandler
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.functions import KernelArguments
from pydantic import BaseModel
from typing import Optional, List

class AzureModel(BaseModel):
    format: str
    name: str
    version: str

class AzureModelDeploymentSku(BaseModel):
    capacity: int
    name: str

class AzureModelDeployment(BaseModel):
    model: AzureModel
    name: str
    sku: AzureModelDeploymentSku
    versionUpgradeOption: str
    
_deployments = None

def load_dotenv_from_azd():
    """
    Load environment variables from Azure Developer CLI (azd) or fallback to .env file.

    Attempts to retrieve environment variables using the 'azd env get-values' command.
    If unsuccessful, falls back to loading from a .env file.
    """
    global _deployments
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info("Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info("AZD environment not found. Trying to load from .env file...")
        load_dotenv()

    deployments_data = yaml.safe_load(os.environ['AI_FOUNDRY_DEPLOYMENTS'])
    if isinstance(deployments_data, list):
        _deployments = [AzureModelDeployment(**item) for item in deployments_data]
    else:
        raise ValueError("AI_FOUNDRY_DEPLOYMENTS is not a list.")
    
    for deployment in _deployments:
        logging.info(f"Loaded deployment: {deployment.name}, model:{deployment.model.name}, version:{deployment.model.version}, SKU:{deployment.sku.name}/{deployment.sku.capacity}")

def get_model_deployment(model_name: str):
    """
    Retrieves a specific Azure model deployment by name.

    Args:
        model_name (str): The name of the model to retrieve.

    Returns:
        AzureModelDeployment: The deployment object if found, otherwise None.
    """
    assert _deployments is not None, "Deployments not loaded. Call load_dotenv_from_azd() first."
    for deployment in _deployments:
        if deployment.model.name == model_name:
            return deployment
    raise ValueError(f"Deployment for model '{model_name}' not found in {[dep.name for dep in _deployments]}.")

telemetry_resource = Resource.create({ResourceAttributes.SERVICE_NAME: os.getenv("AZURE_RESOURCE_GROUP","ai-accelerator")})

# Set endpoint to the local Aspire Dashboard endpoint to enable local telemetry - DISABLED by default
local_endpoint = None
# local_endpoint = "http://localhost:4317"


def set_up_tracing():
    """
    Sets up exporters for Azure Monitor and optional local telemetry.
    """
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logging.info("APPLICATIONINSIGHTS_CONNECTION_STRING is not set skipping observability setup.")
        return

    exporters = []
    exporters.append(AzureMonitorTraceExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    if (local_endpoint):
        exporters.append(OTLPSpanExporter(endpoint=local_endpoint))

    tracer_provider = TracerProvider(resource=telemetry_resource)
    for trace_exporter in exporters:
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    set_tracer_provider(tracer_provider)


def set_up_metrics():
    """
    Configures metrics collection with OpenTelemetry.
    Configures views to filter metrics to only those starting with "semantic_kernel".
    """
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logging.info("APPLICATIONINSIGHTS_CONNECTION_STRING is not set skipping observability setup.")
        return

    exporters = []
    if (local_endpoint):
        exporters.append(OTLPMetricExporter(endpoint=local_endpoint))
    exporters.append(AzureMonitorMetricExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

    metric_readers = [PeriodicExportingMetricReader(exporter, export_interval_millis=5000) for exporter in exporters]

    meter_provider = MeterProvider(
        metric_readers=metric_readers,
        resource=telemetry_resource,
        views=[
            # Dropping all instrument names except for those starting with "semantic_kernel"
            View(instrument_name="*", aggregation=DropAggregation()),
            View(instrument_name="semantic_kernel*"),],
    )
    set_meter_provider(meter_provider)


def set_up_logging():
    """
    Configures logging with OpenTelemetry.
    Adds filters to exclude specific namespace logs for cleaner output.
    """
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        logging.info("APPLICATIONINSIGHTS_CONNECTION_STRING is not set skipping observability setup.")
        return

    exporters = []
    exporters.append(AzureMonitorLogExporter(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

    if (local_endpoint):
        exporters.append(OTLPLogExporter(endpoint=local_endpoint))
    # exporters.append(ConsoleLogExporter())

    logger_provider = LoggerProvider(resource=telemetry_resource)
    set_logger_provider(logger_provider)

    handler = LoggingHandler()

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for log_exporter in exporters:
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

    # FILTER - WHAT NOT TO LOG
    class KernelFilter(logging.Filter):
        """
        A filter to exclude logs from specific semantic_kernel namespaces.
        
        Prevents excessive logging from specified module namespaces to reduce noise.
        """
        # These are the namespaces that we want to exclude from logging for the purposes of this demo.
        namespaces_to_exclude: list[str] = [
            # "semantic_kernel.functions.kernel_plugin",
            "semantic_kernel.prompt_template.kernel_prompt_template",
            # "semantic_kernel.functions.kernel_function",
            "azure.monitor.opentelemetry.exporter.export._base",
            "azure.core.pipeline.policies.http_logging_policy"
        ]

        def filter(self, record):
            return not any([record.name.startswith(namespace) for namespace in self.namespaces_to_exclude])

    # FILTER - WHAT TO LOG - EXPLICITLY
    # handler.addFilter(logging.Filter("semantic_kernel"))
    handler.addFilter(KernelFilter())

def setup_telemetry(name):
    # https://learn.microsoft.com/en-us/semantic-kernel/concepts/enterprise-readiness/observability/telemetry-advanced
    #set_up_tracing()
    #set_up_metrics()
    #set_up_logging()

    # See also https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/trace-application
    
    logging.info("Setting up logging with RichHandler...")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure.monitor.opentelemetry.exporter.export').setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

    logger.info("Configuring Azure Monitor for OpenTelemetry...")
    application_insights_connection_string = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    configure_azure_monitor(connection_string=application_insights_connection_string)

    logging.info("Instrumenting OpenAI SDK for Azure OpenAI...")
    OpenAIInstrumentor().instrument()

    logger.info("Diagnostics: %s", os.getenv('SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS'))
    logger.info("Setting up OpenTelemetry tracer...")
    return trace.get_tracer(name)

async def describe_action(kernel, settings, agent_name, message):
    """
    Determines the next action in an agent conversation workflow.

    Args:
        kernel: The Semantic Kernel instance
        settings: Execution settings for the prompt
        messages: Conversation history between agents

    Returns:
        str: A three-word summary of the next action, indicating which agent should act

    This function analyzes the conversation context to determine workflow progression
    between WRITER and CRITIC agents, with special handling for high-scoring CRITIC responses.
    """
    action_description = await kernel.invoke_prompt(
        function_name="action_description",
        prompt=f"""
        Provided the following chat message summarize the action.

        Provide a six word summary.
        Always indicate WHO takes the action, for example: WRITER: Writes revises draft

        AGENT NAME: {agent_name}
        AGENT_MESSAGE: {message}
        """,
        settings=settings
    )
    return action_description

# --------------------------------------------
# UTILITY - CREATES an agent based on YAML definition
# --------------------------------------------
def create_agent_from_yaml(kernel, service_id, definition_file_path, reasoning_effort=None):
    """
    Creates a ChatCompletionAgent from a YAML definition file.

    Args:
        kernel: The Semantic Kernel instance
        service_id: The service ID to use for the agent
        definition_file_path: Path to the YAML file containing agent definition
        reasoning_effort: Optional reasoning effort parameter for OpenAI models

    Returns:
        ChatCompletionAgent: Configured agent instance

    The YAML definition should include name, description, instructions,
    temperature, and included_plugins.
    """

    with open(definition_file_path, 'r', encoding='utf-8') as file:
        definition = yaml.safe_load(file)

    settings = AzureChatPromptExecutionSettings(
            temperature=definition.get('temperature', 0.5),
            function_choice_behavior=FunctionChoiceBehavior.Auto(
                filters={"included_plugins": definition.get('included_plugins', [])}
            ))

    # Resoning model specifics
    model_id = kernel.get_service(service_id=service_id).ai_model_id
    if model_id.lower().startswith("o"):
        settings.temperature = None
        settings.reasoning_effort = reasoning_effort

    agent = ChatCompletionAgent(
        service=kernel.get_service(service_id=service_id),
        kernel=kernel,
        arguments=KernelArguments(settings=settings),
        name=definition['name'],
        description=definition['description'],
        instructions=definition['instructions']
    )

    return agent