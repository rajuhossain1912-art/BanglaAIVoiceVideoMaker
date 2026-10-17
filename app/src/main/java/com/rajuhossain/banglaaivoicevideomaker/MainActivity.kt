package com.rajuhossain.banglaaivoicevideomaker

import android.Manifest
import android.app.DownloadManager
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) { VideoMakerScreen() }
            }
        }
    }
}

@Composable
private fun VideoMakerScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var script by remember { mutableStateOf("") }
    var audioUri by remember { mutableStateOf<Uri?>(null) }
    var audioName by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("auto") }
    var cloneConsent by remember { mutableStateOf(false) }
    var captionOffset by remember { mutableStateOf(0f) }
    var hasSavedVoiceProfile by remember { mutableStateOf(File(context.filesDir, "voice_profile_sample").exists()) }
    var isRecording by remember { mutableStateOf(false) }
    var recorder by remember { mutableStateOf<MediaRecorder?>(null) }
    var recordingFile by remember { mutableStateOf<File?>(null) }
    var status by remember { mutableStateOf("অনলাইন সার্ভার যুক্ত হলে এখানে ভিডিও তৈরির অবস্থা দেখা যাবে।") }
    var progress by remember { mutableStateOf(0) }
    var online by remember { mutableStateOf(isInternetAvailable(context)) }
    var running by remember { mutableStateOf(false) }
    var downloadPath by remember { mutableStateOf("") }

    LaunchedEffect(mode, hasSavedVoiceProfile) {
        val profile = File(context.filesDir, "voice_profile_sample")
        if (mode == "clone" && hasSavedVoiceProfile && profile.exists()) {
            audioUri = Uri.fromFile(profile)
            audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
        } else if (mode != "clone" && audioUri?.scheme == "file" && audioUri?.path == profile.absolutePath) {
            audioUri = null
            audioName = ""
        }
    }

    val startVoiceRecording: () -> Unit = {
        try {
            val target = File(context.filesDir, "voice_profile_sample")
            val newRecorder = MediaRecorder()
            newRecorder.setAudioSource(MediaRecorder.AudioSource.MIC)
            newRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            newRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            newRecorder.setAudioSamplingRate(16000)
            newRecorder.setAudioEncodingBitRate(64000)
            newRecorder.setOutputFile(target.absolutePath)
            newRecorder.prepare()
            newRecorder.start()
            recorder = newRecorder
            recordingFile = target
            isRecording = true
            status = "নিজের কণ্ঠ রেকর্ড হচ্ছে। স্বাভাবিকভাবে ১০ থেকে ৩০ সেকেন্ড কথা বলুন, তারপর রেকর্ড বন্ধ করুন।"
        } catch (e: Exception) {
            runCatching { recorder?.release() }
            recorder = null
            isRecording = false
            status = "রেকর্ডিং শুরু করা যায়নি। মাইক্রোফোনের অনুমতি ও ফোনের স্টোরেজ পরীক্ষা করুন।"
        }
    }
    val recordPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startVoiceRecording()
        else status = "নিজের কণ্ঠ রেকর্ড করতে মাইক্রোফোনের অনুমতি দিতে হবে।"
    }
    fun stopVoiceRecording() {
        val currentRecorder = recorder
        val target = recordingFile
        var saved = false
        try {
            currentRecorder?.stop()
            saved = target != null && target.exists() && target.length() > 1000
        } catch (_: Exception) {
            status = "রেকর্ডিং খুব ছোট হয়েছে বা সংরক্ষণ করা যায়নি। আবার ১০ থেকে ৩০ সেকেন্ড রেকর্ড করুন।"
        } finally {
            runCatching { currentRecorder?.reset() }
            runCatching { currentRecorder?.release() }
            recorder = null
            recordingFile = null
            isRecording = false
        }
        if (saved && target != null) {
            audioUri = Uri.fromFile(target)
            audioName = "ফোনে রেকর্ড ও সংরক্ষিত নিজের কণ্ঠ"
            hasSavedVoiceProfile = true
            mode = "clone"
            status = "নিজের কণ্ঠ ফোনে সংরক্ষিত হয়েছে। ভিডিও তৈরির সময় সম্মতি দিলে নমুনাটি স্বয়ংক্রিয়ভাবে ক্লোনিং সেবায় পাঠানো হবে; প্রতিবার ফাইল বেছে নিতে হবে না।"
        } else {
            target?.delete()
            hasSavedVoiceProfile = false
        }
    }

    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            if (mode == "clone") {
                try {
                    val profile = File(context.filesDir, "voice_profile_sample")
                    context.contentResolver.openInputStream(uri).use { input ->
                        requireNotNull(input) { "অডিও ফাইল খোলা যায়নি" }
                        profile.outputStream().use { output -> input.copyTo(output) }
                    }
                    audioUri = Uri.fromFile(profile)
                    audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
                    hasSavedVoiceProfile = true
                    status = "কণ্ঠের নমুনা শুধু এই ফোনের অ্যাপের ব্যক্তিগত স্টোরেজে সংরক্ষিত হয়েছে। ক্লোনিং চালালে সম্মতি দেওয়ার পর বাহ্যিক সার্ভারে পাঠানো হবে।"
                } catch (e: Exception) {
                    status = "কণ্ঠের নমুনা ফোনে সংরক্ষণ করা যায়নি।"
                }
            } else {
                audioUri = uri
                audioName = uri.lastPathSegment ?: "অডিও ফাইল নির্বাচন করা হয়েছে"
                mode = "audio"
                status = "অডিও ফাইল নির্বাচন করা হয়েছে।"
            }
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Bangla AI Voice Video Maker", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("বাংলা, ইংরেজি বা মিশ্র লেখা থেকে ভিডিও তৈরি করুন। বিষয়ভিত্তিক বিনামূল্যের ছবি পাওয়া গেলে ব্যাকগ্রাউন্ডে ব্যবহার হবে; না পেলে গ্রাফিক ব্যাকগ্রাউন্ড থাকবে। ভিডিওতে জুম ও আনুমানিক শব্দ-হাইলাইট সাবটাইটেল থাকবে।")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (online) "ইন্টারনেট সংযোগ পাওয়া গেছে" else "ইন্টারনেট সংযোগ পাওয়া যায়নি", fontWeight = FontWeight.SemiBold)
                OutlinedButton(onClick = { online = isInternetAvailable(context) }, modifier = Modifier.fillMaxWidth()) {
                    Text("ইন্টারনেট আবার পরীক্ষা করুন")
                }
            }
        }
        Text("ভিডিও তৈরির পদ্ধতি", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = mode == "auto", onClick = { mode = "auto" }, enabled = !running)
            Text("শুধু লেখা: স্বয়ংক্রিয় ভয়েস")
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = mode == "audio", onClick = { mode = "audio" }, enabled = !running)
            Text("লেখা ও আমার অডিও")
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = mode == "clone", onClick = { mode = "clone" }, enabled = !running)
            Text("পরীক্ষামূলক: আমার কণ্ঠে লেখা পড়ুন")
        }
        if (mode == "clone") {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("গুরুত্বপূর্ণ গোপনীয়তা সতর্কতা", fontWeight = FontWeight.Bold)
                    Text("আপনার কণ্ঠের নমুনা ফোনের ব্যক্তিগত অ্যাপ স্টোরেজে রাখা হয়। এই ফ্রি ডেমোতে আলাদা ক্লোন মডেল স্থায়ীভাবে সংরক্ষণের ব্যবস্থা নেই, তাই প্রতিটি ভিডিও তৈরির সময় অ্যাপ নমুনাটি স্বয়ংক্রিয়ভাবে Hugging Face-এর বাইরের ডেমো সার্ভারে পাঠাবে। সেই সার্ভারের সংরক্ষণ বা লগিং সম্পর্কে আমরা নিশ্চয়তা দিতে পারি না। ব্যক্তিগত বা গোপন কথা রেকর্ড করবেন না। এই সুবিধা পরীক্ষামূলক, একবারে সর্বোচ্চ ৫০০ অক্ষর এবং ফলাফল নিশ্চিত নয়।")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = cloneConsent, onCheckedChange = { cloneConsent = it }, enabled = !running)
                        Text("আমি বুঝেছি এবং আমার নিজের কণ্ঠের নমুনা বাহ্যিক সার্ভারে পাঠাতে সম্মতি দিচ্ছি।")
                    }
                }
            }
        }
        OutlinedTextField(
            value = script, onValueChange = { script = it },
            modifier = Modifier.fillMaxWidth().height(210.dp),
            label = { Text(if (mode == "clone") "নিজের কণ্ঠে পড়ার লেখা (সর্বোচ্চ ৫০০ অক্ষর)" else "বাংলা বা ইংরেজি লেখা") },
            placeholder = { Text("এখানে সম্পূর্ণ স্ক্রিপ্ট পেস্ট করুন") },
            minLines = 5, enabled = !running,
            supportingText = { Text("সার্ভার লেখা গ্রহণ করে ভিডিও তৈরি করবে।") }
        )
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("সাবটাইটেলের সময় সামঞ্জস্য", fontWeight = FontWeight.SemiBold)
                Text("পরিবর্তন: " + (if (captionOffset > 0f) "+" else "") + String.format("%.1f", captionOffset) + " সেকেন্ড")
                Slider(
                    value = captionOffset,
                    onValueChange = { captionOffset = it },
                    valueRange = -1.5f..1.5f,
                    steps = 29,
                    enabled = !running,
                    modifier = Modifier.semantics { contentDescription = "সাবটাইটেলের সময় আগে বা পরে করার নিয়ন্ত্রণ" }
                )
                Text("কথার তুলনায় লেখা আগে দেখা গেলে ঋণাত্মক দিকে, দেরিতে এলে ধনাত্মক দিকে সরান। এটি পুরো সাবটাইটেল একসঙ্গে সরায়; শব্দে-শব্দে নিখুঁত alignment নয়।", style = MaterialTheme.typography.bodySmall)
            }
        }
        if (mode == "clone") {
            OutlinedButton(
                onClick = {
                    if (isRecording) stopVoiceRecording()
                    else if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startVoiceRecording()
                    else recordPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !running
            ) {
                Text(if (isRecording) "রেকর্ড বন্ধ করে কণ্ঠ ফোনে সেভ করুন" else "নিজের কণ্ঠ রেকর্ড করে ফোনে সেভ করুন")
            }
        }
        OutlinedButton(onClick = { audioPicker.launch("audio/*") }, modifier = Modifier.fillMaxWidth(), enabled = !running && !isRecording) {
            Text(if (mode == "clone" && hasSavedVoiceProfile) "রেকর্ড করা কণ্ঠ বদলান বা অডিও বেছে নিন" else if (mode == "clone") "নিজের কণ্ঠের নমুনা নির্বাচন ও ফোনে সংরক্ষণ করুন" else if (audioName.isBlank()) "অডিও ফাইল নির্বাচন করুন" else "অডিও নির্বাচন করা হয়েছে: " + audioName)
        }
        if (mode == "clone" && hasSavedVoiceProfile) {
            OutlinedButton(onClick = {
                File(context.filesDir, "voice_profile_sample").delete()
                hasSavedVoiceProfile = false
                audioUri = null
                audioName = ""
                status = "ফোনে সংরক্ষিত কণ্ঠের নমুনা মুছে ফেলা হয়েছে।"
            }, modifier = Modifier.fillMaxWidth(), enabled = !running) {
                Text("ফোন থেকে সংরক্ষিত কণ্ঠের নমুনা মুছুন")
            }
        }
        Button(
            onClick = {
                online = isInternetAvailable(context)
                val baseUrl = BuildConfig.API_BASE_URL.trim().trimEnd('/')
                when {
                    script.isBlank() -> status = "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।"
                    mode == "clone" && script.trim().length > 500 -> status = "নিজের কণ্ঠের পরীক্ষায় সর্বোচ্চ ৫০০ অক্ষর দিন।"
                    mode == "clone" && !cloneConsent -> status = "আগে বাহ্যিক সার্ভারে কণ্ঠ পাঠানোর সতর্কতা পড়ে সম্মতি দিন।"
                    !online -> status = "ভিডিও তৈরি করতে ইন্টারনেট সংযোগ দিন।"
                    baseUrl.isBlank() -> status = "অনলাইন API ঠিকানা এখনো সেট করা হয়নি। সার্ভার স্থাপন ও API ঠিকানা যুক্ত করার পর ভিডিও তৈরি চালু হবে।"
                    mode in listOf("audio", "clone") && audioUri == null -> status = "অডিও ফাইল নির্বাচন করুন।"
                    else -> {
                        running = true
                        progress = 0
                        downloadPath = ""
                        status = "অনলাইন সার্ভারে কাজ পাঠানো হচ্ছে।"
                        scope.launch {
                            try {
                                val job = withContext(Dispatchers.IO) { createJob(context, baseUrl, script.trim(), mode, audioUri, cloneConsent, captionOffset) }
                                val jobId = job.getString("id")
                                status = "অনুরোধ গ্রহণ করা হয়েছে। ভিডিও তৈরি চলছে।"
                                var finished = false
                                var attempts = 0
                                while (!finished && attempts < 240) {
                                    delay(2500)
                                    attempts++
                                    val info = withContext(Dispatchers.IO) { getJobStatus(baseUrl, jobId) }
                                    progress = info.optInt("progress", 0)
                                    status = info.optString("message", "ভিডিও তৈরি চলছে।")
                                    when (info.optString("status")) {
                                        "completed" -> {
                                            downloadPath = info.optString("download_url", "/api/jobs/" + jobId + "/download")
                                            status = "ভিডিও তৈরি হয়েছে। এখন ভিডিও সংরক্ষণ করতে নিচের ডাউনলোড বোতাম চাপুন।"
                                            finished = true
                                        }
                                        "failed" -> {
                                            status = "ভিডিও তৈরি করা যায়নি: " + info.optString("message", "অজানা সমস্যা")
                                            finished = true
                                        }
                                    }
                                }
                                if (!finished) status = "সার্ভার এখনো উত্তর দেয়নি। পরে আবার চেষ্টা করুন।"
                            } catch (e: Exception) {
                                status = "সংযোগ বা ভিডিও তৈরিতে সমস্যা হয়েছে: " + (e.message ?: "অজানা সমস্যা")
                            } finally {
                                cloneConsent = false
                                running = false
                            }
                        }
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(), enabled = !running
        ) { Text(if (running) "ভিডিও তৈরি হচ্ছে" else "স্বয়ংক্রিয় ভিডিও তৈরি করুন") }

        if (running) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator()
                Text("অগ্রগতি: " + progress + " শতাংশ")
            }
        }
        if (downloadPath.isNotBlank()) {
            Button(
                onClick = {
                    val baseUrl = BuildConfig.API_BASE_URL.trim().trimEnd('/')
                    val request = DownloadManager.Request(Uri.parse(baseUrl + downloadPath))
                        .setTitle("Bangla AI ভিডিও")
                        .setDescription("তৈরি হওয়া ভিডিও ডাউনলোড হচ্ছে")
                        .setMimeType("video/mp4")
                        .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                        .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "BanglaAI-" + UUID.randomUUID() + ".mp4")
                    val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                    manager.enqueue(request)
                    status = "ভিডিও ডাউনলোড শুরু হয়েছে। ডাউনলোড শেষ হলে ফোনের Downloads ফোল্ডারে পাবে।"
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("ভিডিও ডাউনলোড করুন") }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp)) {
                Text("বর্তমান অবস্থা", fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(6.dp))
                Text(status, modifier = Modifier.semantics { contentDescription = "বর্তমান অবস্থা: " + status })
            }
        }
        Text("প্রাথমিক সংস্করণে MP4, গ্রাফিক পটভূমি ও আনুমানিক সাবটাইটেল তৈরি হয়। নিজের কণ্ঠের ক্লোনিং বাহ্যিক ফ্রি ডেমোর ওপর নির্ভরশীল; সব সময় কাজ নাও করতে পারে।", style = MaterialTheme.typography.bodySmall)
    }
}

