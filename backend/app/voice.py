"""ElevenLabs voice alert (Sakshi's Task 7).

text_to_speech("...") -> mp3 bytes. Clips are cached in memory, so replaying the
same demo line doesn't use extra ElevenLabs credits.
"""
import hashlib
import logging

import httpx

from . import config

log = logging.getLogger("lightsout.voice")

MAX_CHARS = 400  # keep alerts short (and cheap)
_cache: dict[str, bytes] = {}


class VoiceUnavailable(Exception):
    """No key, or ElevenLabs failed. The page falls back to the browser's own voice."""


def short_text(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    end = cut.rfind(". ")
    return cut[: end + 1] if end > 100 else cut.rstrip() + "."


def text_to_speech(text: str) -> bytes:
    if not config.ELEVENLABS_API_KEY:
        raise VoiceUnavailable("ELEVENLABS_API_KEY is empty")
    text = short_text(text)
    if not text:
        raise ValueError("text is empty")

    key = hashlib.sha1(f"{config.ELEVENLABS_VOICE_ID}|{text}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    try:
        r = httpx.post(
            url,
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
            json={
                "text": text,
                "model_id": config.ELEVENLABS_MODEL,
                # calm and clear: steady voice, not too expressive
                "voice_settings": {"stability": 0.6, "similarity_boost": 0.75},
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise VoiceUnavailable(f"ElevenLabs unreachable: {exc}") from exc
    if r.status_code != 200:
        log.warning("ElevenLabs error %s: %s", r.status_code, r.text[:200])
        raise VoiceUnavailable(f"ElevenLabs HTTP {r.status_code}")

    _cache[key] = r.content
    return r.content
