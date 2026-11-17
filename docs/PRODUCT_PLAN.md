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
- Latest verified direct-distribution APK: v0.3.225. Release workflow run 44043382156 succeeded, including release build, package/version identity, persistent signing key, APK signature verification, artifact upload and GitHub Release publication. PR #42 merged as a4e27b32b43590da173ec15ab582af4a629ee85a; it clarifies Android background-work limits and uses direct stopService calls for four stop paths.
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
- Android code merge deploy `dep-dbu0k73rjlhs73b6klv0` reached live; latest audit documentation deploy `dep-dbu0kn5bedkc73esa6a0` also reached live. The request-log query did not return a `/health` entry, so metadata and deploy are confirmed but an individual health-probe request is not independently evidenced by logs.
- Job state remains in memory and files remain on ephemeral storage. No Render Postgres or Key Value service is attached. A server restart may lose active jobs and generated files.
- Historical Render logs include external image-search/provider timeouts and an audio-QC unavailable event; they are not evidence of a current outage, but provider reliability remains a risk.

### Remaining acceptance work
1. Test v0.3.225 update installation on the user's Android phone, with TalkBack, without asking for visual-only inspection.
2. Exercise job resume with app process recreation while the backend job is still alive; separately document backend restart loss.
3. Run a real Bangla, English and mixed-language voice-clone test with explicit consent and assess pronunciation, voice similarity and provider availability.
4. Verify current provider timeouts and image diversity under realistic Free-tier constraints; do not bypass semantic review or publication gate.
5. Add durable job/file storage only if a genuinely free and supportable option is available and explicitly approved; do not silently add paid services.


### Latest release update — 2026-11-17
- v0.3.225 release tag target: `a4e27b32b43590da173ec15ab582af4a629ee85a`.
- APK SHA-256: `88e1d0bb193d95e6bbddff1a84135698515c275c49e5fa735052765744c6d7a8`; size 10,736,616 bytes.
- Direct APK: https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/releases/download/v0.3.225/BanglaAIVoiceVideoMaker-v0.3.225.apk
- Physical install/update and TalkBack validation remain outstanding.


### Latest quality fix — PR #43 (2026-11-17)
- Added specific Bangla motivation-to-image mappings: retrying after failure, learning from a mistake, steady practice toward a goal, and taking a concrete first step toward a dream.
- Replaced the overly generic motivation prompt that could lead the visual planner to depict unrelated manual-labor activities.
- PR #43 merged as 76f925bede140a6d5da7c83ad414786b13f05dc8; backend CI run 44047382875 succeeded (138 unit tests); Render deploy dep-dbu11qjrjlhs73b742j0 live.
- The fix does not address the observed 40% audio/script match, missing/extra transcript words, missing explicit word timestamps, or subtitle OCR timeout. Publication remains fail-closed.
- Next engineering priorities: diagnose Bengali TTS/Whisper mismatch with provider/audio evidence; reduce OCR batch processing time without skipping any caption word; then re-run a real device test. No paid provider or new secret was added.


### Latest audio and subtitle QA updates — 2026-11-17
- PR #44 merged (`f9a6c9af36b363546944229b3ef754e5cf7de168`): provide Cloudflare Whisper a `bn`/`en` hint only for clearly monolingual supplied scripts; mixed scripts retain auto-detection. Previous-text conditioning is disabled for narration QC. CI run 44048026905 passed.
- PR #45 merged (`2def815ae723dc859ffc81a5bf794df50593b07a`, parent includes PR #44): Tesseract subtitle OCR uses 4-frame batches and a 45-second per-batch timeout; explicit timeout diagnostics retain completed-frame counts. CI run 44048287657 passed (140 tests).
- Render deployment dep-dbu13t7pq7jc739ktl30 was queued at last check; do not treat the changes as live until confirmed.
- These are targeted reliability improvements, not proof that the user's 40.45% transcript match or OCR timeout is resolved. Retest the same narration and confirm exact transcript, complete word timestamps and every OCR frame. Publication remains fail-closed.