private fun createJob(context: Context, baseUrl: String, script: String, mode: String, audioUri: Uri?, cloneConsent: Boolean, captionOffset: Float): JSONObject {
    val boundary = "----BanglaAI" + UUID.randomUUID().toString()
    val connection = (URL(baseUrl + "/api/jobs").openConnection() as HttpURLConnection).apply {
        requestMethod = "POST"
        connectTimeout = 30000
        readTimeout = 180000
        doOutput = true
        setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary)
    }
    try {
        BufferedOutputStream(connection.outputStream).use { output ->
            fun field(name: String, value: String) {
                output.write(("--" + boundary + "\r\n").toByteArray())
                output.write(("Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n").toByteArray())
                output.write(value.toByteArray(Charsets.UTF_8))
                output.write("\r\n".toByteArray())
            }
            field("script", script)
            field("mode", mode)
            field("voice_clone_consent", cloneConsent.toString())
            field("caption_offset", captionOffset.toString())
            if (mode in listOf("audio", "clone") && audioUri != null) {
                output.write(("--" + boundary + "\r\n").toByteArray())
                output.write("Content-Disposition: form-data; name=\"audio\"; filename=\"voice-file\"\r\n".toByteArray())
                output.write("Content-Type: application/octet-stream\r\n\r\n".toByteArray())
                context.contentResolver.openInputStream(audioUri).use { input ->
                    requireNotNull(input) { "অডিও ফাইল খোলা যায়নি" }
                    input.copyTo(output)
                }
                output.write("\r\n".toByteArray())
            }
            output.write(("--" + boundary + "--\r\n").toByteArray())
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        if (body.isBlank()) {
            throw IllegalStateException("সার্ভার খালি উত্তর দিয়েছে (HTTP $code)। ফ্রি সার্ভার সাময়িকভাবে বন্ধ বা পুনরায় চালু হলে কিছুক্ষণ পর আবার চেষ্টা করুন।")
        }
        if (code !in 200..299) {
            val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull().orEmpty()
            throw IllegalStateException(detail.ifBlank { "সার্ভার অনুরোধ গ্রহণ করেনি (HTTP $code)।" })
        }
        return JSONObject(body)
    } finally {
        connection.disconnect()
    }
}

private fun getJobStatus(baseUrl: String, jobId: String): JSONObject {
    val connection = (URL(baseUrl + "/api/jobs/" + jobId).openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 15000
        readTimeout = 30000
    }
    try {
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        if (body.isBlank()) {
            throw IllegalStateException("সার্ভারের অবস্থা খালি এসেছে (HTTP $code)। সার্ভার পুনরায় চালু হলে পরে আবার চেষ্টা করুন।")
        }
        if (code !in 200..299) {
            val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull().orEmpty()
            throw IllegalStateException(detail.ifBlank { "সার্ভারের অবস্থা পাওয়া যায়নি (HTTP $code)।" })
        }
        return JSONObject(body)
    } finally {
        connection.disconnect()
    }
}

private fun isInternetAvailable(context: Context): Boolean {
    val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val network = manager.activeNetwork ?: return false
    val capabilities = manager.getNetworkCapabilities(network) ?: return false
    return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
        capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
}
