# Bangla AI Voice Video Maker — প্রকল্প অডিট ও কাজের রেজিস্টার

সর্বশেষ পর্যালোচনা: ২০২৬-১১-১৩  
Repository: https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker  
পূর্ণ Git commit history: https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commits/main/  
Production API URL (repository configuration): https://bangla-ai-voice-video-maker-api.onrender.com

এই নথি Git commit history, বর্তমান source code, workflow, README এবং product plan দেখে তৈরি। এটি সার্ভারের গোপন environment value বা কোনো API token প্রকাশ করে না। GitHub code-এ provider integration থাকা মানেই provider account-এ বর্তমানে quota/credentials আছে বা live call সফল—এমন নয়।

## ১. প্রকল্পের প্রথম থেকে প্রধান কাজের ইতিহাস

GitHub-এ পাওয়া প্রথম commit ২০২৬-১০-১৫। নিচের তালিকা commit history-তে পাওয়া কাজগুলোকে পর্যায়ভিত্তিক সাজিয়েছে; একই কাজের implementation, test এবং documentation commit আলাদা আলাদা থাকতে পারে।

### ১৫–১৭ অক্টোবর: ভিত্তি তৈরি
- Android Jetpack Compose অ্যাপের প্রাথমিক কাঠামো ও APK workflow।
- FastAPI-ভিত্তিক অনলাইন ভিডিও API এবং Android থেকে API-তে সংযোগ।
- FFmpeg দিয়ে MP4 তৈরি, ffprobe দিয়ে ফাইল পরীক্ষা এবং backend smoke test।
- বাংলা ও ইংরেজি mixed text-এর ভিডিও পরীক্ষা।
- Render Free-তে কম RAM/CPU ব্যবহারের জন্য render pipeline সরলীকরণ।
- পরীক্ষামূলক voice cloning-এর consent flow, voice sample ফোনে private storage-এ রাখা, sample normalize ও remote clone শেষে temporary reference মুছে ফেলার ব্যবস্থা।

### ১৭–১৯ অক্টোবর: ভয়েস, ছবি ও সাবটাইটেল
- Google TTS এবং eSpeak NG fallback।
- বাক্য/দৃশ্যভিত্তিক scene splitting, vertical background image, zoom/pan motion।
- লাইসেন্স-ভিত্তিক Openverse/Wikimedia image search এবং topic graphic fallback।
- FLUX ও Z-Image-Turbo Hugging Face Space, Pollinations image generation fallback।
- Bangla visual keyword matching এবং technology topic-এ অপ্রাসঙ্গিক map image বাদ দেওয়ার নিয়ম।
- অডিওর silence/pause থেকে আনুমানিক sentence timing এবং word-highlight subtitle।
- ৩/৫/১০/১৫/২০ সেকেন্ডের scene interval ও timing offset।

### ২০–২২ অক্টোবর: TalkBack প্রতিবেদন ও visual diagnostics
- TalkBack-এ শোনার উপযোগী video quality report endpoint এবং Android report button।
- ভিডিওর dark/blank frame শনাক্তকরণ, scene order এবং repeated background শনাক্ত করার প্রাথমিক ব্যবস্থা।
- Render Free-তে rendering memory ও image timeline mapping সংশোধন।

### ২৯ অক্টোবর–৩ নভেম্বর: বড় অডিট ও ব্যবহারযোগ্যতা
- voice cloning-এর chunking, provider timeout, retry, progress এবং audio validation।
- ৩০০০ অক্ষরের voice-clone input সীমা; Bangla/English sentence language routing।
- recording preview, explicit save/consent, দুই মিনিটে auto-stop, TalkBack audio contamination কমানোর ব্যবস্থা।
- voice sample replace/delete নিরাপত্তা, saved voice playback।
- Settings-এ video mode, scene interval, subtitle offset, voice settings; Back navigation ও main screen সরলীকরণ।
- screen-off recording/video generation-এর foreground service ও wake lock।
- job concurrency সীমা, progress monotonic রাখা, ২৪ ঘণ্টা retention এবং temporary file cleanup।
- backend diagnostics ও documentation-এ বাস্তব provider/limitation দেখানো।

