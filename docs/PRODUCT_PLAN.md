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

## Automatic AI brain and research-context milestone — 2026-11-12

- Before visual planning, the backend asks the configured free Cloudflare Workers AI model chain to classify the supplied narration's language, topic, content type, tone, audience and visual style.
- For factual topics only, the model may return up to three neutral research queries. The backend searches public Bengali or English Wikipedia and attaches small source snippets and page links to the video plan.
- Research context is supplied to the scene visual planner, but the exact current narration remains authoritative for each scene. The user's supplied narration is not rewritten.
- The AI plan and research source list are included in the job status and video quality report for accessible review.
- Research snippets are context only, not independently fact-checked claims. Multi-source corroboration, current-news research, reliable official-source ranking, factual claim checking and automatic correction remain future work.
- If Cloudflare AI or public research is unavailable, the pipeline uses a local fallback and reports the limitation. No paid API is enabled.

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
- The GitHub Release APK is built with the persistent signing key and pinned certificate so it can update the same installed application. It is a direct-distribution APK, not a Google Play Store production release.
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


## Consolidated verification and release-safety milestone — 2026-11-13

- Added a repository-wide project audit at docs/PROJECT_AUDIT.md covering commit history, AI models, external providers, hosting/build infrastructure, verified implementation, and unfinished work.
- The publication gate now requires every final scene image to have a verified semantic match, rejects unresolved duplicate final images, requires exact script/transcript token coverage, explicit complete word timestamps with integrity checks, subtitle OCR success, and technical video/audio checks. The download endpoint repeats the gate at download time.
- Missing/unreadable image similarity comparisons now fail closed as duplicate/unknown instead of being treated as distinct; regression coverage is added.
- README claims were synchronized with current scene planning, Whisper timestamps, OCR and persistent APK signing.
- Visual semantic review now defaults to every final AI-generated or licensed contextual photo scene. A positive IMAGE_SEMANTIC_REVIEW_MAX_SCENES value is an explicit operator cap; any scene outside that cap remains unreviewed and the publication gate continues to block sharing. Topic-graphic fallback is still not accepted by the photographic semantic-review gate and remains a known blocker requiring a separately validated illustration-review path.
- Full-scene review can consume more free vision-model quota and increase render time. If the provider rate-limits or becomes unavailable, the gate fails closed; this is intentional and must be explained in the app rather than bypassed.
- Current Render service health/deploy/log/environment state and latest GitHub Actions/Release success still require live verification. Source code or workflow configuration alone is not proof of a successful deploy/build.

## Current verified implementation status — 2026-11-17

This section supersedes older statements above wherever they describe the current implementation.

### Android release and job recovery
- Latest verified direct-distribution APK: v0.3.224. Release workflow #224 / run 43936012789 succeeded, including release build, package/version identity, persistent signing key, APK signature verification, artifact upload and GitHub Release publication.
- PR #41 is merged. Android stores the active backend job ID in SharedPreferences and, after Activity/process recreation, attempts to resume status polling for that existing server job. Temporary polling interruption retains the ID; a terminal server status clears it.
- This is not guaranteed background execution and does not recover a job whose in-memory state or output file has already been lost by a Render restart/spin-down. Durable backend storage and a WorkManager/service-owned lifecycle remain future work.
- No physical-device install/update, TalkBack acceptance or screen-off test has been completed.

### Visual verification and publication safety
- `IMAGE_SEMANTIC_REVIEW_MAX_SCENES` defaults to 0, meaning all final scene images are selected for semantic review. A positive configured cap leaves scenes outside the cap unreviewed; the publication gate blocks any video without a verified final-scene match.
- Topic graphics are checked through a separate vision-review path after the final graphic has been selected. A matched review is recorded as final visual status `matched`; mismatch or unavailable review remains blocked. Unreviewed topic graphics are not accepted.
- The gate also requires exact narration/transcript token coverage, complete explicit word timestamps with timing integrity, subtitle OCR success, no unresolved duplicate final images, and technical audio/video checks. The download endpoint repeats the gate.
- These automated checks do not guarantee human-level semantic correctness, perfect subtitle spelling, or suitability for every audience. Keep publication fail-closed when a check is unknown.

### Voice cloning reality
- Bengali default provider is the public Bengali CosyVoice3 demo. The optional Bengali Vakya backup list defaults to empty unless an operator configures a verified compatible Space.
- English defaults to Chatterbox, with Chatterbox Multilingual as a configured fallback.
- `ai4bharat/IndicF5` is a model repository, not a hosted Gradio Space, and must not be represented as a working Space fallback.
- External public demos may be unavailable, rate-limited, changed, or have unknown data-retention behavior. The app cannot guarantee uptime, quota, privacy controls or voice similarity.
- Render Free has no persistent storage attached; durable reusable cloned-voice profiles are not supported by the current backend. User samples remain on the phone until cloning is requested, at which point the sample/text are sent to the external provider.

### Hosting and live verification
- Render service `bangla-ai-voice-video-maker-api` is currently not suspended, on Free Docker, one instance, auto-deploy from main; current service metadata reports healthCheckPath `/health`.
- Latest inspected deploy `dep-dbtl9tfb9u1s73at7r7g` is live. The request-log query did not return a `/health` entry, so metadata and deploy are confirmed but an individual health-probe request is not independently evidenced by logs.
- Job state remains in memory and files remain on ephemeral storage. No Render Postgres or Key Value service is attached. A server restart may lose active jobs and generated files.
- Historical Render logs include external image-search/provider timeouts and an audio-QC unavailable event; they are not evidence of a current outage, but provider reliability remains a risk.

### Remaining acceptance work
1. Test v0.3.224 update installation on the user's Android phone, with TalkBack, without asking for visual-only inspection.
2. Exercise job resume with app process recreation while the backend job is still alive; separately document backend restart loss.
3. Run a real Bangla, English and mixed-language voice-clone test with explicit consent and assess pronunciation, voice similarity and provider availability.
4. Verify current provider timeouts and image diversity under realistic Free-tier constraints; do not bypass semantic review or publication gate.
5. Add durable job/file storage only if a genuinely free and supportable option is available and explicitly approved; do not silently add paid services.
