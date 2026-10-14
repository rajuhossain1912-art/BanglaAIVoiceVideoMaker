# বাংলা AI Voice Video Maker

An online-only, TalkBack-friendly Android app for turning Bangla, English, or mixed-language text—or a script plus a supplied voice recording—into a video.

## চূড়ান্ত লক্ষ্য

- শুধু বাংলা/ইংরেজি লেখা দিলে স্বয়ংক্রিয় ভয়েস ও ভিডিও তৈরি
- লেখা ও নিজের অডিও দিলে কথার সঙ্গে সাবটাইটেল মেলানো
- বিষয় অনুযায়ী ছবি/দৃশ্য, শিরোনাম, জুম, ট্রানজিশন ও শব্দ হাইলাইট
- MP4 তৈরি, ফোনে সংরক্ষণ ও শেয়ার
- TalkBack-সহায়ক বাংলা ইন্টারফেস
- অনলাইন-নির্ভর ব্যবহার; অফলাইন মোড নেই
- বিনামূল্যের ও ওপেন-সোর্স প্রযুক্তি অগ্রাধিকার; অনুমতি ছাড়া পেইড সেবা নয়

## প্রাথমিক বাস্তবায়ন

- Android Jetpack Compose UI
- FastAPI সার্ভার
- FFmpeg দিয়ে MP4 রেন্ডারিং
- espeak-ng দিয়ে প্রাথমিক ওপেন-সোর্স TTS
- Pillow দিয়ে গ্রাফিক পটভূমি
- অডিও থাকলে আপলোড; না থাকলে সার্ভারে TTS
- বাক্যভিত্তিক আনুমানিক সাবটাইটেল
- GitHub Actions-এ APK বিল্ড
- Render-এর ফ্রি Docker Web Service-এর জন্য প্রাথমিক Blueprint

## গুরুত্বপূর্ণ সীমাবদ্ধতা

এই সংস্করণটি সম্পূর্ণ AI ভিডিও নির্মাতা নয়। এটি একটি প্রাথমিক ভিডিও-রেন্ডারিং প্রোটোটাইপ: AI-তৈরি বাস্তব দৃশ্য, নির্ভুল শব্দ-স্তরের অডিও-টেক্সট alignment, স্থায়ী job storage এবং উচ্চমানের বাংলা TTS এখনও পরবর্তী কাজ। espeak-ng কণ্ঠ রোবোটিক শোনাতে পারে। Render-এর ফ্রি সার্ভার ঘুমিয়ে যেতে পারে এবং অস্থায়ী কাজ/ফাইল পুনরায় চালু হলে হারাতে পারে।

## বিল্ড ও ডিপ্লয়

- GitHub Actions workflow: .github/workflows/android-apk.yml
- Render Blueprint: render.yaml
- API health endpoint: /health
- API documentation: /docs
- বিস্তারিত পরিকল্পনা: docs/PRODUCT_PLAN.md