### ৪–৯ নভেম্বর: AI ও provider reliability
- Cloudflare Workers AI visual planner এবং independent storyboard reviewer।
- Cloudflare image model response decoding, model-specific input validation, blank/black image rejection।
- AI image mismatch হলে narration-grounded prompt দিয়ে regeneration; licensed photo recovery; শেষে topic graphic fallback।
- provider cooldown, quota handling, retry, cache এবং image source reporting।
- Bengali word matching/inflection handling এবং sentence-aware scene planning।
- audio-only input-এর transcription support।
- Whisper word timestamps পাওয়া গেলে সেগুলো subtitle timing-এ ব্যবহার।
- accessible scene-by-scene audit, semantic image review counters, audio transcript comparison।
- AI voice chat endpoint একই Cloudflare token reuse করে।

### ১১–১৩ নভেম্বর: AI Brain ও প্রকাশ নিরাপত্তা
- AI Brain বাংলা/ইংরেজি/Banglish ভাষা, topic, content type, tone, audience ও visual style বিশ্লেষণ।
- factual topic হলে সর্বোচ্চ তিনটি Wikipedia search query দিয়ে research context; এটি fact-check নয়।
- AI Brain ও research sources report-এ দেখানো।
- video share/download-এর আগে fail-closed publication gate: visual audit, audio transcript, word timestamps, subtitle OCR, video/audio technical checks।
- subtitle word timestamp integrity ও OCR checks।
- TalkBack report-এ strict word-time check pass/fail ব্যাখ্যা।
- চূড়ান্ত selected scene image পুনরায় duplicate-check; duplicate রয়ে গেলে share/download block।

সাম্প্রতিক audit commits:
- [শব্দের সময়ের কঠোর পরীক্ষার প্রতিবেদন](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/00d0dcf52de2f70306b6e6db984735e59405333d)
- [চূড়ান্ত ছবির duplicate অবশিষ্ট থাকলে প্রকাশ বন্ধ](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/25decc473f4282cd36bba23cc6b152413fcfb292)
- [duplicate gate-এর unit tests](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/commit/2a2fb82473fc1fc5da61ba544cf9851a9c9b2955)

## ২. বর্তমান কোডে পাওয়া AI model ও provider তালিকা

### ভাষা বোঝা, AI Brain, storyboard ও chat
- Cloudflare Workers AI @cf/meta/llama-3.2-3b-instruct — AI Brain default এবং voice chat fallback chain-এর অংশ।
- @cf/qwen/qwen3-30b-a3b-fp8 — AI Brain/storyboard/chat fallback।
- @cf/google/gemma-4-26b-a4b-it — storyboard planner default chain, AI Brain/chat fallback।
- @cf/zai-org/glm-4.7-flash — storyboard visual planner fallback।
- Local keyword-based planning — Cloudflare credentials/quota/model failure হলে fallback।
- Public Wikipedia search — factual research context; independently fact-checked নয়।

### ছবির পরিকল্পনা ও ছবির বিষয়বস্তু যাচাই
- Cloudflare Workers AI image models: @cf/black-forest-labs/flux-1-schnell, @cf/lykon/dreamshaper-8-lcm, @cf/bytedance/stable-diffusion-xl-lightning।
- Pollinations hosted FLUX image endpoint — no-account free endpoint; availability/rate limit বদলাতে পারে।
- Hugging Face Spaces: black-forest-labs/FLUX.1-schnell এবং Tongyi-MAI/Z-Image-Turbo।
- Licensed image sources: Openverse API এবং Wikimedia Commons API।
- শেষ fallback: local topic-specific graphic; এটি photograph নয়।
- Vision reviewer: Cloudflare Workers AI @cf/moondream/moondream3.1-9B-A2B — selected photographic scene-এর narration/image মিল যাচাই করে। Quota/credential/model failure হলে ফল unavailable হিসেবে থাকে।

### Speech-to-text ও subtitle timing
- Cloudflare Workers AI @cf/openai/whisper-large-v3-turbo — uploaded audio transcription এবং narration audio verification; provider word timestamps দিলে সেগুলো ব্যবহার করা হয়।
- Whisper timestamps না পাওয়া/মেলেনি হলে sentence duration-এর মধ্যে proportional word timing fallback থাকে; কিন্তু strict publication gate এই অনুমানভিত্তিক timing-এ download/share অনুমোদন করে না।
- Tesseract OCR ben ও eng — rendered subtitle frames পরীক্ষা।
- Silence-boundary detection — sentence timing উন্নত করার জন্য; এটি forced alignment নয়।

