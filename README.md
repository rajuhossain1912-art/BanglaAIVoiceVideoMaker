# বাংলা AI Voice Video Maker

An online-only, TalkBack-friendly Android app for turning Bangla, English, or mixed-language text—or a script plus a supplied voice recording—into a video.

## চূড়ান্ত লক্ষ্য

- শুধু বাংলা/ইংরেজি লেখা দিলে স্বয়ংক্রিয় ভয়েস ও ভিডিও তৈরি
- লেখা ও নিজের অডিও দিলে কথার সঙ্গে সাবটাইটেল মেলানো
- বিষয় অনুযায়ী ছবি/দৃশ্য, স্বয়ংক্রিয় জুম-প্যান এবং শব্দ হাইলাইট
- MP4 তৈরি ও ফোনের Downloads ফোল্ডারে সংরক্ষণ
- TalkBack-সহায়ক বাংলা ইন্টারফেস
- অনলাইন-নির্ভর ব্যবহার; অফলাইন মোড নেই
- বিনামূল্যের ও ওপেন-সোর্স প্রযুক্তি অগ্রাধিকার; অনুমতি ছাড়া পেইড সেবা নয়

## স্বয়ংক্রিয় AI Brain — নতুন বাস্তবায়ন

ভিডিও রেন্ডার শুরুর আগে AI Brain বাংলা, ইংরেজি ও মিশ্র লেখার ভাষা, বিষয়, ভিডিওর ধরন, আবহ, দর্শক এবং ভিজ্যুয়াল স্টাইল বিশ্লেষণ করে। তথ্যভিত্তিক বিষয় হলে AI সর্বোচ্চ তিনটি অনুসন্ধান-প্রশ্ন তৈরি করে Wikipedia-র উন্মুক্ত অনুসন্ধান থেকে প্রাসঙ্গিক সংক্ষিপ্ত তথ্য আনে। এই গবেষণা-প্রেক্ষাপট দৃশ্য পরিকল্পনায় সহায়তা করে; এটি স্বাধীন তথ্য-যাচাই নয় এবং ব্যবহারকারীর মূল বর্ণনা পরিবর্তন করে না। AI বিশ্লেষণ ও গবেষণার উৎস ভিডিওর কাজের প্রতিবেদনেও সংরক্ষিত থাকে।

## প্রাথমিক বাস্তবায়ন

- Android Jetpack Compose UI
- FastAPI সার্ভার
- FFmpeg দিয়ে MP4 রেন্ডারিং
- Google TTS অনলাইন ভয়েস; ব্যর্থ হলে espeak-ng স্থানীয় fallback
- Pillow ও FFmpeg দিয়ে দৃশ্যভিত্তিক ভিডিও; Cloudflare Workers AI, Pollinations এবং Hugging Face-এর ফ্রি ইমেজ মডেল চেষ্টা; প্রয়োজনে Openverse/Wikimedia-র লাইসেন্সযুক্ত ছবি, শেষে বিষয়ভিত্তিক গ্রাফিক fallback
- অডিও থাকলে আপলোড; না থাকলে সার্ভারে TTS
- অডিওর নীরব বিরতি শনাক্ত করে বাক্যের সময় নির্ধারণের চেষ্টা; তারপর শব্দ-হাইলাইট সাবটাইটেল
- GitHub Actions-এ APK বিল্ড
- Render-এর ফ্রি Docker Web Service-এর জন্য প্রাথমিক Blueprint

## শেয়ার বা ডাউনলোডের আগে বাধ্যতামূলক নিরাপত্তা যাচাই

দৃষ্টিপ্রতিবন্ধী ব্যবহারকারীর অজান্তে ভুল বা অসম্পূর্ণ ভিডিও প্রকাশ ঠেকাতে সর্বশেষ যাচাই-ব্যবস্থায়:

- ভিডিওর প্রতিটি চূড়ান্ত দৃশ্যের অডিট সম্পন্ন না হলে প্রকাশের অনুমতি দেওয়া হয় না।
- ভিডিও থেকে বাস্তবে ডিকোড হওয়া ফ্রেম এবং শ্রবণযোগ্য অডিও সিগন্যাল না পাওয়া গেলে ডাউনলোড/শেয়ার আটকে থাকে।
- প্রকাশের জন্য প্রতিটি সাবটাইটেল শব্দের সময়চিহ্ন উপস্থিত ও বৈধ হতে হয়; অসম্পূর্ণ বা অবৈধ word timestamp থাকলে প্রকাশ আটকে থাকে।
- ডাউনলোড দেখানোর আগেই যাচাই হয় এবং ডাউনলোডের সময় আবার যাচাই করা হয়, যাতে পরে অবস্থা বদলালে পুরোনো অনুমোদনের ওপর নির্ভর না করা হয়।
- কোনো যাচাই ব্যর্থ বা অসম্পূর্ণ হলে অ্যাপকে সেটিকে সফল বলা বা ডাউনলোড অনুমোদন করা উচিত নয়।