### Latest visual-quality fixes — 2026-11-17
- PR #46 merged (a29b2aa6ba61b1694ff9dd115ff9857cc6e892ef): repeated narration slots now carry occurrence/total context into storyboard planning and review, so 3-second cadence slots can use distinct but faithful visual moments. Motivational image concepts now use grounded indoor desk/learning-workspace scenes rather than vague manual tasks. CI 44049785590 passed (141 tests); Render deploy dep-dbu1abbbc2fs73fmc5kg live; E2E 44050081207 passed.
- PR #47 merged (35417cd71f30ec5a00a065914e664bc452bc7d9e): independent vision review explicitly rejects unrelated agricultural activity for motivational scripts that do not mention agriculture, while preserving legitimate farming scenes. CI 44050411831 passed; Render deploy dep-dbu1bnbbc2fs73fmdpe0 live; E2E 44050498051 passed including Bangla/English generation and production health.
- These changes improve scene planning and strengthen rejection of off-topic visuals. They do not guarantee perfect image correctness. Re-test a real user motivational video and review the final scene descriptions; do not loosen publication gating if vision review is unavailable or uncertain.
- Next: re-run the user's same Bengali script after the latest live deployment, compare image descriptions against each narration scene, verify transcript similarity and exact word timestamps, and confirm all subtitle OCR frames are checked. Physical Android/TalkBack acceptance remains outstanding.

### Latest follow-up from the user's 26.5-second motivational video — 2026-11-17
- PR #48 merged (4182a152d56f752e09d416182a52f24a5f437bac): motivational fallback keyword matching now includes failure, never-give-up, patience, perseverance and self-confidence terms, so this script no longer falls through to the generic landscape illustration solely because its first sentence uses “হাল ছেড়ে” and “ব্যর্থতা”. Regression CI 44053440137 passed; Render deploy dep-dbu1lfijnfac73dti560 is live; health and root requests returned HTTP 200.
- The user's report still shows independent audio QC at 40% similarity (25 missing and 28 extra tokens), incomplete real word timestamps, and OCR timeout after 8 checked frames. These are not fixed by PR #48 and remain release blockers. Keep download/share blocked until exact audio verification, complete provider-supplied word timestamps, and full subtitle OCR all pass.
- Investigate the Tesseract processing cost and the Cloudflare Whisper output returned for this exact narration. Do not fabricate word timing from sentence duration or accept a transcript by feeding the expected script back as a recognition prompt.

### ASR and subtitle OCR follow-up — 2026-11-17
- PR #49 merged (7d3ecfef296b910cd40c30ec13c4b8a2fc48788e): generated narration QC now calls Whisper with VAD filtering disabled; uploaded audio and reference-clip transcription keep the existing VAD default. CI 44053935012 and main E2E 44054177454 passed; Render dep-dbu1n5tbedkc73etlceg live with HTTP 200 health checks. This may protect quiet words from VAD trimming but does not prove the user's transcript match improved.
- PR #50 merged (caa4a63fd96f780b7294ff32e12dc0273e40316f): OCR processes the active yellow word crop from every caption frame, with a contextual OCR retry for ambiguous Bengali words and a spatial-overlap check against the highlight. No frames are skipped and no gate is weakened. CI 44054590949 passed; Render dep-dbu1op0ae00c73a57i9g live; / and /health returned HTTP 200.
- A local synthetic test using the user's 43-word script recognized all 43 active words in about 5.1 seconds, including contextual retries. This is not a production benchmark.
- Still unresolved until the user re-runs the same script: exact ASR word match, complete provider-supplied word timestamps, and full subtitle OCR on the actual generated video. Main E2E run 44054702523 was pending when this note was written.

### Real OCR integration test — 2026-11-17
- PR #51 merged (cd76148515edb5e402632db628551185afb7ecb3): added a real Tesseract test that renders all 43 subtitle frames for the user's exact Bengali script through the production caption renderer and requires every active word to be recognized. It runs when Tesseract and both language packs are available; the Docker E2E image provides them. Backend CI 44055071535 passed.
- Main Docker E2E run 44055157228 was queued at the time of this note. This test is synthetic and does not replace a real user video retest or guarantee Render production OCR timing.

### Current engineering status — 2026-11-18 (supersedes earlier "Next engineering priorities" notes above)

- PR #52–#56 strengthened Bengali active-word OCR without skipping caption frames: multiple Tesseract page-segmentation retries, isolated highlighted-word crops, Bengali/English language packs and Noto Bengali fonts in CI, and the PSM 10 fallback. PR #56's real Tesseract synthetic integration test recognized all 43 words from the user's 43-word sample.
- PR #57 added a bounded transcript preview to the accessible audio QC report, so the user can compare what Whisper actually recognized. PR #58 classifies Cloudflare daily free-allocation exhaustion separately from authentication, rate-limit and server errors.
- PR #59 preserves Whisper's detected language and language-confidence metadata. PR #60 preserves original audio duration, post-VAD duration and provider word count. These diagnostics help explain failures; they do not improve ASR recognition by themselves or guarantee transcript accuracy.
- PRs #59 and #60 are merged to main. PR #60's main Docker E2E run 44152407718 completed SUCCESS with 48/48 steps, including Bangla/English video-generation smoke flows and live Render health. This smoke environment had no Cloudflare credentials and disabled external AI image/planner calls, so it did not validate a real Whisper response, real-provider word timestamps, semantic vision review, or final publication eligibility.
- The audit document records the verified PR history and limitations: [PROJECT_AUDIT.md](PROJECT_AUDIT.md).