### Text-to-speech ও নিজের কণ্ঠ
- gTTS / Google Translate TTS — সাধারণ বাংলা/ইংরেজি narration।
- eSpeak NG — gTTS ব্যর্থ হলে local fallback; কণ্ঠ robotic হতে পারে।
- Hugging Face Gradio Space kawshikbuet17/bengali-cosyvoice3-tts-demo — Bengali/mixed voice cloning primary pool।
- ai4bharat/IndicF5 — Bengali voice-clone fallback; reference audio transcript-এর জন্য Cloudflare Whisper প্রয়োজন।
- ResembleAI/Chatterbox — English voice-clone provider।
- ResembleAI/Chatterbox-Multilingual-TTS — English multilingual fallback।
- Voice sample ফোনে private storage-এ থাকে; clone চালালে sample ও script external Hugging Face Space-এ পাঠানো হয়। স্থায়ী private clone model এই integration দেয় না; provider retention/privacy guarantee অ্যাপের নিয়ন্ত্রণে নেই।

## ৩. সার্ভার, hosting ও build infrastructure

### Render
- Repository Blueprint: render.yaml
- Service name: bangla-ai-voice-video-maker-api
- Runtime: Docker, plan: Free, autoDeploy: true, health check: /health
- URL: https://bangla-ai-voice-video-maker-api.onrender.com
- Service ID আগে পাওয়া নথি: srv-db7u1d49v7es73ctjqj0 (বর্তমান service state আবার live account থেকে যাচাই করা বাকি)।
- Docker base: Python 3.11 slim; FastAPI/Uvicorn; FFmpeg/ffprobe; eSpeak NG; Noto fonts; Tesseract Bengali ও English।
- Working files: /tmp/bangla-video-jobs; in-memory job state; default একসঙ্গে ১টি active job; default ২৪ ঘণ্টা retention। Render restart হলে temporary files/job state হারাতে পারে।
- Live deployment commit, current health, events, environment variable names/presence এবং recent logs—Render workspace নির্বাচন নিশ্চিত না হওয়ায় এই audit-এ live account থেকে পুনরায় যাচাই করা হয়নি।

### Cloudflare Workers AI
- Code-এ account ID ও API token environment variables হিসেবে লাগে: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_AI_API_TOKEN (legacy alias CLOUDFLARE_API_TOKEN)।
- এটি language model, image model, Moondream vision review এবং Whisper-এর integration host করে।
- Account ID/token থাকা বা code integration থাকা মানেই বর্তমান free allocation, model availability বা quota নিশ্চিত নয়।
- কোনো token value এই নথিতে রাখা হয়নি।

### Hugging Face
- Public Spaces voice cloning ও image generation চালায়।
- Optional authentication variable: HF_TOKEN অথবা HUGGINGFACE_HUB_TOKEN।
- Public Spaces-এর free GPU quota, queue, availability ও data retention তৃতীয় পক্ষের নিয়ন্ত্রণে।

### GitHub Actions
- .github/workflows/backend-smoke.yml: Docker build, backend unit tests, health endpoint, Tesseract Bengali/English, video pipeline ও provider/parser smoke checks।
- .github/workflows/android-apk.yml: JDK 17, Gradle 8.9, release APK build, package identity/version check, signature certificate check, single APK artifact এবং GitHub Release publish।
- Android application ID: com.rajuhossain.banglaaivoicemaker; একই package ID ও pinned signing certificate বজায় রাখার উদ্দেশ্য হলো installed app-এ update install করা, আলাদা app নয়।
- Release workflow expects secrets: ANDROID_KEYSTORE_BASE64, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS, ANDROID_KEY_PASSWORD, GH_RELEASE_TOKEN। Secret values কখনো source code-এ রাখা যাবে না।
- Workflow code-এ একটি APK asset publish করার ব্যবস্থা আছে; latest run success ও latest release asset এই audit-এ নিশ্চিত করা হয়নি।

### অন্যান্য
- Supabase project বা Supabase dependency এই repository-তে পাওয়া যায়নি।
- Wikipedia, Openverse, Wikimedia Commons এবং Pollinations হলো external public services; এগুলো Render-এর নিজস্ব server নয়।

## ৪. বর্তমান publication gate কী কী বাধ্যতামূলক করে

বর্তমান _publication_gate_decision এবং download endpoint অনুযায়ী:
1. প্রত্যেক final scene-এর visual status matched অথবা retry_matched হতে হবে।
2. Scene audit count অবশ্যই generated image count-এর সমান হতে হবে।
3. duplicate_remaining=true থাকলে share/download বন্ধ।
4. Whisper transcript মূল script-এর সঙ্গে matched এবং missing/extra token শূন্য হতে হবে।
5. প্রতিটি script word-এর explicit timestamp থাকতে হবে; timestamp count script word count-এর সমান এবং integrity check pass হতে হবে।
6. Subtitle OCR status passed হতে হবে।
7. Video/audio track, decoded frames, duration এবং audible audio signal-এর technical checks pass করতে হবে।
8. Download endpoint download-এর সময় report আবার চালায়; আগের অনুমোদনের ওপর নির্ভর করে না।

