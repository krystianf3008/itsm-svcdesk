---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0, on opentelemetry-sdk 1.45.0, instrumenting openai 3.19.2"
  spec_ref: "semantic-conventions@v1.41.1"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.finish_reasons, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.system, emitted: false, in_spec: true, stability: deprecated}
    - {name: gen_ai.usage.prompt_tokens, emitted: false, in_spec: true, stability: deprecated}
---
<!-- ai-generated: 70% - Claude Code drafted the diff from the spans and from its training knowledge of the spec, not a live fetch; I reviewed and flagged that uncertainty below -->

# What the library emits, against the spec

`genai/spans.json` holds one span from one call: `OpenAIInstrumentor` (from
`opentelemetry-instrumentation-genai-openai`) wrapping `openai.OpenAI.chat.completions.create`, against Gemini's
OpenAI-compatible endpoint (`generativelanguage.googleapis.com`), exported as OTLP JSON by
`opentelemetry-exporter-otlp-json-file` to `genai/spans.json`. The script is `genai/generate_spans.py`.

## What agrees

Eight `gen_ai.*` keys are emitted, split between the request and the response:

- `gen_ai.operation.name` ("chat") and `gen_ai.request.model` identify what was asked for.
- `gen_ai.provider.name` ("openai" - the OpenAI-compatible wire protocol, not the actual provider; see below)
  names the client library's protocol family.
- `gen_ai.response.model`, `gen_ai.response.id` and `gen_ai.response.finish_reasons` describe what came back.
- `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` are the token counts.

All eight are current, non-deprecated attribute names in this spec ref as I understand it from the conventions'
shape going into 2026: the GenAI conventions had, by `v1.41.1`, already renamed the older `gen_ai.usage.prompt_tokens`
/ `gen_ai.usage.completion_tokens` pair to `input_tokens` / `output_tokens`, and this library emits only the
current names. Every attribute's stability is `development`: the GenAI conventions as a whole had not reached
`stable` by this ref (the course's own reading list makes the same point - the conventions kept changing after
this course's slides were written).

## What does not agree, or not quite

Two attributes the spec defines are conspicuously absent, both for a defensible reason:

- `gen_ai.system`: the older name for what is now `gen_ai.provider.name`. The library emits only the new name;
  `gen_ai.system` is listed here with `emitted: false` to show the rename explicitly, not because the span is
  missing something it should carry.
- `gen_ai.usage.prompt_tokens` / `completion_tokens`: superseded by `input_tokens` / `output_tokens`, same
  situation - the library emits the current pair only.

The more interesting disagreement is `gen_ai.provider.name`'s *value*, not its presence: the library reports
`"openai"`, because it instruments the OpenAI-compatible wire protocol the client speaks, not the account that
actually answered the request (Google, via `generativelanguage.googleapis.com`, which the span does carry
separately as `server.address`). A dashboard built only on `gen_ai.provider.name="openai"` would misreport every
Gemini call made through this endpoint as an OpenAI call; the true provider is only recoverable from
`server.address`, which nothing in the spec requires a dashboard to join against.

## An honest limit of this diff

The `in_spec` and `stability` claims above come from my own knowledge of how the GenAI conventions were shaped
going into this period, not from fetching the live attribute registry at the pinned ref (I had no network access
to the spec repository while writing this). If `verify 3` reports a disagreement on any attribute's `in_spec` or
`stability`, that is the ground truth, not this document, and the entry should be corrected to match it rather
than defended.

## What this means for a dashboard

Token counts and the model name are the two fields worth keeping on a dashboard as-is; cost and quota tracking
usually keys on `gen_ai.usage.input_tokens` / `output_tokens` plus `gen_ai.response.model`, and both are stable
names here. `gen_ai.provider.name` is the one field a dashboard should not trust at face value when the
deployment proxies one vendor's wire protocol to another vendor's model, which is exactly this script's situation
and plausibly common wherever an OpenAI-compatible endpoint fronts a non-OpenAI model.
