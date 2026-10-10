# ai-generated: 90% - Claude Code drafted, reviewed by me
"""One-off script for Stretch 1 (MONITORING-SPEC.md M-28): makes one instrumented LLM call through Gemini's
OpenAI-compatible endpoint and writes the OTLP spans to genai/spans.json. Not part of the deployed service - not
copied into the svcdesk image, run once by hand:

    python3 -m venv /tmp/genai-venv && source /tmp/genai-venv/bin/activate
    pip install openai==3.19.2 opentelemetry-sdk==1.45.0 \
        opentelemetry-instrumentation-genai-openai==1.2b0 opentelemetry-exporter-otlp-json-file==0.66b0
    GEMINI_API_KEY=... python3 genai/generate_spans.py

The key is read from the environment only; it is never written to a file.
"""
import os

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Import path per the HANDOUT's package name (opentelemetry-exporter-otlp-json-file); if this differs from what
# pip installed, run `python3 -c "import opentelemetry.exporter.otlp.json.file as m; print(dir(m))"` to find the
# real module and class name and fix this import.
from opentelemetry.exporter.otlp.json.file import FileSpanExporter

SPANS_PATH = os.path.join(os.path.dirname(__file__), "spans.json")

provider = TracerProvider(resource=Resource.create({"service.name": "svcdesk-genai-diff"}))
provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(path=SPANS_PATH)))
trace.set_tracer_provider(provider)

OpenAIInstrumentor().instrument()

client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
response = client.chat.completions.create(
    model="gemini-3.8-flash",
    messages=[{"role": "user", "content": "In one sentence, what does a Prometheus histogram bucket boundary do?"}],
)
print(response.choices[0].message.content)

provider.shutdown()  # flushes the span to genai/spans.json before the process exits
print(f"wrote spans to {SPANS_PATH}")
