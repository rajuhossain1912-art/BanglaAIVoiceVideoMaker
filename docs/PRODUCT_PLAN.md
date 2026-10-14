# Final Product Requirements

## Product direction
Bangla AI Voice Video Maker is an online-only Android app intended to create a complete video automatically from text, or from matching text plus a supplied voice recording. Offline operation is not a product requirement.

## Input modes
1. Text only: accept Bangla, English, or mixed-language text; use an online text-to-speech service; derive a title and scene plan; generate or select suitable visual assets; synchronize captions; render a video.
2. Text plus audio: accept a script and an audio file; transcribe or align speech with the supplied script; synchronize sentence captions and word highlighting; use the same automatic visual and rendering pipeline.

## Automatic pipeline
- Detect language and infer topic and tone.
- Create a title and scene-by-scene visual plan.
- Generate or select appropriately licensed images/video assets.
- Generate TTS when no voice file is supplied.
- Align captions and word timing with speech, with a correction fallback.
- Apply automatic zoom, pan, transitions, and readable subtitle styling.
- Render an MP4 and provide a download/save link.
- Report progress and errors accessibly.

## Accessibility
- TalkBack labels and state announcements for every important control.
- Clear Bengali UI/status messages.
- Screen-reader accessible input, audio selection, progress, and download.
- Never make visual-only confirmation necessary.

## Constraints
- Online-only; show a clear message when there is no validated internet connection.
- Prioritize free/open-source options; no paid API or subscription without explicit approval.
- Never claim generation is complete unless the backend confirms it.
- Keep secrets on the server, not in Android source code.
- Consider processing limits, timeouts, upload size, privacy, and cleanup for user files.

## Current implementation milestone
The initial Android Compose shell and APK workflow are being added. The online AI/video backend, actual generation pipeline, audio upload, word alignment, and MP4 rendering are not yet implemented. The UI must communicate this honestly until those pieces are connected.
