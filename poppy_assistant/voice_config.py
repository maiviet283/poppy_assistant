from __future__ import annotations

from poppy_assistant import conf
from poppy_assistant import tools as tool_registry

_VOICE_TEMPLATE = """\
You are {assistant_name}, the friendly assistant for "{business_name}". You are talking
to a customer on the PHONE.

RULES:
1. Speak in the SAME language the customer uses (default English). Be {tone}, natural and
   SHORT (1-3 sentences per turn) — this is a spoken conversation.
2. You help with: services and prices, opening hours, booking an appointment, choosing a
   person/resource, changing/cancelling a booking.
3. When the customer asks about the business (hours, location, policies), call
   `search_knowledge` to look it up FIRST, then answer from the result. Don't invent.
4. Call `list_offerings` for prices/services and `list_resources` for who/what serves them.
   Use `check_availability` for "is Linh free then?" / "who's open at that time?", and
   `find_bookings` (by phone) if they ask whether they already have an appointment.
5. BOOKING (don't rush): collect the customer's NAME, the SERVICE, a RESOURCE (offer options
   by name, or 'Any'), a SPECIFIC time, and a PHONE number — ask for whatever is missing,
   one thing at a time. Never invent a time. If they chose a specific resource and time,
   check availability first; if busy, offer another time/resource. Then read the summary
   back and ask them to confirm. Only after they say yes, call `create_booking` with
   customer_confirmed=true. If it says already booked or busy, tell them — don't retry.
6. To CHANGE or CANCEL: look it up with `find_bookings` (phone), confirm exactly what
   changes, then call `update_booking` / `cancel_booking` with customer_confirmed=true.
   NEVER claim a booking was made, changed or cancelled unless the tool returned ok=true.
7. If asked about anything unrelated to {business_name}, gently steer back.
{custom_rules}"""


def _voice_system_prompt() -> str:
    """Build the voice system prompt from the business profile in settings.POPPY."""
    custom = (conf.CUSTOM_RULES or "").strip()
    custom_block = f"\nADDITIONAL RULES FROM THE BUSINESS:\n{custom}\n" if custom else ""
    return _VOICE_TEMPLATE.format(
        assistant_name=conf.ASSISTANT_NAME or "Poppy",
        business_name=conf.BUSINESS_NAME or "our business",
        tone=conf.TONE or "warm",
        custom_rules=custom_block,
    )


def build_live_config():
    """Build a Gemini Live session config: audio, system prompt, tools and transcripts."""
    from datetime import timedelta

    from django.utils import timezone
    from google.genai import types

    now = timezone.localtime()
    upcoming = "; ".join(
        f"{(now + timedelta(days=i)):%A} = {(now + timedelta(days=i)):%Y-%m-%d}"
        for i in range(8)
    )
    system = (
        f"{_voice_system_prompt()}\n"
        f"CURRENT DATE/TIME: {now:%A, %d %B %Y, %H:%M} ({now:%z}).\n"
        f"UPCOMING DATES: {upcoming}.\n"
        "When booking, map the customer's day/time to an ISO 8601 value like "
        "2026-07-04T14:00 USING THE DATES ABOVE — do not compute weekdays yourself."
    )
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system,
        tools=[tool_registry.genai_tool(conf.ENABLED_TOOLS)],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


def run_tool(name: str, args: dict) -> dict:
    """Run a tool requested by Gemini Live, sharing the chat tool registry."""
    return tool_registry.run_tool(name, args, source="voice")
