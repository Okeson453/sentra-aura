# Voice Agent

**Domain:** creative · **ID:** `voice_agent`

## Architecture §4.2
TTS narration with tone/speed/pronunciation.
**In:** polished script, voice profile  
**Out:** audio segments with word-level timing, TTS metadata

## Tools (tool_permissions.py)
| Name | Decision | Backend |
|------|----------|---------|
| `synthesize_speech` | ALLOW | provider-gateway `POST /v1/tts` |
| `clone_voice` | ESCALATE | not auto-run (legal review) |

## Upstream
Consumes `scripting_agent` `ScriptResponse.script` (`hook`/`intro`/`sections`/`cta`/`outro`).
