# Final Product Requirements

## Product direction
Bangla AI Voice Video Maker is an online-only Android app intended to create a complete video automatically from Bangla, English, or mixed-language text, or synchronize supplied voice with a script. The app itself requires internet access.

## Primary feature: the user's own cloned voice
The main target is not merely attaching a pre-recorded narration. A user should be able to provide a short recording of their own voice, explicitly consent to using it for cloning, and then have newly typed text spoken in that same voice. The resulting generated speech must feed directly into the video renderer.

- Keep a reusable voice profile only when the user explicitly chooses to save it; provide a way to delete it.
- Explain clearly whether the voice sample is processed locally or sent to a third-party service, before uploading it.
- Never send samples to an unapproved third-party demo or store them publicly.
- Never add paid APIs, subscriptions, hosting, or paid GPU services without explicit user approval.
- If a free provider is unavailable, over quota, or cannot handle the request, explain that clearly and keep the uploaded-audio fallback available.

## Mixed-language text is required
A single script may freely mix Bengali and English, including sentence-level and phrase-level switching, for example: "আসসালামু আলাইকুম everyone, আজকে আমরা AI voice cloning নিয়ে কথা বলব." The system must not select one voice for the whole script merely because it contains some Bengali characters.

Acceptance criteria:
- Detect or segment mixed Bengali/English text without deleting or reordering words.
- Preserve punctuation, numerals, names, and English technical terms as far as the selected model supports them.
- Prefer one multilingual cloning model that can speak both Bengali and English in the same cloned speaker identity.
- If a model cannot reliably do this, disclose the limitation and test alternatives before claiming support.
- Test Bengali-only, English-only, and mixed-language samples separately for intelligibility, voice similarity, and latency.

## Input modes
1. Text only: the online API receives the script and creates speech in the user's saved cloned voice (when available), visuals, captions, and MP4.
2. First-time voice setup: record or upload a short sample of the user's own voice, review consent/privacy information, and create a voice profile only if a verified provider is available.
3. Text plus audio: upload a script and voice file; align the script to speech, create captions and a video, then return a downloadable MP4.
4. Fallback: allow ordinary TTS or supplied narration when voice cloning cannot run, with a clear explanation that this is not cloned speech.

## Automatic pipeline
- Detect language and infer topic and tone.
- Create a title and scene-by-scene visual plan.
- Generate or select appropriately licensed images/video assets.
- Generate speech in the selected cloned voice when a verified voice-cloning provider is available.
- Align captions and word timing with speech; offer a correction fallback.
- Apply automatic zoom, pan, transitions, and readable subtitle styling.
- Render an MP4 and provide a download/save link.
- Report progress and errors accessibly.

## Free-first policy
- Prioritize open-source software, openly licensed models, and free tiers.
- Do not enable a paid API, subscription, or paid hosting without explicit user approval.
- Free-tier limits, cold starts, model quotas, and resource restrictions must be disclosed.
- Do not claim that a service is unlimited or permanently free unless verified.
- Render's free web service must not be assumed capable of hosting a large voice-cloning model; evaluate model hosting and quota constraints before integration.

## Accessibility
- TalkBack labels and state announcements for every important control.
- Clear Bengali UI/status messages.
- Screen-reader accessible recording, audio selection, text entry, progress, and download.
- Never make visual-only confirmation necessary.

## Privacy and security
- Keep API keys on the server, never in Android source or APK.
- Limit upload size and script length.
- Use HTTPS, clear errors, and cleanup temporary user files.
- Do not expose uploaded audio, cloned voice profiles, or generated videos publicly.
- Ask explicit consent before cloning a voice; design for the user's own voice or a voice they have permission to use.

## Current implementation milestone
The repository contains an initial Android Compose app and a Docker-based FastAPI backend prototype. The backend can create a basic MP4 with a generated graphic background, a supplied audio file or espeak-ng speech, and estimated sentence subtitles. It does not yet implement voice cloning, persistent voice profiles, mixed-language cloned speech, AI-generated photographic scenes, or exact word-level alignment. Job records and generated files are temporary and can disappear after a server restart. These limitations must be disclosed until improved.
