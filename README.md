# বাংলা AI Voice Video Maker

An online-only, TalkBack-friendly Android app intended to turn Bangla, English, or mixed-language text into a complete video automatically—or synchronize a supplied voice recording with the script.

## চূড়ান্ত লক্ষ্য

- শুধু বাংলা/ইংরেজি লেখা দিলে অনলাইন TTS দিয়ে ভয়েস তৈরি এবং ভিডিও বানানো
- লেখা ও নিজের অডিও দিলে কথার সঙ্গে লেখা, সাবটাইটেল ও শব্দ হাইলাইট মেলানো
- বিষয় বুঝে শিরোনাম ও উপযুক্ত ছবি/দৃশ্য তৈরি বা নির্বাচন
- স্বয়ংক্রিয় জুম ইন/আউট, প্যান, ট্রানজিশন ও সাবটাইটেল
- MP4 ভিডিও তৈরি, ফোনে সংরক্ষণ ও শেয়ার
- TalkBack ব্যবহারকারীদের জন্য প্রবেশগম্য বাংলা ইন্টারফেস
- অ্যাপটি অনলাইন-নির্ভর; অফলাইন মোড পরিকল্পনায় নেই
- বিনামূল্যের ও ওপেন-সোর্স প্রযুক্তিকে অগ্রাধিকার; অনুমতি ছাড়া কোনো পেইড সেবা নয়

## Repository status

প্রাথমিক Android Jetpack Compose অ্যাপের কাঠামো ও GitHub Actions-এ debug APK তৈরির workflow যোগ করা হয়েছে। বর্তমান UI একটি প্রাথমিক ভিত্তি—এখনও বাস্তব AI/TTS সার্ভার, অডিও আপলোড, শব্দের সময় নির্ধারণ, ছবি তৈরি ও MP4 রেন্ডারিং সংযুক্ত হয়নি। সার্ভার যুক্ত হওয়ার আগে অ্যাপ সম্পূর্ণ ভিডিও তৈরি করতে পারবে না।

## Build

GitHub Actions-এর Build Android APK workflow চালিয়ে debug APK artifact তৈরি করার ব্যবস্থা আছে। সফল বিল্ড হলে workflow-এর Artifacts বিভাগ থেকে APK পাওয়া যাবে।

বিস্তারিত পরিকল্পনা: [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md)
