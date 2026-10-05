"""Answer generation with Groq: grounded prompt, numbered citations, query rewriting."""

import re
import time
from collections.abc import AsyncIterator
from functools import lru_cache

from groq import AsyncGroq, Groq, RateLimitError

from app.config import get_settings
from app.retrieval import Hit

# The eval checks for this exact phrase to score refusals on out-of-scope questions.
NOT_FOUND = "I couldn't find this in the Acts I have access to"

SYSTEM_PROMPT = f"""You are Nyaya, an assistant that answers questions about three Indian laws:
the Digital Personal Data Protection Act 2023, the Right to Information Act 2005, and the
Consumer Protection Act 2019.

Rules:
- Answer ONLY from the numbered sources provided. Do not use outside knowledge.
- Cite every factual sentence with the source number(s) in plain square brackets, e.g. [1] or [2][3].
  Never use 【】, † or line-range citation markers.
- Name the Act and section when you state a rule, e.g. "Under Section 7(1) of the RTI Act ...".
- Quote exact figures (days, amounts, ages) as written in the source.
- If the sources do not contain the answer, reply exactly: "{NOT_FOUND}." and, in one short
  sentence, say what the sources do cover. Never guess.
- Be concise: a direct answer first, then supporting detail as short bullets if useful.
- You provide legal information, not legal advice."""

REWRITE_PROMPT = """Rewrite the user's latest question as a standalone search query about Indian
law, resolving pronouns and references using the conversation. Output only the query."""


@lru_cache
def client() -> Groq:
    return Groq(api_key=get_settings().groq_api_key or None)


@lru_cache
def aclient() -> AsyncGroq:
    return AsyncGroq(api_key=get_settings().groq_api_key or None)


def llm_configured() -> bool:
    return bool(get_settings().groq_api_key)


_NATIVE_CITE = re.compile(r"【(\d+)(?:†[^】]*)?】")


def normalize_citations(text: str) -> str:
    """gpt-oss sometimes emits its native 【1†L1-L3】 style; map it to [1]."""
    return _NATIVE_CITE.sub(r"[\1]", text)


def model_kwargs(model: str, effort: str | None = None) -> dict:
    """gpt-oss models are reasoning models; others don't accept reasoning_effort."""
    if "gpt-oss" in model:
        return {"reasoning_effort": effort or get_settings().reasoning_effort}
    return {}


def format_sources(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{i}] {h.header}\n{h.content}" for i, h in enumerate(hits, start=1))


def build_messages(question: str, hits: list[Hit], history: list[dict] | None = None) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-6:]:
        msgs.append({"role": turn["role"], "content": turn["content"]})
    msgs.append({"role": "user", "content": f"Sources:\n\n{format_sources(hits)}\n\nQuestion: {question}"})
    return msgs


def complete(messages: list[dict], model: str | None = None, *, json_mode: bool = False,
             max_tokens: int = 2048, effort: str | None = None, retries: int = 6) -> str:
    """Blocking completion with backoff on rate limits (used by eval + rewriting)."""
    model = model or get_settings().answer_model
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    kwargs |= model_kwargs(model, effort)
    for attempt in range(retries):
        try:
            resp = client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=max_tokens,
                **kwargs,
            )
            return normalize_citations(resp.choices[0].message.content or "")
        except RateLimitError as e:
            # Daily quotas don't recover in a useful time; let the caller stop/resume.
            if attempt == retries - 1 or "per day" in str(e):
                raise
            wait = float(e.response.headers.get("retry-after", 2 ** attempt * 5))
            time.sleep(min(wait, 120))
    raise RuntimeError("unreachable")


def rewrite_query(question: str, history: list[dict]) -> str:
    if not history:
        return question
    convo = "\n".join(f"{t['role']}: {t['content'][:500]}" for t in history[-4:])
    out = complete(
        [
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest question: {question}"},
        ],
        model=get_settings().rewrite_model,
        max_tokens=300,
        effort="low",
    )
    return out.strip().strip('"') or question


async def stream_answer(question: str, hits: list[Hit], history: list[dict] | None = None) -> AsyncIterator[str]:
    model = get_settings().answer_model
    stream = await aclient().chat.completions.create(
        model=model,
        messages=build_messages(question, hits, history),
        temperature=0.1,
        max_tokens=2048,
        stream=True,
        **model_kwargs(model),
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
