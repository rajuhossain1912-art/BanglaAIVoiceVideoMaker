# Final Product Requirements

## Product direction
Bangla AI Voice Video Maker is an online-only Android app intended to create a complete video automatically from Bangla, English, or mixed-language text, or synchronize supplied voice with a script. The app itself requires internet access.

## Input modes
1. Text only: the online API receives the script and creates speech, a visual design, captions, and MP4.
2. Text plus audio: upload a script and voice file; align the script to speech, create captions and a video, then return a downloadable MP4.

## Automatic pipeline
- Detect language and infer topic and tone.
- Create a title and scene-by-scene visual plan.
- Generate or select appropriately licensed images/video assets.
- Generate TTS when no voice file is supplied.
- Align captions and word timing with speech; offer a correction fallback.
- Apply automatic zoom, pan, transitions, and readable subtitle styling.
- Render an MP4 and provide a download/save link.
- Report progress and errors accessibly.

## Free-first policy
- Prioritize open-source software, openly licensed models, and free tiers.
- Do not enable a paid API, subscription, or paid hosting without explicit user approval.
- Free-tier limits, cold starts, model quotas, and resource restrictions must be disclosed.
- Do not claim that a service is unlimited or permanently free unless verified.

## Accessibility
- TalkBack labels and state announcements for every important control.
- Clear Bengali UI/status messages.
- Screen-reader accessible input, audio selection, progress, and download.
- Never make visual-only confirmation necessary.

## Privacy and security
- Keep API keys on the server, never in Android source or APK.
- Limit upload size and script length.
- Use HTTPS, clear errors, and cleanup temporary user files.
- Do not expose uploaded audio or generated videos publicly.

## Current implementation milestone
The repository contains an initial Android Compose app and a Docker-based FastAPI backend prototype. The backend can create a basic MP4 with a generated graphic background, a supplied audio file or espeak-ng speech, and estimated sentence subtitles. It does not yet create AI-generated photographic scenes or exact word-level alignment. Job records and generated files are temporary and can disappear after a server restart. These limitations must be disclosed until improved.