## ৫. অমীমাংসিত বিষয় ও সম্ভাব্য বাধা — পুনরাবৃত্ত কাজ এড়ানোর তালিকা

### উচ্চ অগ্রাধিকার
- Semantic review cap বনাম strict gate: IMAGE_SEMANTIC_REVIEW_MAX_SCENES default 12; কিন্তু publication gate প্রত্যেক scene-এর verified match চায়। ১২টির বেশি scene হলে sampled review-এর বাইরে থাকা scene not_reviewed হতে পারে, ফলে share/download block হবে। এটি বাস্তব code-level mismatch; সমাধান ছাড়া এটিকে সম্পন্ন বলা যাবে না।
- Topic graphic fallback বনাম strict gate: local topic graphic semantic vision review এড়িয়ে যায়, কিন্তু gate কেবল matched/retry_matched গ্রহণ করে। ফলে graphic fallback-সহ ভিডিও download block হতে পারে। Safety না কমিয়ে কীভাবে graphic-এর উপযুক্ত যাচাই হবে তা আলাদা করে সমাধান করতে হবে।
- Similarity comparison failure: সংশোধন করা হয়েছে। _scene_images_too_similar image open/compare exception হলে এখন True (duplicate/unknown) দেয়; missing image-এর regression test যোগ করা হয়েছে। এই test GitHub Actions-এ সফল হয়েছে কি না এখনো যাচাই বাকি।
- Live Render audit: workspace selection নিশ্চিত না হওয়ায় service status, deploy commit, events, logs ও env-var presence এখনো live account থেকে পরীক্ষা হয়নি।
- Current CI/release state: backend smoke workflow ও Android release workflow-এর সাম্প্রতিক run success, artifact এবং GitHub Release APK পুনরায় যাচাই দরকার।
- Real device test: TalkBack দিয়ে latest APK install/update, voice recording, screen-off processing, video report এবং download gate—এসব বাস্তব ফোনে পরীক্ষা ছাড়া সম্পূর্ণ বলা যাবে না।

### মধ্যম অগ্রাধিকার
- Voice cloning provider availability, বাংলা উচ্চারণ, ইংরেজি pronunciation, mixed sentence handling এবং voice similarity বাস্তব audio sample দিয়ে পরীক্ষা দরকার।
- Whisper transcript/script comparison ভালো হলেও এটি শতভাগ মানব-স্তরের speech accuracy নয়।
- Tesseract OCR অক্ষর/শব্দ শনাক্ত করতে পারে; এটি সব বানান বা বাক্যের অর্থগত correctness প্রমাণ করে না।
- Job state ও generated files Render-এর ephemeral filesystem-এ; durable storage/resume এখনো নেই।
- Screen-off foreground service activity process death-এর পর polling coroutine resume করে না; job ID persistence/WorkManager integration ভবিষ্যৎ কাজ।
- Social sharing flow, title card ও animated transitions এখনো সম্পূর্ণ নয়।

## ৬. পরবর্তী কাজের ক্রম — একই কাজ পুনরায় না করে

1. Render workspace নিশ্চিত করে live service/deploy/log/environment audit করা।
2. GitHub Actions-এর সর্বশেষ backend এবং Android run, release asset ও signing continuity যাচাই করা।
3. Scene audit cap ও topic graphic verification-এর নিরাপদ সমাধান করা; similarity comparison-এর fail-closed fix যোগ হয়েছে, তার CI ফল যাচাই করা।
4. README ও PRODUCT_PLAN-কে actual code-এর সঙ্গে একীভূতভাবে synchronize করা।
5. Backend smoke tests pass না হওয়া পর্যন্ত deployment/release success দাবি না করা।
6. এরপর একটিমাত্র signed APK release এবং একই app package-এ update install যাচাই করা।
7. শেষে TalkBack-এ report শুনে প্রতিটি gate-এর কারণ স্পষ্টভাবে বলা এবং বাস্তব ফোনে পরীক্ষা।

**অডিট নীতি:** কোনো provider, model, server, test, deployment বা APK-কে active/successful বলা হবে না, যতক্ষণ না তার বর্তমান অবস্থা থেকে প্রমাণ পাওয়া যায়। নতুন কাজের আগে এই নথির “অমীমাংসিত বিষয়” ও commit history দেখে নিতে হবে।
