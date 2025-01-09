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

# from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
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


# Endpoint to the Aspire Dashboard
endpoint = "http://localhost:4317"
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "hello-ai-4"})

def set_up_tracing():
    exporter = OTLPSpanExporter(endpoint=endpoint)

    # Initialize a trace provider for the application. This is a factory for creating tracers.
    tracer_provider = TracerProvider(resource=resource)
    # Span processors are initialized with an exporter which is responsible
    # for sending the telemetry data to a particular backend.
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    # Sets the global default tracer provider
    set_tracer_provider(tracer_provider)


def set_up_metrics():
    exporter = OTLPMetricExporter(endpoint=endpoint)

    # Initialize a metric provider for the application. This is a factory for creating meters.
    meter_provider = MeterProvider(
        metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=5000)],
        resource=resource,
        views=[
            # Dropping all instrument names except for those starting with "semantic_kernel"
            View(instrument_name="*", aggregation=DropAggregation()),
            View(instrument_name="semantic_kernel*"),
        ],
    )
    # Sets the global default meter provider
    set_meter_provider(meter_provider)


# def set_up_logging():
#     # Create a resource to represent the service/sample
    
#     resource = Resource.create({ResourceAttributes.SERVICE_NAME: "hello-ai-world"})
    
#     class KernelFilter(logging.Filter):
#         """A filter to not process records from semantic_kernel."""

#         # These are the namespaces that we want to exclude from logging for the purposes of this demo.
#         namespaces_to_exclude: list[str] = [
#             "semantic_kernel.functions.kernel_plugin",
#             "semantic_kernel.prompt_template.kernel_prompt_template",
#         ]

#         def filter(self, record):
#             return not any([record.name.startswith(namespace) for namespace in self.namespaces_to_exclude])

#     exporters = []
#     # if settings.connection_string:
#     #     exporters.append(AzureMonitorLogExporter(connection_string=settings.connection_string))
#     # if settings.otlp_endpoint:
#     #     exporters.append(OTLPLogExporter(endpoint=settings.otlp_endpoint))
#     if not exporters:
#         exporters.append(ConsoleLogExporter())

#     # Create and set a global logger provider for the application.
#     logger_provider = LoggerProvider(resource=resource)
#     # Log processors are initialized with an exporter which is responsible
#     # for sending the telemetry data to a particular backend.
#     for log_exporter in exporters:
#         logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
#     # Sets the global default logger provider
#     set_logger_provider(logger_provider)

#     # Create a logging handler to write logging records, in OTLP format, to the exporter.
#     handler = LoggingHandler()
#     # Add filters to the handler to only process records from semantic_kernel.
#     handler.addFilter(logging.Filter("semantic_kernel"))
#     handler.addFilter(KernelFilter())
#     # Attach the handler to the root logger. `getLogger()` with no arguments returns the root logger.
#     # Events from all child loggers will be processed by this handler.
#     logger = logging.getLogger()
#     logger.addHandler(handler)
#     # Set the logging level to NOTSET to allow all records to be processed by the handler.
#     logger.setLevel(logging.NOTSET)

def set_up_logging():
    logger_provider = LoggerProvider(resource=resource)

    exporter = OTLPLogExporter(endpoint=endpoint)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    set_logger_provider(logger_provider)

    handler = LoggingHandler()
    handler.addFilter(logging.Filter("semantic_kernel"))
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)