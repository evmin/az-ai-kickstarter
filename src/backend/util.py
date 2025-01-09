import os
import logging
from dotenv import load_dotenv
from io import StringIO
from subprocess import run, PIPE
import asyncio
from typing import Literal

# from opentelemetry import trace
# from opentelemetry._logs import set_logger_provider
# from opentelemetry.metrics import set_meter_provider
# from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
# from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
# from opentelemetry.sdk.metrics import MeterProvider
# from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
# from opentelemetry.sdk.metrics.view import DropAggregation, View
# from opentelemetry.sdk.resources import Resource
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
# from opentelemetry.semconv.resource import ResourceAttributes
# from opentelemetry.trace import set_tracer_provider
# from opentelemetry.trace.span import format_trace_id

# from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
# from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

# from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
# from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
# from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# from opentelemetry.exporter.otlp.proto.grpc import OTLPLogExporter, OTLPMetricExporter, OTLPSpanExporter

from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import set_meter_provider
from opentelemetry.trace import set_tracer_provider

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent, AgentChat
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies import DefaultTerminationStrategy

from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.connectors.ai import PromptExecutionSettings
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.kernel import Kernel
from semantic_kernel.functions import KernelPlugin
from semantic_kernel.utils.logging import setup_logging
from semantic_kernel.core_plugins.time_plugin import TimePlugin

def load_dotenv_from_azd():
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info(f"Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info(f"AZD environment not found. Trying to load from .env file...")
        load_dotenv()

# TODO: Generate the name? Get Current Deployment/RG?
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "ai-accelerator"})

# Endpoint to the Aspire Dashboard
endpoint = "http://localhost:4317"


def set_up_tracing():
    exporters = []
    exporters.append(AzureMonitorTraceExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))
    exporters.append(OTLPSpanExporter(endpoint=endpoint))

    tracer_provider = TracerProvider(resource=resource)
    for trace_exporter in exporters:
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        
    set_tracer_provider(tracer_provider)


def set_up_metrics():
    exporters = []
    exporters.append(OTLPMetricExporter(endpoint=endpoint))
    exporters.append(AzureMonitorMetricExporter.from_connection_string(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

    metric_readers = [PeriodicExportingMetricReader(exporter, export_interval_millis=5000) for exporter in exporters]

    meter_provider = MeterProvider(
        metric_readers=metric_readers,
        resource=resource,
        views=[
            # Dropping all instrument names except for those starting with "semantic_kernel"
            View(instrument_name="*", aggregation=DropAggregation()),
            View(instrument_name="semantic_kernel*"),
        ],
    )
    # Sets the global default meter provider
    set_meter_provider(meter_provider)


def set_up_logging():
    exporters = []
    exporters.append(AzureMonitorLogExporter(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")))

    # TODO: Conditional init if AZD/AspireDashboard Connection is present
#     # if AZD and AspireDashboard Connection:
    exporters.append(OTLPLogExporter(endpoint=endpoint))

    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    handler = LoggingHandler()

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for log_exporter in exporters:
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

    # FILTER - WHAT NOT TO LOG
    class KernelFilter(logging.Filter):
        """A filter to not process records from semantic_kernel."""

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
