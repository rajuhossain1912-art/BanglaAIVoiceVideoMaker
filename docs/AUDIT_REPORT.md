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

## ফলাফলের অর্থ

- **success / সফল:** সংশ্লিষ্ট GitHub workflow/job/step সফলভাবে শেষ হয়েছে।
- **failure / ব্যর্থ:** workflow/job/step ব্যর্থ হয়েছে; ব্যর্থতার রেকর্ড অক্ষত থাকবে।
- **cancelled / বাতিল:** কাজটি সম্পন্ন হয়নি।
- **queued / in_progress:** এখনো চূড়ান্ত ফল নয়।
- **not_verified / যাচাই হয়নি:** প্রয়োজনীয় live বা device evidence পাওয়া যায়নি।

**নিরাপত্তা নীতি:** কোনো API token, password, keystore, signing secret বা ব্যক্তিগত voice sample এই রিপোর্টে লেখা হবে না।
