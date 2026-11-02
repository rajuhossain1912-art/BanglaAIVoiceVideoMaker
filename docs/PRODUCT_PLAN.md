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

## Current implementation milestone — 2026-11-02

The repository now contains an Android Jetpack Compose app and a FastAPI/FFmpeg video backend.

Implemented and covered by automated checks:
- Text-only Bangla, English and mixed-language video generation; supplied-audio video generation; experimental own-voice recording, local sample storage, preview, explicit consent and remote voice-clone attempts.
- Free-provider voice-clone fallback: Bengali CosyVoice3 for Bangla/mixed text and Chatterbox first for English, with CosyVoice3 fallback. Provider runtime success and voice similarity are not guaranteed.
- Scene-level visual planning through optional Cloudflare Workers AI, AI-image provider fallback, licensed-image fallback and topic-graphic fallback. Up to 32 representative visual backgrounds are generated for long scripts.
- 3, 5, 10, 15 and 20-second scene intervals; persistent subtitle timing adjustment from -1.5 to +1.5 seconds; vertical MP4 rendering; automatic pan/zoom; per-word caption highlighting with estimated word timing.
- Technical MP4 report, download endpoint, Bangla status messages and TalkBack progress announcements.
- Main-screen/settings navigation, including Android Back handling, and local deletion of the saved voice sample.
- GitHub Actions backend end-to-end smoke checks and Android APK build/release.

Known limitations that must remain visible to users:
- Voice cloning depends on public third-party Hugging Face Spaces. Their availability, quotas, data retention and privacy controls are outside this app's control. Do not promise a successful clone or a permanent private voice model. Actual user-device audio quality and provider output still require a human test.
- Mixed-language cloned speech uses the Bengali provider whenever Bengali characters occur; consistent pronunciation and same-speaker similarity across Bangla and English are not guaranteed.
- Word highlight timing is estimated from sentence duration and silence detection, not a true forced-alignment model. Technical reports do not verify spoken words or caption spelling.
- AI images may be irrelevant or repetitive despite prompt planning and similarity checks. Topic graphics are a fallback, not photographic images.
- A separate title-card builder, animated scene transitions and a dedicated in-app social sharing flow are not yet implemented; the completed MP4 can be saved through Android's Downloads manager.
- The GitHub Releases APK is a debug build for direct device testing, not a production-signed Play Store package.
- Job state is held in process memory and files in temporary storage. The free backend accepts one active video job at a time and removes completed/failed job folders after the configured retention window (24 hours by default). Render restarts can still make active jobs or recent downloads unavailable.
- The free Render service can sleep and has limited CPU/RAM. Long scripts, external image providers and cloning services can be slow or fail.
- There is no guaranteed unlimited service, no paid provider is enabled, and no external provider's privacy behavior is represented as controlled by this app.

## Professional interface and background execution milestone — 2026-11-02

- Android Material 3 brand palette with a restrained green primary color and light neutral surfaces.
- Main screen removes redundant explanatory copy while preserving essential input labels, TalkBack announcements, consent warnings, progress, and actionable results.
- Settings are grouped into expandable categories: video/voice mode, visuals/subtitle timing, saved voice, and screen-off processing.
- During voice recording, an Android microphone foreground service displays an ongoing notification and holds a partial CPU wake lock; it stops when recording ends. During video generation, a data-sync foreground service does the same until the generation flow completes or fails.
- Screen-off/background operation is supported while Android keeps the app/service alive. Force-stop, device shutdown, aggressive OEM battery controls, network loss, Android foreground-service time limits, or process termination can still interrupt work; this must not be described as an absolute guarantee.
- The foreground service currently protects the app process while the activity's generation coroutine polls the backend. It does not yet persist and resume a lost polling coroutine after a process death. A future milestone should move the complete job lifecycle and job ID persistence into the service or WorkManager with foreground execution.
