# Bangla AI Voice Video Maker — স্বয়ংক্রিয় অডিট রিপোর্ট

**রিপোর্টের ধরন:** স্থায়ী কাজের ইতিহাস ও পরীক্ষার রেজিস্টার  
**প্রকল্প:** [BanglaAIVoiceVideoMaker](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker)  
**মূল অডিট ও বিস্তারিত প্রযুক্তিগত ইতিহাস:** [docs/PROJECT_AUDIT.md](PROJECT_AUDIT.md)  
**সম্পূর্ণ commit history:** https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commits/main/  
**স্বয়ংক্রিয় রেকর্ড শুরু:** ২০২৬-১১-১৪

## কীভাবে এই রিপোর্ট আপডেট হবে

GitHub-এর `main` branch-এ নতুন commit হলে এই রিপোর্টে পরিবর্তনের সময়, commit, বার্তা ও পরিবর্তিত ফাইলের তালিকা যোগ হবে। Backend end-to-end smoke test এবং Android APK workflow শেষ হলে তাদের চূড়ান্ত অবস্থা, run link, commit এবং job/step-এর ফলও যোগ হবে। সফল, ব্যর্থ, বাতিল—সব ফল সংরক্ষিত হবে। পুরোনো রেকর্ড মুছে ফেলা বা আগের ফলকে সফল হিসেবে বদলে দেওয়া হবে না।

এই রিপোর্টে কেবল যাচাইযোগ্য GitHub event ও workflow ফল লেখা হবে। কোনো service-এর live status বা deployment outcome প্রমাণ ছাড়া সফল বলা হবে না। ChatGPT কথোপকথনে হওয়া কিন্তু repository/CI-তে নথিভুক্ত না হওয়া আলোচনা স্বয়ংক্রিয়ভাবে ধরা পড়ে না; বাস্তব কাজের commit message ও test result-এ কাজের পরিচয় রাখতে হবে।

## প্রকল্পের শুরু থেকে পূর্ববর্তী কাজের সারসংক্ষেপ

GitHub commit history অনুযায়ী প্রকল্পের প্রথম commit ২০২৬-১০-১৫। বিস্তারিত পর্যায়ভিত্তিক বিবরণ, AI model/provider তালিকা, architecture, publication gate, ঝুঁকি ও অসমাপ্ত কাজ [মূল অডিট রিপোর্টে](PROJECT_AUDIT.md) সংরক্ষিত আছে।

- **১৫–১৭ অক্টোবর:** Android অ্যাপ, FastAPI backend, Render/FFmpeg ভিত্তি, বাংলা-ইংরেজি ভিডিও smoke test এবং প্রাথমিক voice-consent flow।
- **১৭–১৯ অক্টোবর:** TTS fallback, scene splitting, ছবি সংগ্রহ/তৈরি, zoom/pan এবং subtitle timing।
- **২০–২২ অক্টোবর:** TalkBack-উপযোগী quality report, dark/blank frame ও repeated image শনাক্তকরণ।
- **২৯ অক্টোবর–৩ নভেম্বর:** voice cloning flow, recording preview/consent, screen-off processing, settings ও job management।
- **৪–৯ নভেম্বর:** Cloudflare AI Brain/visual planning, image review, image recovery, provider fallback এবং audio transcription।
- **১১–১৩ নভেম্বর:** ভাষা ও বিষয় বিশ্লেষণ, research context, strict publication gate, word timestamp integrity, OCR ও duplicate-image fail-closed checks।

## সর্বশেষ যাচাইকৃত ভিত্তি অবস্থা — ২০২৬-১১-১৪

| বিষয় | যাচাইকৃত ফল |
|---|---|
| Backend CI run #454 | **সফল** — video-smoke-test job এবং health, tests, Bengali/English E2E ও publication-gate checks |
| Android APK workflow #222 | **সফল** — signing key, build, app identity/version, signature, single APK এবং release publish |
| সর্বশেষ যাচাইকৃত APK | **v0.3.222**, একটি APK asset |
| APK release | https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/releases/tag/v0.3.222 |
| Backend CI run | https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/43279949106 |
| Android build run | https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/43080180005 |
| Render deployment | সর্বশেষ audit update-এর পর queued deployment ছিল; পরবর্তী চূড়ান্ত অবস্থা যাচাই না হওয়া পর্যন্ত **অমীমাংসিত** |
| Render health / metrics | health ও metrics-এর পূর্ণ live প্রমাণ পাওয়া যায়নি; অনুপস্থিত metrics-কে শূন্য বা healthy ধরা হয়নি |
| বাস্তব Android ফোনে TalkBack পরীক্ষা | ব্যবহারকারীর ফোনে পরীক্ষা ছাড়া **যাচাই হয়নি** |

