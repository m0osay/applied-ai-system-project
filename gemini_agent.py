"""Gemini Flash agentic workflow for PawPal+.

Two-step Plan -> Check loop:
  1. PLAN call  -- identifies care gaps not covered in today's schedule
  2. CHECK call -- validates suggestions against remaining available time
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PLAN_PROMPT = """\
You are a veterinary care advisor reviewing a daily pet care schedule.

Owner: {owner_name}, available time today: {available_minutes} minutes.

Pets:
{pet_list}

Today's scheduled tasks:
{scheduled_tasks}

Skipped tasks (ran out of time):
{skipped_tasks}

Care categories already covered today: {covered_categories}

Your task:
Identify up to 3 specific care gaps NOT covered in today's schedule \
(e.g., no exercise for a dog, no enrichment for a senior cat, no dental care this week).
For each gap:
- Explain in one sentence why it matters for this specific pet (consider species and age).
- Suggest one concrete task to fill the gap with an estimated duration in minutes.

Respond as valid JSON only -- no preamble, no markdown fences:
{{"gaps": [{{"pet_name": "<name>", "gap_type": "<category>", "reason": "<one sentence>", \
"suggestion": "<task description>", "suggested_duration_minutes": <int>}}]}}
"""

CHECK_PROMPT = """\
You are reviewing AI-generated pet care suggestions for feasibility.

Owner's remaining time today: {remaining_minutes} minutes \
(total available: {available_minutes} min, already scheduled: {used_minutes} min).

Proposed care gap suggestions:
{gap_list}

For each suggestion:
- Is there enough remaining time to add it today?
- If yes, mark status as "actionable". If no, mark status as "deferred".
- Add a short confidence note (1 sentence) about whether this suggestion is \
appropriate for the pet's species and age.

Respond as valid JSON only -- no preamble, no markdown fences:
{{"validated_gaps": [{{"pet_name": "<name>", "gap_type": "<category>", \
"suggestion": "<task description>", "suggested_duration_minutes": <int>, \
"status": "actionable or deferred", "confidence_note": "<one sentence>"}}], \
"overall_note": "<1-2 sentence summary of today's pet care situation>"}}
"""


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentInsight:
    gaps: list = field(default_factory=list)
    validated: list | None = None
    overall_note: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class PawPalAgent:
    """Two-step Gemini Flash agent that identifies and validates pet care gaps."""

    def __init__(self) -> None:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            logger.warning(
                "GEMINI_API_KEY not set — PawPalAgent will return fallback insights"
            )
            self._enabled = False
            self._client = None
            return

        try:
            from google import genai

            self._client = genai.Client(api_key=api_key)
            self._model_name = "models/gemini-2.0-flash-lite"
            self._enabled = True
            logger.info("PawPalAgent initialized with Gemini 2.0 Flash Lite")
        except Exception as exc:
            logger.error("Failed to initialize Gemini model: %s", exc)
            self._enabled = False
            self._client = None

    def analyze(self, owner, plan) -> AgentInsight:
        """Run the 2-step Plan -> Check loop and return an AgentInsight."""
        if not self._enabled:
            return self._fallback_insight("GEMINI_API_KEY is not configured.")

        logger.info("Starting agentic analysis for owner '%s'", owner.name)

        # --- Step 1: Plan call ---
        context = self._build_context(owner, plan)
        plan_prompt = PLAN_PROMPT.format(**context)
        logger.info("Sending PLAN prompt to Gemini (%d chars)", len(plan_prompt))

        raw_gaps = self._call_gemini(plan_prompt)
        if raw_gaps is None:
            return self._fallback_insight("Gemini Plan call failed.")

        gaps_data = self._parse_json(raw_gaps)
        if gaps_data is None or "gaps" not in gaps_data:
            return self._fallback_insight("Could not parse gaps from Gemini response.")

        gaps = gaps_data["gaps"]
        logger.info("Plan call identified %d care gap(s)", len(gaps))

        if not gaps:
            return AgentInsight(
                gaps=[],
                validated=[],
                overall_note="No care gaps identified — today's schedule looks well-rounded!",
            )

        # --- Step 2: Check call ---
        remaining = owner.available_minutes_per_day - plan.total_minutes_used
        check_context = {
            "remaining_minutes": max(remaining, 0),
            "available_minutes": owner.available_minutes_per_day,
            "used_minutes": plan.total_minutes_used,
            "gap_list": json.dumps(gaps, indent=2),
        }
        check_prompt = CHECK_PROMPT.format(**check_context)
        logger.info("Sending CHECK prompt to Gemini (%d chars)", len(check_prompt))

        raw_validated = self._call_gemini(check_prompt)
        if raw_validated is None:
            logger.warning("Check call failed — returning unvalidated gaps")
            return AgentInsight(gaps=gaps, validated=None, overall_note="")

        validated_data = self._parse_json(raw_validated)
        if validated_data is None:
            logger.warning("Could not parse Check response — returning unvalidated gaps")
            return AgentInsight(gaps=gaps, validated=None, overall_note="")

        validated = validated_data.get("validated_gaps", [])
        overall_note = validated_data.get("overall_note", "")

        actionable = sum(1 for v in validated if v.get("status") == "actionable")
        deferred = sum(1 for v in validated if v.get("status") == "deferred")
        logger.info(
            "Check call complete — %d actionable, %d deferred", actionable, deferred
        )

        return AgentInsight(gaps=gaps, validated=validated, overall_note=overall_note)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_gemini(self, prompt: str) -> str | None:
        """Send a single prompt to Gemini and return the text response."""
        try:
            response = self._client.models.generate_content(
                model=self._model_name, contents=prompt
            )
            text = response.text
            logger.info("Gemini responded with %d chars", len(text))
            return text
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            return None

    def _parse_json(self, text: str) -> dict | None:
        """Parse a JSON response, stripping markdown code fences if present."""
        try:
            clean = text.strip()
            if clean.startswith("```"):
                # strip opening fence line (e.g. ```json)
                clean = clean.split("\n", 1)[-1]
                # strip closing fence
                clean = clean.rsplit("```", 1)[0]
            result = json.loads(clean.strip())
            logger.debug("JSON parsed successfully")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse Gemini JSON response: %s", exc)
            return None

    def _build_context(self, owner, plan) -> dict:
        """Assemble template variables from Owner and DailyPlan."""
        pet_lines = [
            f"- {pet.name} ({pet.species}, {pet.age} years old)"
            for pet in owner.pets
        ]

        scheduled_lines = [
            f"- {item.pet_name}: {item.task.description} "
            f"({item.task.category or 'general'}, {item.task.duration_minutes} min)"
            for item in plan.items
        ] or ["None scheduled"]

        skipped_lines = [
            f"- {pet_name}: {task.description} ({task.duration_minutes} min)"
            for pet_name, task in plan.skipped_tasks
        ] or ["None"]

        covered = {
            (item.task.category or "general").lower()
            for item in plan.items
        }

        return {
            "owner_name": owner.name,
            "available_minutes": owner.available_minutes_per_day,
            "pet_list": "\n".join(pet_lines) or "No pets",
            "scheduled_tasks": "\n".join(scheduled_lines),
            "skipped_tasks": "\n".join(skipped_lines),
            "covered_categories": ", ".join(sorted(covered)) or "none",
        }

    def _fallback_insight(self, reason: str) -> AgentInsight:
        logger.warning("Returning fallback AgentInsight: %s", reason)
        return AgentInsight(error=reason)