এই প্রযুক্তিগত গেটগুলো ভিডিওর প্রতিটি ছবির বিষয়বস্তু বা সাবটাইটেলের বানান মানুষের মতো নিখুঁতভাবে বুঝতে পারে—এমন নিশ্চয়তা নয়। তাই যাচাই প্রতিবেদন ও সীমাবদ্ধতার বার্তা স্পষ্ট রাখতে হবে।

## বর্তমানে যাচাইকৃত সুবিধা

- বাংলা, ইংরেজি এবং মিশ্র লেখার জন্য ভাষাভিত্তিক অংশে Google TTS অনলাইন ভয়েস ব্যবহার; ব্যর্থ হলে eSpeak NG fallback
- GitHub Actions-এ বাংলা, ইংরেজি ও মিশ্র-ভাষার MP4 তৈরি, ডাউনলোড এবং ffprobe যাচাই সফল
- ভিডিওর দৈর্ঘ্য ও নির্বাচিত scene interval অনুযায়ী দৃশ্যের সংখ্যা নির্ধারিত হয়; ডিফল্টে নির্দিষ্ট ৩২/৪৮ ছবির সীমা নেই। Cloudflare Workers AI, Pollinations এবং Hugging Face-এর ছবি-সেবা চেষ্টা করা হয়; ব্যর্থ হলে Openverse/Wikimedia-র লাইসেন্সভিত্তিক ছবি এবং শেষে বিষয়ভিত্তিক গ্রাফিক ব্যবহার করা হয়। ছবির প্রাসঙ্গিকতা নিশ্চিত না হলে publication gate ডাউনলোড/শেয়ার বন্ধ রাখে
- ৩, ৫, ১০, ১৫ ও ২০ সেকেন্ডে দৃশ্য পরিবর্তনের পছন্দ আছে; ডিফল্ট ৩ সেকেন্ড। Settings থেকে সাবটাইটেল অডিওর তুলনায় -১.৫ থেকে +১.৫ সেকেন্ড সরানো যায়। Cloudflare Whisper-এর স্পষ্ট word timestamps পাওয়া গেলে সেগুলো ব্যবহার করা হয়; না পাওয়া গেলে আনুমানিক timing তৈরি হতে পারে, কিন্তু কঠোর publication gate সেই অনুমানভিত্তিক timing-এ ডাউনলোড/শেয়ার অনুমোদন করে না
- প্রতিটি subtitle frame-এ বাংলা ও ইংরেজি Tesseract OCR চালানো হয়। OCR বা explicit word-time integrity পরীক্ষা ব্যর্থ/অসম্পূর্ণ হলে publication gate ডাউনলোড/শেয়ার বন্ধ রাখে
- সর্বশেষ যাচাইকৃত Android APK GitHub Release-এ প্রকাশিত: [v0.3.225](https://github.com/rajuhossain1912-art/BanglaAIVoiceVideoMaker/releases/tag/v0.3.225)। PR #42-এর background-service shutdown safety ও বাংলা নির্দেশনা সংশোধনসহ release build, application identity/version, persistent signing key ও APK signature verification, artifact upload এবং Release publication সফল হয়েছে। এটি সরাসরি APK বিতরণ; Google Play Store release নয়। বাস্তব ফোনে install/update ও TalkBack acceptance test এখনো আলাদাভাবে দরকার।

## গুরুত্বপূর্ণ সীমাবদ্ধতা

ভিজ্যুয়াল semantic review-এর ডিফল্ট এখন প্রতিটি চূড়ান্ত দৃশ্যের জন্য; IMAGE_SEMANTIC_REVIEW_MAX_SCENES দিয়ে positive cap দিলে cap-এর বাইরে থাকা দৃশ্য unreviewed থাকে এবং fail-closed publication gate ডাউনলোড/শেয়ার বন্ধ রাখে। Topic graphic-কে ফটোগ্রাফের প্রশ্নে নয়, আলাদা vision-review path-এ যাচাই করা হয়; match না হলে বা review unavailable হলে gate বন্ধ থাকে। AI/লাইসেন্সযুক্ত ছবির প্রাসঙ্গিকতা শতভাগ নিখুঁত হওয়ার নিশ্চয়তা নেই। Whisper-এর explicit word timestamps পাওয়া গেলে সেগুলো ব্যবহার করা হয়; না পাওয়া গেলে অনুমানভিত্তিক timing তৈরি হতে পারে, কিন্তু publication gate তা গ্রহণ করে না। Tesseract OCR-ও বানান/অর্থের নিখুঁত মানব-স্তরের যাচাই নয়। স্থায়ী backend job storage নেই: Render Free-তে job state memory-তে এবং ফাইল ephemeral storage-এ থাকে; সার্ভার restart/spin-down হলে সক্রিয় কাজ বা ভিডিও হারাতে পারে। অ্যাপ এখন Android process restart-এর পর সংরক্ষিত job ID দিয়ে polling পুনরায় শুরু করতে পারে, কিন্তু backend job হারালে তা পুনরুদ্ধার করতে পারে না। এক সময়ে একটি active video job চলে। আলাদা title card, animated scene transition এবং dedicated in-app social sharing flow এখনো অসম্পূর্ণ। espeak-ng কণ্ঠ রোবোটিক শোনাতে পারে। Free provider-এর quota, timeout ও availability নিশ্চিত নয়; কোনো পেইড API বা Render plan সক্রিয় করা হয়নি।

**নিজের কণ্ঠে লেখা পড়ার পরীক্ষামূলক সুবিধা:** অ্যাপে নিজের কণ্ঠ রেকর্ড/অডিও নির্বাচন, preview এবং সম্মতির পর voice-clone চেষ্টা করা যায়। বাংলা অংশের default provider হলো [Bengali CosyVoice3 demo](https://huggingface.co/spaces/kawshikbuet17/bengali-cosyvoice3-tts-demo); ইংরেজির default provider [Chatterbox](https://huggingface.co/spaces/ResembleAI/Chatterbox), এরপর [Chatterbox Multilingual](https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS)। বাংলা Vakya backup list default-এ ফাঁকা; আলাদা compatible Space operator configure না করলে কোনো Bengali backup নেই। [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5) একটি model repository, hosted Gradio Space নয়; এটিকে Space fallback হিসেবে ব্যবহার করা হয় না। কণ্ঠের sample ফোনের app storage-এ থাকে, কিন্তু cloning request-এ sample ও text বাহ্যিক provider-এ পাঠানো হয়। Public demo-র uptime, quota, data retention বা privacy guarantee এই অ্যাপ নিয়ন্ত্রণ করে না; গোপন/সংবেদনশীল অডিও দেবেন না। Render Free-তে স্থায়ী reusable clone profile রাখার backend storage নেই। বাংলা-ইংরেজি মিশ্র উচ্চারণ, voice similarity এবং প্রতিবার provider success এখনো বাস্তব ব্যবহারকারীর sample দিয়ে যাচাই করা হয়নি; তাই cloning-কে পরীক্ষামূলক হিসেবে ধরতে হবে। কোনো paid provider চালু করা হয়নি.

## গোপনীয়তা ও সীমা

- অ্যাপ অনলাইনে কাজ করে; লেখা, ভিডিও তৈরির অনুরোধ এবং বেছে নেওয়া অডিও Render সার্ভারে পাঠানো হয়।
- কণ্ঠের নমুনা ফোনের ব্যক্তিগত অ্যাপ স্টোরেজে থাকে এবং অ্যাপ থেকে মুছে ফেলা যায়। ক্লোনিং চালালে সেই নমুনা প্রতিবার বাহ্যিক ডেমোতে স্বয়ংক্রিয়ভাবে পাঠানো হয়, তাই ব্যবহারকারীকে প্রতিবার ফাইল নির্বাচন করতে হয় না। এটি স্থায়ী ক্লোন মডেল নয়। সাধারণ অডিও ন্যারেশন ভিডিও তৈরি হওয়ার পর সার্ভারের কাজের ফোল্ডার থেকে মুছে ফেলার চেষ্টা করা হয়। সার্ভার ব্যর্থ হলে বা হোস্টিং/লগিং স্তরে অন্য কপি থাকলে সম্পূর্ণ মুছে যাওয়ার নিশ্চয়তা নেই।
- নিজের কণ্ঠ ক্লোনিং বেছে নিলে কণ্ঠের নমুনা ও লেখা আলাদা বাহ্যিক Hugging Face ডেমোতে পাঠানো হয়। তৃতীয় পক্ষের সংরক্ষণ/লগিং সম্পর্কে নিশ্চয়তা নেই। গোপন বা সংবেদনশীল অডিও দেবেন না এবং শুধু নিজের বা অনুমতিপ্রাপ্ত কণ্ঠ ব্যবহার করুন।
- Render Free-তে সার্ভার ঘুমিয়ে যেতে পারে; বড়/দীর্ঘ ভিডিও, ছবি অনুসন্ধান বা বাহ্যিক ক্লোনিং ব্যর্থ হতে পারে। কোনো পেইড API বা পেইড Render প্ল্যান ব্যবহার করা হচ্ছে না।

## বিল্ড ও ডিপ্লয়

- GitHub Actions workflow: .github/workflows/android-apk.yml
- Render Blueprint: render.yaml
- API health endpoint: /health
- API documentation: /docs
- বিস্তারিত পরিকল্পনা: docs/PRODUCT_PLAN.md
- পূর্ণ ইতিহাস, model/provider inventory ও অমীমাংসিত কাজ: [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md)

