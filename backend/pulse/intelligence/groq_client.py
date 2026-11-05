from __future__ import annotations

import json
import logging
from typing import Any

from pulse.config import get_settings

logger = logging.getLogger("pulse.groq")


class GroqRaceAnalyst:
    """Interacts with Groq API for strategic race intelligence synthesis."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None
        self._auth_failed: bool = False
        if self.settings.groq_enabled and self.settings.groq_api_key:
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(
                    api_key=self.settings.groq_api_key,
                    max_retries=0,
                    timeout=4.0,
                )
                logger.info("Groq Async client initialized with model %s", self.settings.groq_model)
            except Exception as e:
                logger.warning("Could not initialize Groq client: %s", e)

    @property
    def is_available(self) -> bool:
        return self._client is not None and not self._auth_failed

    async def generate_tactical_briefing(
        self,
        driver_name: str,
        driver_number: int,
        team: str,
        position: int,
        event_type: str,
        pit_delta_saving: float,
        stint_laps: int,
        tyre_compound: str,
        gap_to_next: str,
        evidence: list[str],
    ) -> dict[str, Any]:
        """Generate a consumer-perspective F1 race tactical analysis and driver radio."""
        # Fallback response in case Groq is unavailable or fails
        fallback = {
            "headline": f"{driver_name} inside critical pit window under {event_type}",
            "narrative": (
                f"{driver_name} ({team}) gains approximately {pit_delta_saving:.1f}s net pit loss advantage "
                f"under {event_type}. Pitting from P{position} on {stint_laps}-lap old {tyre_compound} tyres offers "
                f"protection against rivals."
            ),
            "forecast": f"Likely to retain P{position} - P{position + 1} across the pit cycle",
            "alternative": "Stay out if track clears and green flag resumes immediately",
            "driver_radio": f"Box box, {driver_name}, box this lap! VSC pit delta is {pit_delta_saving:.1f} seconds advantage.",
            "confidence": 84,
            "tactical_recommendation": "BOX THIS LAP",
        }

        if not self.is_available:
            return fallback

        prompt = f"""
You are the Lead Race Strategy Engineer for an elite Formula 1 team.
Analyze the following live race situation and return a JSON object with consumer-oriented strategic clarity:

Driver: {driver_name} (#{driver_number}), Team: {team}, Current Position: P{position}
Race Event: {event_type}
Pit Lane Time Saving from Neutralisation: {pit_delta_saving:.1f} seconds
Tyre Compound: {tyre_compound}, Stint Age: {stint_laps} laps
Gap Context: {gap_to_next}
Evidence: {', '.join(evidence)}

Respond ONLY with a valid JSON object matching this schema:
{{
  "headline": "Punchy 6-10 word title explaining the situation to an F1 fan",
  "narrative": "Crisp 2-sentence explanation of why this moment is decisive for the race outcome",
  "forecast": "1-sentence prediction of position/interval over next 1-2 laps",
  "alternative": "1-sentence what-if scenario if the team does the opposite",
  "driver_radio": "Realistic authentic team radio transmission from race engineer to driver",
  "confidence": 85,
  "tactical_recommendation": "BOX THIS LAP or STAY OUT or MONITOR"
}}
"""
        try:
            chat_completion = await self._client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a world-class Formula 1 strategist providing instant, authoritative race commentary. Output JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.settings.groq_model,
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=1024,
            )
            raw_text = chat_completion.choices[0].message.content
            parsed = json.loads(raw_text)
            return {
                "headline": parsed.get("headline", fallback["headline"]),
                "narrative": parsed.get("narrative", fallback["narrative"]),
                "forecast": parsed.get("forecast", fallback["forecast"]),
                "alternative": parsed.get("alternative", fallback["alternative"]),
                "driver_radio": parsed.get("driver_radio", fallback["driver_radio"]),
                "confidence": int(parsed.get("confidence", fallback["confidence"])),
                "tactical_recommendation": parsed.get("tactical_recommendation", fallback["tactical_recommendation"]),
            }
        except Exception as e:
            if "401" in str(e) or "invalid_api_key" in str(e) or "AuthenticationError" in type(e).__name__:
                self._auth_failed = True
                logger.warning("Groq API authentication rejected (401 invalid key). Falling back to deterministic tactical synthesis.")
            else:
                logger.error("Groq inference error: %s, using deterministic fallback", e)
            return fallback


_analyst: GroqRaceAnalyst | None = None


def get_groq_analyst() -> GroqRaceAnalyst:
    global _analyst
    if _analyst is None:
        _analyst = GroqRaceAnalyst()
    return _analyst

