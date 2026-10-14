# Voice Cloning Evaluation — 2026-10-15

## Goal
Allow each Android user to provide a short sample of their own voice, enter Bengali or English text, generate speech in that voice, and use the audio in the video pipeline. Free-first only; do not add paid APIs or services without explicit approval.

## Findings

### Bengali candidate: Bengali CosyVoice3 TTS
- Model: https://huggingface.co/kawshikbuet17/bengali-cosyvoice3-tts
- Model card declares Apache-2.0 and Bengali TTS, recommends cross-lingual voice-cloning mode.
- The published demo accepts a reference recording of 1–30 seconds and text up to 500 characters; the demo source shows a queue with max size 4 and default concurrency 1.
- Base model: FunAudioLLM/Fun-CosyVoice3-0.5B-2512, whose model card declares Apache-2.0 and lists English among its nine supported languages.
- Important: the Bengali fine-tune is documented for Bengali; English generation using this fine-tune has NOT been runtime-verified. Do not promise bilingual quality until English test audio is generated and reviewed.
- The public demo was marked Running during source inspection. This is not a successful end-to-end audio-generation test and does not guarantee uptime or permission to use that third-party Space as a production backend.

### English candidate: Chatterbox
- Project: https://github.com/resemble-ai/chatterbox
- Model card declares MIT and supports reference-audio voice cloning. Its published multilingual list includes English but not Bengali.
- Suitable as an English test candidate, not a single-engine Bengali/English solution based on currently published language support.

### Free hosting constraints
- Render free web services use 0.1 CPU and 512 MB RAM; this is not an appropriate place to load a 0.5B voice-cloning model, and the existing video API is not a GPU model host.
- Hugging Face ZeroGPU documentation lists a free-account quota of 5 minutes of GPU time per day and up to two hosted ZeroGPU Spaces for eligible accounts. This is useful for a limited demo, not a dependable unlimited service for every app user.
- A public third-party Space must not be treated as a guaranteed, private, or production API. Voice samples are sensitive data; any eventual integration must disclose where samples go, obtain explicit user consent, and avoid retaining samples unnecessarily.

## Verification status
- Android GitHub Actions build for commit 5ddda0cf277d6924e3990b587eecd4f1744c8590: PASS (debug APK artifact created).
- Android source/build verification does not prove the online video backend works.
- Voice-cloning model cards, licenses, source code, demo status, and free-hosting constraints were inspected.
- Actual audio inference with a Bengali sample and an English sample: NOT YET TESTED in this environment. Network/runtime access did not permit submitting audio to the live demo.
- Production integration: NOT IMPLEMENTED. No API keys or paid services were added.

## Recommended next test sequence
1. Manually verify the public Bengali CosyVoice3 demo with a speaker-consented 5–10 second voice sample and a short Bengali script.
2. Try an English script with the same reference sample; assess intelligibility, accent, speaker similarity, and latency. Treat it as experimental until verified.
3. Compare with Chatterbox for English only.
4. Before production, choose a hosting route with explicit privacy and quota controls; do not route all users' recordings to an unapproved third-party demo.
5. Add a provider interface and fallback only after model and hosting tests pass. Keep the ordinary TTS and uploaded-audio options available.

## References
- Bengali model: https://huggingface.co/kawshikbuet17/bengali-cosyvoice3-tts
- Bengali demo source: https://huggingface.co/spaces/kawshikbuet17/bengali-cosyvoice3-tts-demo
- CosyVoice3 base model: https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
- Chatterbox: https://github.com/resemble-ai/chatterbox
- Render free service limits: https://render.com/docs/compute-plans
- Hugging Face ZeroGPU limits: https://huggingface.co/docs/hub/spaces-zerogpu
