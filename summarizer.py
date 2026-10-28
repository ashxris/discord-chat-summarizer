"""Groq-powered summarization of Discord message batches."""

from __future__ import annotations

from groq import AsyncGroq

SYSTEM_PROMPT = (
    "You are Chat Summarizer, a summarizer for Discord conversations. "
    "You receive a transcript of messages from a single Discord channel. "
    "Write a concise digest that captures the main topics, key points, decisions, "
    "open questions, and action items. Use short bullet points, stay neutral, and "
    "keep it under 200 words. Refer to people by their Discord usernames. "
    "If the conversation is mostly small talk, say that in one line instead of padding."
)

MAX_TRANSCRIPT_MESSAGES = 400
MAX_CONTENT_CHARS = 1000
REQUEST_TIMEOUT_SECONDS = 45

_clients: dict[str, AsyncGroq] = {}


def _client(api_key: str) -> AsyncGroq:
    client = _clients.get(api_key)
    if client is None:
        client = AsyncGroq(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        _clients[api_key] = client
    return client


async def verify_key(api_key: str) -> None:
    """Raise if Groq rejects the key."""
    await _client(api_key).models.list()


async def model_exists(api_key: str, model: str) -> bool:
    models = await _client(api_key).models.list()
    return any(m.id == model for m in models.data)


def build_transcript(lines: list[str]) -> str:
    """Join formatted message lines, keeping only the most recent ones."""
    return "\n".join(lines[-MAX_TRANSCRIPT_MESSAGES:])


async def summarize(transcript: str, api_key: str, model: str) -> str:
    """Summarize a formatted transcript and return the digest text."""
    response = await _client(api_key).chat.completions.create(
        model=model,
        temperature=0.3,
        max_tokens=700,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    summary = response.choices[0].message.content
    if not summary:
        raise RuntimeError("Groq returned an empty summary")
    return summary.strip()