## চলমান অমীমাংসিত বিষয়

1. ১২টির বেশি scene হলে semantic review সীমা ও strict publication gate-এর মধ্যে অসামঞ্জস্য।
2. Topic graphic fallback-এর নিরাপদ verification পদ্ধতি।
3. Render health-check configuration এবং deployment completion-এর live verification।
4. Provider credential/quota/connectivity—secret value না পড়ে শুধু নিরাপদ presence/health evidence দিয়ে যাচাই।
5. বাস্তব ফোনে TalkBack, voice recording, screen-off processing, update install এবং video download পরীক্ষা।

## স্বয়ংক্রিয় কাজের রেকর্ড

নিচে নতুন commit ও workflow ফল সময়ক্রমে যোগ হবে। রিপোর্ট তৈরির আগের কাজের পূর্ণ ইতিহাস উপরের সারাংশ, মূল অডিট এবং Git commit history-তে আছে।

<!-- AUTO_LOG_START -->
- ২০২৬-১১-১৪: স্বয়ংক্রিয় অডিট রেজিস্টার স্থাপনের প্রাথমিক রেকর্ড। এই তারিখের পর GitHub push ও নির্দিষ্ট CI workflow-এর প্রতিটি completed ফল নিচে যুক্ত হবে।

### Source update — 2026-11-14T17:05:56.879Z
- Branch: `main`
- Push range: `dbe30e6a7f2e01900a9238006956d86426007c0e` → `a0035e669462c31645b3364d7a3007acbe78e0b8`
- Pushed by: rajuhossain1912-art
- Commit: [a0035e669462](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/a0035e669462c31645b3364d7a3007acbe78e0b8) — ci: enable audit workflow self-test and manual dispatch
- Changed files:
- Result: **push recorded**; this is not a test or deployment success claim.


### Source update — 2026-11-14T17:06:17.830Z
- Branch: `main`
- Push range: `d072f0ca8fad9c6e2bc8987389ce6a8d23fcb81e` → `5e3026a7ea3d5be6431ea4a895a3e7fe2462cb45`
- Pushed by: rajuhossain1912-art
- Commit: [5e3026a7ea3d](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/5e3026a7ea3d5be6431ea4a895a3e7fe2462cb45) — ci: capture changed files when push payload omits commit list
- Changed files:
- Result: **push recorded**; this is not a test or deployment success claim.


### Source update — 2026-11-14T17:06:54.943Z
- Branch: `main`
- Push range: `359c61721805a627f337c25c59b49510f8fe68b5` → `5820fcb76ce05b4b691de3514b918d17519a78a6`
- Pushed by: rajuhossain1912-art
- Commit: [5820fcb76ce0](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/5820fcb76ce05b4b691de3514b918d17519a78a6) — ci: keep audit log on separate branch to avoid API redeploys
- Changed files:
- Result: **push recorded**; this is not a test or deployment success claim.


### Source update — 2026-11-14T17:07:22.287Z
- Branch: `main`
- Push range: `5820fcb76ce05b4b691de3514b918d17519a78a6` → `ae78b9d34d86ee5bbacfcf5d3953c874bb480547`
- Pushed by: rajuhossain1912-art
- Commit: [ae78b9d34d86](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/ae78b9d34d86ee5bbacfcf5d3953c874bb480547) — ci: resolve changed file lists from commit metadata
- Changed files:
  - `.github/workflows/audit-register.yml`
- Result: **push recorded**; this is not a test or deployment success claim.


### Source update — 2026-11-14T17:11:35.648Z
- Branch: `main`
- Push range: `ae78b9d34d86ee5bbacfcf5d3953c874bb480547` → `e788e5f7df1950b1ce0f38d097d5a27472fdd69d`
- Pushed by: rajuhossain1912-art
- Commit: [e788e5f7df19](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/e788e5f7df1950b1ce0f38d097d5a27472fdd69d) — ci: verify live Render health in backend smoke test
- Changed files:
  - `.github/workflows/backend-smoke.yml`
- Result: **push recorded**; this is not a test or deployment success claim.


