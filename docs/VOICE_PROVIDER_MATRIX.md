# Voice provider matrix

This document records the free/best-effort voice-cloning providers wired into the backend. A public demo is not an SLA: it may sleep, queue, change its API, or stop serving requests.

## Bengali voice cloning

| Order | Provider | Space | Status in app | Notes |
|---|---|---|---|---|
| 1 | Bengali CosyVoice3 | `kawshikbuet17/bengali-cosyvoice3-tts-demo` | Primary | Bengali cross-lingual cloning; the public model card identifies Bengali support and Apache-2.0 for the fine-tuned model. |
| 2 | Bengali XTTS-v2 | `EMTIAZZ/bangla-xtts-tts` | Fallback | Independent Gradio Space. Its underlying fine-tune is Coqui XTTS-derived; treat it as non-commercial only unless the model author grants broader rights in writing. |

An optional Vakya/IndicF5 provider pool remains disabled unless `VOICE_CLONE_BN_VAKYA_SPACES` is explicitly configured with a verified Gradio Space matching the backend adapter contract.

## English voice cloning

| Order | Provider | Space | Status in app | Notes |
|---|---|---|---|---|
| 1 | Chatterbox | `ResembleAI/Chatterbox` | Primary | English voice cloning. |
| 2 | Chatterbox Multilingual | `ResembleAI/Chatterbox-Multilingual-TTS` | Fallback | Multilingual model; English is supported, Bengali is not listed in its supported-language set. |
| 3 | Qwen3-TTS Base | `Qwen/Qwen3-TTS` | Fallback | English voice cloning through the Space's Base model, using the 0.6B variant and a transcript of the reference clip. The demo uses Hugging Face ZeroGPU. |

## Runtime and privacy safeguards

- Bengali text is routed only to Bengali-capable providers; standalone English text is routed only to English-capable providers.
- A shared per-job deadline bounds all provider attempts. Individual calls also receive a timeout.
- Provider failure does not bypass the audio/script or video publication safety checks.
- Reference audio is sent to a third-party Space only after the user selects the own-voice cloning feature and submits the job. Do not run automated live-provider tests using a user's personal audio.
- The backend normalizes a temporary server-side copy. The original recording saved on the phone is not modified.
- Do not add paid endpoints, API keys, or billing requirements as automatic fallbacks.

## Free-tier caveats

Hugging Face ZeroGPU is shared, quota-limited infrastructure. The documented free quota is limited per user and can be consumed by API calls as well as the web UI. Free CPU Spaces may sleep when idle. Therefore, “free” means no required paid API plan in this configuration, not guaranteed uptime, unlimited requests, or fixed generation time.

## References

- Bengali CosyVoice3 model card: https://huggingface.co/kawshikbuet17/bengali-cosyvoice3-tts
- Bengali XTTS Space: https://huggingface.co/spaces/EMTIAZZ/bangla-xtts-tts
- XTTS fine-tune model card: https://huggingface.co/EMTIAZZ/xtts-bangla-finetuned
- Chatterbox model card: https://huggingface.co/ResembleAI/chatterbox
- Qwen3-TTS Space: https://huggingface.co/spaces/Qwen/Qwen3-TTS
- Hugging Face ZeroGPU documentation: https://huggingface.co/docs/hub/main/spaces-zerogpu
- Coqui Public Model License: https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt
