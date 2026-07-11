"""Tool-calling agent loop.

Each step the LLM emits a JSON action (constrained by a response schema, so a
small local model stays reliable): either call a tool or give a final answer.
Tool observations are fed back until the model answers or the step budget runs
out. Grounded on live data + KB; refuses when tools yield nothing relevant.
"""

from __future__ import annotations

import json
import re

from app.agent import tools as toolmod
from app.llm import engine


def _parse_action(raw: str) -> dict | None:
    """Tolerant parse of the model's JSON action (handles raw newlines in strings)."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Model emitted literal newlines inside a string — escape and retry.
    try:
        return json.loads(raw.replace("\r", "").replace("\n", "\\n"))
    except json.JSONDecodeError:
        pass
    # Last resort: pull the answer field out directly.
    m = re.search(r'"answer"\s*:\s*"(.*)"\s*}?\s*$', raw, re.S)
    if m:
        return {"action": "final_answer", "answer": m.group(1).replace("\\n", "\n").strip()}
    return None

MAX_STEPS = 6

_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "action": {
            "type": "string",
            "enum": list(toolmod.TOOLS.keys()) + ["final_answer"],
        },
        "action_input": {"type": "object"},
        "answer": {"type": "string"},
    },
    "required": ["thought", "action"],
}

REFUSAL = (
    "I don't have grounded information to answer that confidently, so I won't guess. "
    "I can help with live heat forecasts and rankings, tract detail and land cover, "
    "heat anomalies, address lookups, model accuracy, and how the system works."
)


def _system_prompt() -> str:
    return (
        "You are CityGuide, the operator copilot for AusTwin — Austin's urban climate "
        "digital twin. Answer operator questions by CALLING TOOLS to fetch live data and "
        "knowledge, then giving a grounded, cited answer.\n\n"
        "Available tools:\n"
        f"{toolmod.tools_doc()}\n\n"
        "Protocol: respond ONLY with a JSON object with keys 'thought', 'action', and "
        "either 'action_input' (an object of arguments for a tool) or 'answer' (when "
        "action is 'final_answer'). Call one tool at a time. Chain multiple tools for "
        "multi-step questions (e.g. find the hottest tract, then get its detail). To "
        "COMPARE tracts, first call rank_tracts to learn their names, then call get_tract "
        "for each. CRITICAL GROUNDING RULE: report ONLY values that appear in a tool "
        "observation. You must call a tool for EVERY data type the user asks about — if "
        "they ask about air quality, call air_quality; about current weather, call "
        "current_weather; etc. NEVER estimate, recall, or invent a number, tract, AQI, or "
        "threshold. In the 'answer' string, write plain sentences and DO NOT use raw line "
        "breaks — keep it to flowing prose. When you have enough grounded information, set "
        "action to 'final_answer' with the complete answer in 'answer', citing the data "
        "sources. If tools return nothing relevant, say you don't have that information.\n"
        "NWS heat-index bands: 80-90F Caution, 90-103F Extreme Caution, 103-124F Danger, "
        "125F+ Extreme Danger."
    )


def run_agent(question: str) -> dict:
    """Returns {answer, tools_used, live_used, refused, steps}."""
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": question},
    ]
    tools_used: list[str] = []
    live_used: list[str] = []
    last_observation = ""

    for step in range(MAX_STEPS):
        raw = engine.chat(
            messages,
            response_format={"type": "json_object", "schema": _ACTION_SCHEMA},
            temperature=0.1,
            max_tokens=512,
        )
        obj = _parse_action(raw)
        if obj is None:
            # Unparseable — treat its text as the final answer.
            return {
                "answer": raw or REFUSAL,
                "tools_used": tools_used,
                "live_used": live_used,
                "refused": not raw,
                "steps": step + 1,
            }

        action = obj.get("action")
        if action == "final_answer":
            answer = (obj.get("answer") or "").strip()
            # Reject placeholder answers (e.g. "[us_aqi]") — force the real tool call.
            if step < MAX_STEPS - 1 and re.search(r"\[[a-z0-9_ ]+\]", answer):
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your answer contains placeholders like [us_aqi]. Do NOT use "
                            "placeholders. Call the tool that provides each missing value "
                            "(e.g. air_quality, weather_alerts) and then answer with real numbers."
                        ),
                    }
                )
                continue
            return {
                "answer": answer or last_observation or REFUSAL,
                "tools_used": tools_used,
                "live_used": live_used,
                "refused": not answer and not last_observation,
                "steps": step + 1,
            }

        observation, live = toolmod.run_tool(action, obj.get("action_input") or {})
        last_observation = observation
        if action not in tools_used:
            tools_used.append(action)
        if live and live not in live_used:
            live_used.append(live)

        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": f"Observation from {action}: {observation}"})

    # Ran out of steps — force a final synthesis from what we gathered.
    messages.append(
        {
            "role": "user",
            "content": "Give your final answer now, in plain prose, using only the observations above.",
        }
    )
    try:
        final = engine.chat(messages, temperature=0.2, max_tokens=512)
    except Exception:  # noqa: BLE001
        final = last_observation or REFUSAL
    return {
        "answer": final or last_observation or REFUSAL,
        "tools_used": tools_used,
        "live_used": live_used,
        "refused": False,
        "steps": MAX_STEPS,
    }