### Workflow result — 2026-11-14T17:14:13.315Z
- Workflow: **Backend end-to-end smoke test**
- Final result: **সফল (success)**
- Run: [#455](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/43619754340)
- Commit: [e788e5f7df19](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/e788e5f7df1950b1ce0f38d097d5a27472fdd69d)
- Trigger: push; branch: main; actor: rajuhossain1912-art
- Job **video-smoke-test**: success
  - Step 1. Set up job: success
  - Step 2. Checkout source: success
  - Step 3. Build backend container: success
  - Step 4. Run backend unit tests: success
  - Step 5. Start backend: success
  - Step 6. Wait for health endpoint: success
  - Step 7. Verify Bengali and English Tesseract language packs: success
  - Step 8. Verify voice chat reuses the existing AI token: success
  - Step 9. Verify Bangla and English audio transcript comparison: success
  - Step 10. Verify subtitle timing diagnostics never claim word-level ASR alignment: success
  - Step 11. Verify bounded licensed image search cache: success
  - Step 12. Verify licensed photo searches include subject synonyms: success
  - Step 13. Verify image-search keywords prioritize scene subjects over camera wording: success
  - Step 14. Verify Openverse reuses successful cached provider results: success
  - Step 15. Verify sampled scene timeline mapping: success
  - Step 16. Verify duration-based visual scene count has no fixed ceiling: success
  - Step 17. Verify forced topic graphic never calls image providers: success
  - Step 18. Verify rejected AI photos can recover with licensed contextual photos: success
  - Step 19. Verify scene-aware visual planning: success
  - Step 20. Verify sentence-aware scene splitting: success
  - Step 21. Verify Bengali visual keyword inflections: success
  - Step 22. Verify storyboard prompts improve licensed image search terms: success
  - Step 23. Verify licensed image search broadens zero-result queries: success
  - Step 24. Verify Openverse continues after a failed photo download: success
  - Step 25. Verify Wikimedia continues after a failed photo download: success
  - Step 26. Verify licensed image search checks a broad candidate pool: success
  - Step 27. Verify licensed photo candidates are ranked by storyboard relevance: success
  - Step 28. Verify licensed photo relevance uses provider subject tags: success
  - Step 29. Verify Wikimedia photo relevance uses category metadata: success
  - Step 30. Verify voice cloning requires explicit consent: success
  - Step 31. Generate Bangla and English videos end to end: success
  - Step 32. Verify image provider cooldown classification and Pollinations rate-limit handling: success
  - Step 33. Verify Cloudflare image response decoding: success
  - Step 34. Verify Cloudflare image models receive supported inputs: success
  - Step 35. Verify blank image providers are rejected before selection: success
  - Step 36. Verify every image provider rejects blank output: success
  - Step 37. Verify vision review response parsing: success
  - Step 38. Verify storyboard context crosses long-script batch boundaries: success
  - Step 39. Verify visual planner parses global scene numbers in later batches: success
  - Step 40. Verify independent reviewer parses global scene numbers: success
  - Step 41. Verify storyboard reviewer preserves neighboring narration context: success
  - Step 42. Verify repeated images request a distinct photo composition: success
  - Step 43. Verify vision review skips local fallback graphics: success
  - Step 44. Verify duplicate replacement photos receive sampled semantic review: success
  - Step 45. Verify licensed recovery reports its verified semantic result: success
  - Step 46. Verify final visual audit follows accepted duplicate replacement: success
  - Step 47. Show backend logs on failure: skipped
  - Step 48. Verify live Render production health endpoint: success
  - Step 96. Post Checkout source: success
  - Step 97. Complete job: success


### Source update — 2026-11-14T17:40:10.806Z
- Branch: `main`
- Push range: `e788e5f7df1950b1ce0f38d097d5a27472fdd69d` → `68ab8ddc122bccdf2d03dd05644c4de432d1bb79`
- Pushed by: rajuhossain1912-art
- Commit: [68ab8ddc122b](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/68ab8ddc122bccdf2d03dd05644c4de432d1bb79) — fix: review every final photo scene by default
- Changed files:
  - `backend/app.py`
  - `backend/tests/test_scene_graphic_variation.py`
  - `docs/PRODUCT_PLAN.md`
  - `docs/PROJECT_AUDIT.md`
- Result: **push recorded**; this is not a test or deployment success claim.


### Workflow result — 2026-11-14T17:42:58.268Z
- Workflow: **Backend end-to-end smoke test**
- Final result: **সফল (success)**
- Run: [#456](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/actions/runs/43622346619)
- Commit: [68ab8ddc122b](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/68ab8ddc122bccdf2d03dd05644c4de432d1bb79)
- Trigger: push; branch: main; actor: rajuhossain1912-art
- Job **video-smoke-test**: success
  - Step 1. Set up job: success
  - Step 2. Checkout source: success
  - Step 3. Build backend container: success
  - Step 4. Run backend unit tests: success
  - Step 5. Start backend: success
  - Step 6. Wait for health endpoint: success
  - Step 7. Verify Bengali and English Tesseract language packs: success
  - Step 8. Verify voice chat reuses the existing AI token: success
  - Step 9. Verify Bangla and English audio transcript comparison: success
  - Step 10. Verify subtitle timing diagnostics never claim word-level ASR alignment: success
  - Step 11. Verify bounded licensed image search cache: success
  - Step 12. Verify licensed photo searches include subject synonyms: success
  - Step 13. Verify image-search keywords prioritize scene subjects over camera wording: success
  - Step 14. Verify Openverse reuses successful cached provider results: success
  - Step 15. Verify sampled scene timeline mapping: success
  - Step 16. Verify duration-based visual scene count has no fixed ceiling: success
  - Step 17. Verify forced topic graphic never calls image providers: success
  - Step 18. Verify rejected AI photos can recover with licensed contextual photos: success
  - Step 19. Verify scene-aware visual planning: success
  - Step 20. Verify sentence-aware scene splitting: success
  - Step 21. Verify Bengali visual keyword inflections: success
  - Step 22. Verify storyboard prompts improve licensed image search terms: success
  - Step 23. Verify licensed image search broadens zero-result queries: success
  - Step 24. Verify Openverse continues after a failed photo download: success
  - Step 25. Verify Wikimedia continues after a failed photo download: success
  - Step 26. Verify licensed image search checks a broad candidate pool: success
  - Step 27. Verify licensed photo candidates are ranked by storyboard relevance: success
  - Step 28. Verify licensed photo relevance uses provider subject tags: success
  - Step 29. Verify Wikimedia photo relevance uses category metadata: success
  - Step 30. Verify voice cloning requires explicit consent: success
  - Step 31. Generate Bangla and English videos end to end: success
  - Step 32. Verify image provider cooldown classification and Pollinations rate-limit handling: success
  - Step 33. Verify Cloudflare image response decoding: success
  - Step 34. Verify Cloudflare image models receive supported inputs: success
  - Step 35. Verify blank image providers are rejected before selection: success
  - Step 36. Verify every image provider rejects blank output: success
  - Step 37. Verify vision review response parsing: success
  - Step 38. Verify storyboard context crosses long-script batch boundaries: success
  - Step 39. Verify visual planner parses global scene numbers in later batches: success
  - Step 40. Verify independent reviewer parses global scene numbers: success
  - Step 41. Verify storyboard reviewer preserves neighboring narration context: success
  - Step 42. Verify repeated images request a distinct photo composition: success
  - Step 43. Verify vision review skips local fallback graphics: success
  - Step 44. Verify duplicate replacement photos receive sampled semantic review: success
  - Step 45. Verify licensed recovery reports its verified semantic result: success
  - Step 46. Verify final visual audit follows accepted duplicate replacement: success
  - Step 47. Show backend logs on failure: skipped
  - Step 48. Verify live Render production health endpoint: success
  - Step 96. Post Checkout source: success
  - Step 97. Complete job: success

<!-- AUTO_LOG_END -->


## পূর্ণাঙ্গ সরাসরি অডিট — ২০২৬-১১-১৬

### Repository ও source inventory
- GitHub repository: public; default branch: main; repository read/write permission confirmed for the connected integration.
- Latest main commit inspected: 68ab8ddc122bccdf2d03dd05644c4de432d1bb79 — "fix: review every final photo scene by default" (2026-11-14).
- Recursive source tree inspected: Android Jetpack Compose app, FastAPI backend, Dockerfile, Render Blueprint, GitHub Actions workflows, backend tests, product plan and audit documentation.
- Backend source inspected: backend/app.py (4,772 lines); Android MainActivity.kt (1,230 lines); VideoWorkService.kt; Android manifest/build configuration; Dockerfile and backend requirements.

### Latest verified backend CI and production deployment
- Backend workflow run #456, run ID 43622346619, commit 68ab8ddc122bccdf2d03dd05644c4de432d1bb79: **success**.
- Job video-smoke-test: all substantive steps succeeded, including Docker build, backend unit tests, local /health, Bengali/English Tesseract, Bangla/English E2E video generation, scene count, topic graphic routing, photo recovery, visual planner, duplicate replacement review, and live Render production health endpoint. Failure-log step was skipped as expected.
- Render service bangla-ai-voice-video-maker-api, service ID srv-db7u1d49v7es73ctjqj0: latest deploy dep-dbs9pth5efls73eh7ijg for commit 68ab8ddc122bccdf2d03dd05644c4de432d1bb79 is **live**; build and deploy events succeeded on 2026-11-14.
- Render service metadata still reports an empty healthCheckPath while render.yaml specifies /health. CI's explicit live production health endpoint check succeeded, but configuration drift remains and should be reconciled through the existing service/Blueprint without creating a duplicate service.
- Render metrics for CPU, memory, HTTP requests and latency returned empty series in the inspected window. This is **unavailable evidence**, not zero use or proof of failure/health. No application/request error logs were returned for the inspected recent window.

### Android release and UI
- Latest published APK remains v0.3.222, target commit 63cf1f752782c146f3e9a2fe8e8281abe1b5ba49, one APK asset (10,736,616 bytes); signing, package identity, version, artifact upload and release publication steps passed in Android workflow #222.
- MainActivity.kt last changed 2026-11-11 (commit ea98fe90d23a2e38ec3fb879a3c9d112a4258033); later main-branch commits inspected were backend/CI/audit changes. No newer Android build is currently indicated by an app-source change.
- Real NEXG N28 installation/update, TalkBack interaction, recording, screen-off execution and downloaded-video review remain **not verified on the user's physical device**.

### Database, storage and job lifecycle
- Render account inventory: **no PostgreSQL instances and no Key Value/Redis instances** found in the workspace.
- Backend uses in-memory JOBS state and /tmp/bangla-video-jobs; files are ephemeral and jobs are not recoverable after a process restart. Retention cleanup is configured (default 24 hours), but it is not durable storage.
- Android starts a foreground VideoWorkService and holds a bounded wake lock; job submission/status polling remains in a rememberCoroutineScope inside MainActivity. There is no WorkManager/persisted job-resume implementation in the inspected app dependencies/source. Activity/process death can therefore lose client polling state even if server work continues.

### AI/provider and voice findings
- Source includes Cloudflare Workers AI for language planning/chat, image generation and vision review; Whisper for speech transcription; Pollinations and Hugging Face Spaces for image/voice fallbacks; Openverse/Wikimedia for licensed photo fallback; gTTS and eSpeak NG for narration fallback; Tesseract ben/eng for subtitle OCR.
- Code presence and mocked CI coverage do not prove current external provider credentials, quotas, queue availability or output quality. Environment secret values were not accessed; live provider connectivity/quota remains unverified.
- Voice sample is stored locally on device and sent to external Hugging Face demo when clone is requested. The current integration does not persist a private reusable cloned model/Voice ID. Provider retention is outside app control.

### Remaining high-priority gaps (do not weaken safety gates)
1. Local topic-graphic fallback remains explicitly unreviewed by the photographic vision reviewer; strict publication gate correctly blocks it. A reliable graphic-specific verification path is still needed.
2. Render service healthCheckPath configuration drift (/health in Blueprint, empty in live service metadata) remains unresolved despite successful explicit production health check in CI.
3. In-memory job state and ephemeral Render files mean no durable resume/recovery after server restart; no database or persistent disk is attached.
4. Android job polling is Activity coroutine scoped and not persisted; WorkManager/resume after process death is a future reliability improvement.
5. External AI provider live credential/quota/quality checks are not independently verified.
6. Permanent private voice clone profile is not provided by the current free external demo integrations; do not describe the saved sample as a persistent clone.
7. Physical-device accessibility and installation/update tests remain pending.

### Safety and change policy
- Keep publication gate fail-closed: never mark unreviewed topic graphics, estimated word timestamps, missing OCR or unverified scene matches as shareable.
- Do not provision paid infrastructure or change secrets without explicit authorization.
- Before implementing persistence, compare free options and data/privacy implications; do not silently upload personal voice samples to a new provider.
- Before any Android release, preserve applicationId and pinned signing certificate; only build a new APK when app source/build changes or the user requests it.

## ফলাফলের অর্থ

- **success / সফল:** সংশ্লিষ্ট GitHub workflow/job/step সফলভাবে শেষ হয়েছে।
- **failure / ব্যর্থ:** workflow/job/step ব্যর্থ হয়েছে; ব্যর্থতার রেকর্ড অক্ষত থাকবে।
- **cancelled / বাতিল:** কাজটি সম্পন্ন হয়নি।
- **queued / in_progress:** এখনো চূড়ান্ত ফল নয়।
- **not_verified / যাচাই হয়নি:** প্রয়োজনীয় live বা device evidence পাওয়া যায়নি।

**নিরাপত্তা নীতি:** কোনো API token, password, keystore, signing secret বা ব্যক্তিগত voice sample এই রিপোর্টে লেখা হবে না।


## পরবর্তী যাচাই — ২০২৬-১১-১৬

### Render Health Check সংশোধন
- ব্যবহারকারী Render Dashboard-এর Health Check Path-এ `/health` দিয়ে Save Changes করেছেন।
- Live Render service metadata পুনরায় পরীক্ষা করে `serviceDetails.healthCheckPath=/health` পাওয়া গেছে।
- Render event history-তে health check path পরিবর্তনের জন্য নতুন deployment শুরু ও শেষ—দুটিই পাওয়া গেছে।
- নতুন deployment ID: `dep-dbt8sr7f3r2c73c9h96g`; চূড়ান্ত অবস্থা: **succeeded**।
- এটি configuration ও deployment সফল হওয়ার প্রমাণ; একে Android device acceptance test হিসেবে গণ্য করা যাবে না।

### Semantic scene review বিষয়ে কোড-ভিত্তিক পুনঃযাচাই
- `backend/app.py`-এর বর্তমান main branch-এ `IMAGE_SEMANTIC_REVIEW_MAX_SCENES`-এর default `0`; `_semantic_review_indices`-এ এই default সব visual scene review করার উদ্দেশ্যে ব্যবহৃত হয়।
- পরিবেশে positive limit সেট করা হলে সীমিত scene review হতে পারে; publication gate তখনও প্রতিটি final scene-এর `matched` বা `retry_matched` status বাধ্যতামূলক করে।
- অতএব আগের অডিটের “default 12 scenes” বক্তব্য বর্তমান source-এর সঙ্গে মেলে না; সেটি পুরোনো/অপ্রচলিত তথ্য হিসেবে সংশোধিত হলো।
- Local `topic_graphic` এখনো photographic vision reviewer দিয়ে যাচাই করা হয় না এবং publication gate-এ pass করে না। এই নিরাপত্তা বাধা অক্ষত রাখা হয়েছে।

### এই ধাপে পরিবর্তনের সীমা
- এই ধাপে production application source code পরিবর্তন করা হয়নি।
- Audit branch-এ যাচাইযোগ্য live configuration এবং source-code finding নথিভুক্ত করা হয়েছে।
- Android APK পুনর্নির্মাণ প্রয়োজন হয়নি; Android app source পরিবর্তন করা হয়নি।
- পরবর্তী কাজ: topic graphic-এর জন্য আলাদা, উপযুক্ত ও fail-closed verification; Render ephemeral job storage ও Android process-death resume—এগুলোর নিরাপদ free-tier design review।


## কাজ পুনরুদ্ধার ও Android ব্যাকগ্রাউন্ড অগ্রগতি — ২০২৬-১১-১৬

### Backend job lifecycle — সরাসরি source inspection
- `backend/app.py`-এ job registry হলো process-local Python dictionary `JOBS = {}`।
- ভিডিওর ফাইল `WORK_DIR`-এ রাখা হয়; default `/tmp/bangla-video-jobs`। এটি Render-এর ephemeral filesystem; durable database/object storage নয়।
- `POST /api/jobs` অনুরোধ গ্রহণ করে `threading.Thread(target=render, ..., daemon=True).start()` দিয়ে কাজ চালায়।
- `GET /api/jobs/{job_id}` process-local `JOBS`-এ job না পেলে 404 দেয় এবং স্পষ্টভাবে জানায় সার্ভার restart হলে অস্থায়ী কাজের তথ্য মুছে যেতে পারে।
- ফলে process restart/deploy/crash হলে চলমান daemon render thread থেমে যায়, job state memory থেকে হারায় এবং ওই job-এর ফল নির্ভরযোগ্যভাবে পুনরুদ্ধার করা যায় না। শুধু JSON metadata লিখলেই সমাধান হবে না; rendering inputs, uploaded audio, intermediate files, output এবং worker lease/recovery-ও durable হতে হবে।

### Android foreground service — সরাসরি source inspection
- `VideoWorkService.kt` foreground notification ও সর্বোচ্চ ৪ ঘণ্টার bounded partial wake lock দেয়; এটি CPU-কে screen-off অবস্থায় চলতে সহায়তা করে।
- কিন্তু সার্ভারে job submit ও polling loop `MainActivity.kt`-এর Compose `rememberCoroutineScope().launch`-এর ভিতরে চলে; Service নিজে job ID সংরক্ষণ, network polling, retry বা process-death recovery করে না।
- `VideoWorkService`-এর `START_NOT_STICKY`; Android process/service বন্ধ হলে কাজ নিজে থেকে পুনরায় শুরু হওয়ার নিশ্চয়তা নেই।
- `WorkManager` বা DataStore job recovery ব্যবহার বর্তমান MainActivity source-এ পাওয়া যায়নি।
- অতএব notification/wake lock থাকা মানেই অ্যাপ বন্ধ, Activity destroy বা OS process kill হলেও ভিডিও কাজ ও অগ্রগতি টিকে থাকবে—এমন নিশ্চয়তা নয়।

### নিরাপদ পরবর্তী নকশা ও সিদ্ধান্ত
- Backend recovery-এর জন্য durable job store + durable input/output storage + restart-safe worker orchestration প্রয়োজন। বর্তমানে Render workspace-এ PostgreSQL/Key Value নেই এবং ব্যবহারকারীর শর্ত free-only; তাই কোনো paid DB, paid disk, paid API বা অপ্রমাণিত free-tier object store চালু করা হয়নি।
- Android-এর জন্য persistent WorkManager worker, encrypted/local job metadata এবং server job ID পুনরায় poll করার flow প্রয়োজন; তবে backend job ID restart-এর পর টিকে না থাকলে শুধু Android পরিবর্তন যথেষ্ট নয়।
- এই ধাপে production source code পরিবর্তন করা হয়নি; ভুল নিরাপত্তা-আশ্বাস এড়াতে architecture limitation নথিভুক্ত করা হয়েছে।
- Manual action এখন প্রয়োজন নেই। আগে free-only durable backend storage/orchestration-এর বাস্তব সীমা যাচাই করে তবেই implementation ও test plan করা হবে।


### Restart-recovery test coverage inventory
- `backend/tests`-এ বর্তমানে scene graphic variation, scene image similarity, scene interval diagnostics, voice chat এবং voice clone—এই পাঁচটি test module পাওয়া গেছে।
- Job registry persistence, process restart recovery, daemon worker interruption, Android Activity destruction এবং WorkManager recovery-এর dedicated test module পাওয়া যায়নি।
- এই ঘাটতি ভবিষ্যৎ durable job implementation-এর আগে regression test হিসেবে যোগ করতে হবে।


### Free-tier storage options — official provider documentation checked
- Render documents that Free web services have ephemeral filesystems; local files, including SQLite databases, are lost on redeploy, restart, or spin-down. Free web services cannot attach persistent disks. Free Render Postgres expires after 30 days; Free Key Value is memory-only and may lose data on restart. Therefore neither is a safe durable job store for this production requirement. Sources: https://render.com/docs/free and https://render.com/docs/disks
- Cloudflare R2 official pricing currently lists a Standard storage free allowance of 10 GB-month, 1 million Class A operations and 10 million Class B operations per month, with Internet egress free. Source: https://developers.cloudflare.com/r2/pricing/
- Cloudflare D1 official FAQ confirms a permanent Workers Free plan for prototyping/experimentation and that daily/storage limits cause query failures until limits reset or data is cleaned up. Source: https://developers.cloudflare.com/d1/reference/faq/
- Candidate architecture for a free-tier trial: D1 for durable job metadata/state and R2 for uploaded inputs, intermediate assets and completed MP4; worker orchestration must also be restart-safe and idempotent. This is a candidate only, not yet implemented or proven suitable for this workload.
- Important cost/privacy safeguards before enabling: verify actual Cloudflare account billing/plan and required API permissions; enforce per-user/job quotas, maximum file sizes, TTL cleanup, private object access, signed/short-lived download URLs, and never log voice samples or secrets. Free allowances are limits, not a guarantee of unlimited free operation.
- No Cloudflare resources were created and no credentials or billing settings were changed.

### Render health-check configuration — ২০২৬-১১-১৬
- ব্যবহারকারীর নির্দেশিত Dashboard পরিবর্তনের পর live service metadata পুনরায় পরীক্ষা করা হয়েছে। `serviceDetails.healthCheckPath` এখন `/health`; আগের খালি মান আর নেই।
- Render event `evt-dbt8sr5uproc73cpdfj0` নিশ্চিত করে পরিবর্তনের কারণে deploy শুরু হয়েছে; event `evt-dbt8t3h9aqoc73aitlig`-এ deploy status `succeeded`।
- সর্বশেষ deploy `dep-dbt8sr7f3r2c73c9h96g` status `live`; commit `68ab8ddc122bccdf2d03dd05644c4de432d1bb79` অপরিবর্তিত। এটি health-check configuration update, নতুন application source build নয়।
- Live service এখনো Free plan, ১টি instance, auto-deploy enabled এবং main branch-এ যুক্ত।
- Android persistence ও backend restart recovery-এর source-level সীমাবদ্ধতা আগের অংশে নথিভুক্ত; এই পর্যায়ে সেগুলো production-এ পরিবর্তন করা হয়নি।


## Publication gate ও live log পুনঃযাচাই — ২০২৬-১১-১৭

### সরাসরি কোড পরীক্ষা
- `_publication_gate_decision`-এ প্রতিটি চূড়ান্ত দৃশ্যের status অবশ্যই `matched` বা `retry_matched` হতে হবে; একটি `topic_graphic_unreviewed`, `not_reviewed`, `unavailable` বা অনুপস্থিত scene audit থাকলেও share বন্ধ থাকে।
- অডিও যাচাইয়ে status `matched`, `missing_tokens=0` এবং `extra_tokens=0` বাধ্যতামূলক।
- সাবটাইটেল যাচাইয়ে প্রতিটি script word-এর ASR timestamp, timing integrity এবং rendered subtitle OCR pass—সবগুলো বাধ্যতামূলক।
- ভিডিও stream, audio stream, duration, audio signal এবং visual sampling-এর প্রযুক্তিগত শর্তও pass করতে হয়।
- ফলে বর্তমান gate ইচ্ছাকৃতভাবে কঠোর; শুধু MP4 তৈরি হওয়া বা প্রাথমিক technical check সফল হওয়া মানেই প্রকাশের অনুমতি নয়।

### Test coverage gap
- বিদ্যমান `backend/tests/test_scene_graphic_variation.py`-এ semantic scene selection, image source, image recovery ও provider failure-এর test আছে।
- এই test file-এ `_publication_gate_decision`-এর সরাসরি unit test পাওয়া যায়নি। বিশেষ করে topic graphic/unreviewed scene, missing scene audit, audio mismatch, missing word timestamp এবং OCR failure-এর প্রত্যেকটি আলাদাভাবে gate বন্ধ রাখে—এমন regression test যোগ করা প্রয়োজন।
- এটি test coverage-এর ঘাটতি; বর্তমান production gate দুর্বল বা bypass হয়েছে—এমন প্রমাণ নয়।
- নিরাপত্তা যাচাইয়ের আগে test-only পরিবর্তনও production branch-এ push করা হয়নি, কারণ Render auto-deploy main branch-এর commit অনুসরণ করে।

### Render live log পর্যবেক্ষণ
- Render-এর সাম্প্রতিক ফেরত দেওয়া log page-এ `GET /health` request-গুলো `200 OK` দেখা গেছে।
- ওই page-এ video-generation API request বা application error দেখা যায়নি। এটি কেবল ফেরত পাওয়া log window-এর পর্যবেক্ষণ; পুরো service history বা ব্যবহারকারীর app-এ video generation সফল হওয়ার প্রমাণ নয়।
- Service metadata-তে health path `/health`, Free plan, একটি instance এবং main branch auto-deploy—আগের যাচাইয়ের সঙ্গে মিলে গেছে।

### এই ধাপের পরিবর্তন
- Production source, Android app, secrets, Render resources বা Cloudflare resources পরিবর্তন করা হয়নি।
- এই ধাপের ফল audit branch-এ নথিভুক্ত; main branch-এ push বা production deployment ঘটানো হয়নি।
- পরবর্তী নিরাপদ কাজ: publication gate-এর dedicated regression tests তৈরি করে আলাদা test workflow-তে চালানো, যাতে test-only commit-এর কারণে Render production redeploy না হয়।
