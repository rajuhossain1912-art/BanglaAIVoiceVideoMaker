# Evidence-Based Video Quality Gate and Open-Source Options

## User safety rule

A technically playable MP4 is not automatically safe to publish. A video must not be labelled shareable when a required check is missing, estimated, unavailable, or failed. Unknown is not pass. Keep the generated file private on the server while release checks are incomplete.

## Required independent checks

1. **Narration transcription:** compare the produced narration audio with the approved script. Preserve missing/extra token counts. A high similarity score is a screening signal, not proof of perfect pronunciation.
2. **Word alignment:** use actual acoustic word boundaries. Never substitute proportional or silence-based estimates and call them exact.
3. **Subtitle rendering OCR:** read text back from the final rendered caption frames, compare it with the expected caption window, and flag missing, altered, clipped, or unreadable text. Bengali and English need separate OCR language configuration where possible.
4. **Visual semantic review:** inspect every final background image against its exact narration scene. Sampling is not sufficient for a full-release pass. If any image cannot be reviewed, the release gate remains blocked.
5. **Technical media checks:** verify audio/video streams, duration, dimensions, black frames, frozen frames, audio silence/clipping, and frame decode errors.
6. **Accessible result:** return a concise Bangla report with each check marked passed, failed, or unavailable. Never convert unavailable into passed.

## Open-source candidates researched

### Bengali speech recognition
- `bengaliAI/tugstugi_bengaliai-asr_whisper-medium` is referenced by the Bengali VSR dataset pipeline as its Bengali ASR model. Benchmark it against real app samples before replacing the existing Whisper service.
- `AdibAFC/Robust-Long-Form-Bangla-Speech-Processing` documents a Bengali long-form pipeline using VAD and tuned Whisper decoding. Its reported WER is project-specific and must not be treated as a guarantee for this app.
- `psdn-ai/bangla-asr` publishes a Bengali fine-tuned Whisper-medium checkpoint. It is a candidate for offline benchmarking, but the model is substantially larger than the current hosted Whisper API and should not be placed on the Render Free web service without memory/latency tests.
- `ehzawad/whisper-large-v3-turbo-bn-BD` is a Bangladesh Bengali fine-tune, but its model card specifies research-only, non-commercial use and gated weights. It is not suitable for this public production app without written permission.
- `AI4Bharat/IndicConformerASR` lists a Bengali model and MIT code license. Verify the individual checkpoint license, model download size, runtime dependencies and actual word error rate before integrating.

### Word-level timing
- `AI4Bharat/IndicMFA` publishes a Bengali acoustic model and grapheme-to-grapheme pronunciation dictionary as part of its 22-language forced-alignment project. This is the strongest native-script Bengali alignment candidate found so far. It requires Montreal Forced Aligner and corpus/model artifacts, so it must be benchmarked in an isolated worker before adoption.
- `jahurulislam741/bangla-align` is a Bengali-specific MFA workflow that produces phoneme-level TextGrids. Its README describes a manual dictionary-correction step; it is a research/tooling candidate, not a ready-to-run free API.
- `arham-sayyed/mms-forced-align` is **not a native Bengali-script aligner**. Its current README says its model vocabulary is Latin letters and its examples support English or romanized Indic text only. Do not feed Bengali script into it or treat its word times as Bengali-validated.
- `Animesh6096/bengali-vsr-dataset` documents a Bengali pipeline using VAD, Bengali Whisper ASR and alignment, but the exact model assets and runtime constraints need separate validation. Its confidence examples are useful as a safety concept, not a production guarantee.
- `byseon/voxalign` is not selected for production until its model language coverage, license and alignment quality are independently verified.

### Bengali subtitle OCR
- Tesseract OCR is Apache-2.0 and the official Tesseract data repositories include Bengali trained data. The backend now installs Tesseract with Bengali and English language packs and runs OCR against every generated caption frame, in small batches. It verifies that each frame's active highlighted word can be recognized. Missing OCR, missing words or a failed batch blocks publication.
- This OCR check is deliberately limited: it confirms the active word in each caption frame, not a human-level review of every surrounding word, font choice, reading comfort or subtitle/audio timing. It must not be described as complete subtitle proofreading.
- PaddleOCR's published supported-language lists and the Bengali language-support discussion must be checked against the exact deployed version. Do not assume Bengali recognition is supported merely because a language is listed as a discussion request.

### Visual and media checks
- Keep OpenCV/FFmpeg checks for black frames, duplicate frames, blur, freeze, audio clipping and decode errors as technical signals only. They do not establish that a picture depicts the narration.
- Keep a vision-language reviewer for semantic image checks, but require structured visible-content descriptions and an explicit result. A bare MATCH/MISMATCH response or a quota error is unavailable, never a pass.

## Deployment constraints and acceptance process

- Do not add a large model to the Render free service until memory, CPU, cold-start time, model license and request limits are measured.
- Prefer small OCR packages and CPU-friendly ONNX models where feasible. Check each model's license separately from the repository's code license.
- Build a fixed Bengali/English test corpus from user-approved audio and scripts. Include names, numbers, mixed-language phrases, long sentences, repeated words, quiet speech, pauses, and deliberately omitted/inserted words.
- Record word error rate, alignment coverage, OCR character error rate, image-review coverage, false-pass rate, latency and peak memory.
- A new provider becomes an active fallback only after it passes the same regression corpus. Do not silently switch to an untested provider.
- Until every required release check has passed, `share_allowed` must remain false and the download endpoint must refuse release.

## Research links

- https://github.com/Animesh6096/bengali-vsr-dataset
- https://github.com/AdibAFC/Robust-Long-Form-Bangla-Speech-Processing
- https://github.com/eulogik/PolyWhisper
- https://github.com/AI4Bharat/IndicMFA
- https://github.com/jahurulislam741/bangla-align
- https://github.com/arham-sayyed/mms-forced-align
- https://github.com/AI4Bharat/IndicConformerASR
- https://github.com/psdn-ai/bangla-asr
- https://github.com/byseon/voxalign
- https://github.com/tesseract-ocr/tesseract
- https://github.com/tesseract-ocr/tessdata
- https://github.com/PaddlePaddle/PaddleOCR/discussions/17776