### Remaining acceptance work (current)

1. When Cloudflare's free allocation is available, run the same 43-word Bengali narration and inspect the actual Whisper transcript preview, detected language/confidence, duration, VAD duration and word count. Do not infer success from synthetic tests.
2. Verify provider-supplied word-level timestamps for every spoken word. Never synthesize exact word times from sentence pauses; keep publication blocked when timestamps are missing or incomplete.
3. Re-test the actual final scene images and their descriptions for relevance and visual variety. The previous 26.5-second user video used nine AI-generated desk/learning images with repetitive compositions; automated smoke tests without vision credentials cannot establish visual quality.
4. Confirm all subtitle frames and active words pass OCR on a real generated video, not only synthetic rendered frames.
5. Complete Android v0.3.225 installation/update and TalkBack acceptance on the user's phone. No physical-device or screen-off test is currently verified. Backend-only PRs #59/#60 did not create a new APK.
6. Continue to disclose Render Free limitations: in-memory job state and ephemeral output files can be lost on restart/spin-down. Do not add paid storage or services without explicit approval.

No paid provider, new secret, expected-script Whisper prompt, weakened quality threshold, or weakened fail-closed publication gate was introduced by PRs #52–#60.


### Latest E2E verification — 2026-11-18
- PR #61 is merged and live on Render. Main Docker E2E run [44154042847](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/44154042847) succeeded: Docker build, 162 backend unit tests, multilingual generation smoke checks, regression checks, and live Render /health all passed.
- Important distinction: the generated Bengali, English, and mixed smoke videos were all correctly blocked from sharing/download because audio transcription/word-level timestamps and semantic vision review were unavailable. Bengali OCR was 7/7; English OCR was 0/8; mixed OCR was 5/10. This E2E success is not evidence of publication quality.
- The smoke container intentionally had no Cloudflare credentials, so Whisper RuntimeError here means provider verification was unavailable in this test environment; it does not establish current Cloudflare quota exhaustion.
- Next engineering priorities: (1) diagnose English/mixed active-word OCR crop and caption rendering without weakening exact-match checks; (2) run a real Whisper test when free Cloudflare allocation/credentials are available and verify actual per-word timestamps; (3) enable/verify real semantic image review and scene relevance; (4) re-run the user's exact 43-word Bengali test on a real generated video; (5) complete physical Android v0.3.225 update and TalkBack acceptance.
- No new APK was produced by PR #61. Keep the fail-closed publication gate unchanged. Render Free still has in-memory jobs and ephemeral output files.


### PR #62 E2E result and English OCR diagnosis — 2026-11-18
- PR #62 is merged and live on Render. Full E2E run [44155270569](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/44155270569) passed its workflow, including backend unit tests, Bengali/English/mixed video generation smoke, provider regressions, and live Render health.
- The live-video OCR measurements show the English fix is not complete: English 0/8, mixed 5/10. Do not claim the English OCR issue is fixed.
- All smoke videos were correctly blocked from sharing and download. Whisper transcription/word timestamps and semantic vision review were unavailable in the no-Cloudflare-credentials smoke environment; this does not establish current Cloudflare quota status.
- PR #63 is merged and live on Render. CI run [44157551866](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/44157551866) passed 169 tests. It adds script-aware caption font selection (Bengali font for Bengali tokens; DejaVu Sans for Latin-only tokens) plus a real-Tesseract synthetic diagnostic. That diagnostic recognized 6/6 English words in isolated/raw crops, but only 2/6 in full panels.
- This is not yet full-video acceptance: the synthetic test manually draws the English caption rather than exercising production `make_caption_frames`; no post-PR63 multilingual Docker E2E has been verified. Mixed-script single-token font coverage also remains to be tested.
- Next priorities: add an integration test using production caption frame generation for English, Bengali and mixed scripts; OCR the actual active-word frames and verify exact tokens; then rerun multilingual E2E and the user's exact 43-word Bengali sample. Verify real free Cloudflare Whisper word timestamps and semantic vision review when credentials/allocation are available. Preserve exact-token matching and fail-closed publication. Android APK remains v0.3.225; no APK change from PR #63.
