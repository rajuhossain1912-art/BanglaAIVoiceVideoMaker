// PR build validation trigger: keep this comment while CI verifies the UI changes.
package com.rajuhossain.banglaaivoicevideomaker

import android.Manifest
import android.app.DownloadManager
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.media.MediaPlayer
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
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
    var topic by remember { mutableStateOf("") }
    var audioUri by remember { mutableStateOf<Uri?>(null) }
    var audioName by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("auto") }
    var cloneConsent by remember { mutableStateOf(false) }
    var captionOffset by remember { mutableStateOf(0f) }
    var sceneInterval by remember { mutableStateOf(context.getSharedPreferences("video_settings", Context.MODE_PRIVATE).getInt("scene_interval", 3)) }
    var showSettings by remember { mutableStateOf(false) }
    var serverStatus by remember { mutableStateOf("সার্ভারের সংযোগ এখনো পরীক্ষা করা হয়নি।") }
    var serverCheckRunning by remember { mutableStateOf(false) }
    var sceneIntervalMenu by remember { mutableStateOf(false) }
    var hasSavedVoiceProfile by remember { mutableStateOf(File(context.filesDir, "voice_profile_sample").exists()) }
    var isRecording by remember { mutableStateOf(false) }
    var recorder by remember { mutableStateOf<MediaRecorder?>(null) }
    var recordingFile by remember { mutableStateOf<File?>(null) }
    var previewFile by remember { mutableStateOf<File?>(null) }
    var previewPlayer by remember { mutableStateOf<MediaPlayer?>(null) }
    var previewPlaying by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("অনলাইন সার্ভার যুক্ত হলে এখানে ভিডিও তৈরির অবস্থা দেখা যাবে।") }
    var progress by remember { mutableStateOf(0) }
    var online by remember { mutableStateOf(isInternetAvailable(context)) }
    var running by remember { mutableStateOf(false) }
    var downloadPath by remember { mutableStateOf("") }
    var currentJobId by remember { mutableStateOf("") }
    var reportRunning by remember { mutableStateOf(false) }
    var reportText by remember { mutableStateOf("") }

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
            val target = File(context.cacheDir, "voice_recording_preview.m4a")
            target.delete()
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
            val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
            tone.startTone(ToneGenerator.TONE_PROP_BEEP, 250)
            scope.launch { delay(350); tone.release() }
            status = "রেকর্ডিং শুরু হয়েছে। এখন স্বাভাবিকভাবে ১০ থেকে ৩০ সেকেন্ড কথা বলুন। শেষ হলে রেকর্ড বন্ধ করুন।"
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
            previewFile = target
            runCatching { previewPlayer?.release() }
            previewPlayer = null
            previewPlaying = false
            val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
            tone.startTone(ToneGenerator.TONE_PROP_ACK, 250)
            scope.launch { delay(350); tone.release() }
            status = "রেকর্ডিং সম্পন্ন হয়েছে। এখন নিজের কণ্ঠ শুনে দেখুন। ভালো লাগলে কণ্ঠ সংরক্ষণ বোতাম চাপুন।"
        } else {
            target?.delete()
            previewFile = null
            status = "রেকর্ডিং পাওয়া যায়নি বা খুব ছোট হয়েছে। আবার ১০ থেকে ৩০ সেকেন্ড কথা বলে রেকর্ড করুন।"
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

    BackHandler(enabled = showSettings) { showSettings = false }

    if (showSettings) {
        SettingsScreen(
            sceneInterval = sceneInterval,
            mode = mode,
            onModeChange = { selectedMode ->
                mode = selectedMode
                showSettings = false
                status = when (selectedMode) {
                    "auto" -> "স্বয়ংক্রিয় ভয়েস নির্বাচিত হয়েছে। মূল স্ক্রিনে লেখা দিন।"
                    "audio" -> "অডিও ভয়েস নির্বাচিত হয়েছে। মূল স্ক্রিনে অডিও ফাইল বেছে নিন।"
                    else -> "নিজের ভয়েস নির্বাচিত হয়েছে। মূল স্ক্রিনে কণ্ঠের ইনপুট দিন।"
                }
            },
            onSceneIntervalChange = { seconds ->
                sceneInterval = seconds
                context.getSharedPreferences("video_settings", Context.MODE_PRIVATE).edit().putInt("scene_interval", seconds).apply()
            },
            hasSavedVoiceProfile = hasSavedVoiceProfile,
            onDeleteSavedFiles = {
                val deleted = File(context.filesDir, "voice_profile_sample").delete()
                context.cacheDir.listFiles()?.forEach { it.deleteRecursively() }
                hasSavedVoiceProfile = false
                if (audioUri?.scheme == "file") { audioUri = null; audioName = "" }
                status = if (deleted) "ফোনে সংরক্ষিত কণ্ঠের নমুনা ও অস্থায়ী অ্যাপ ফাইল মুছে ফেলা হয়েছে। Downloads ফোল্ডারের ভিডিও মুছতে ফোনের ফাইল ব্যবস্থাপক ব্যবহার করুন।"
                    else "অস্থায়ী অ্যাপ ফাইল মুছে ফেলা হয়েছে। সংরক্ষিত কণ্ঠের নমুনা পাওয়া যায়নি। Downloads ফোল্ডারের ভিডিও অক্ষত আছে।"
            },
            onBack = { showSettings = false }
        )
    } else {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Bangla AI Voice Video Maker", modifier = Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            IconButton(onClick = { showSettings = true }, enabled = !running, modifier = Modifier.semantics { contentDescription = "সেটিংস খুলুন" }) {
                Icon(Icons.Filled.Settings, contentDescription = "সেটিংস")
            }
        }
        Text("বাংলা, ইংরেজি বা মিশ্র লেখা থেকে ভিডিও তৈরি করুন। প্রথমে পদ্ধতি বেছে নিন, তারপর সেই পদ্ধতির প্রয়োজনীয় ইনপুট দিন।")
        OutlinedButton(
            onClick = { showSettings = true },
            modifier = Modifier.fillMaxWidth(),
            enabled = !running
        ) {
            Text("ভিডিও পদ্ধতি: " + when (mode) {
                "audio" -> "অডিও ভয়েস"
                "clone" -> "নিজের ভয়েস"
                else -> "স্বয়ংক্রিয় ভয়েস"
            } + " — পরিবর্তন করতে চাপুন")
        }
        if (mode == "clone") {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("গুরুত্বপূর্ণ গোপনীয়তা সতর্কতা", fontWeight = FontWeight.Bold)
                    Text("আপনার কণ্ঠের নমুনা ফোনের ব্যক্তিগত অ্যাপ স্টোরেজে রাখা হয়। এই ফ্রি ডেমোতে আলাদা ক্লোন মডেল স্থায়ীভাবে সংরক্ষণের ব্যবস্থা নেই, তাই প্রতিটি ভিডিও তৈরির সময় অ্যাপ নমুনাটি স্বয়ংক্রিয়ভাবে Hugging Face-এর বাইরের ডেমো সার্ভারে পাঠাবে। সেই সার্ভারের সংরক্ষণ বা লগিং সম্পর্কে আমরা নিশ্চয়তা দিতে পারি না। ব্যক্তিগত বা গোপন কথা রেকর্ড করবেন না। এই সুবিধা পরীক্ষামূলক，একবারে সর্বোচ্চ ৩০০০ অক্ষর এবং ফলাফল নিশ্চিত নয়।")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = cloneConsent, onCheckedChange = { cloneConsent = it }, enabled = !running)
                        Text("আমি বুঝেছি এবং আমার নিজের কণ্ঠের নমুনা বাহ্যিক সার্ভারে পাঠাতে সম্মতি দিচ্ছি।")
                    }
                }
            }
        }
        OutlinedTextField(
            value = topic, onValueChange = { topic = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("ভিডিওর বিষয়") },
            placeholder = { Text("যেমন: প্রতিবন্ধীদের কর্মসংস্থান") },
            singleLine = true, enabled = !running,
            supportingText = { Text("বিষয় লিখে নিচের বোতামে চাপলে সম্পাদনাযোগ্য খসড়া তৈরি হবে।") }
        )
        OutlinedButton(
            onClick = {
                if (topic.isBlank()) status = "আগে ভিডিওর বিষয় লিখুন।"
                else {
                    script = makeTopicDraft(topic.trim())
                    mode = "auto"
                    status = "বিষয় থেকে প্রাথমিক খসড়া তৈরি হয়েছে। ভিডিও করার আগে পড়ে সম্পাদনা করুন। এটি বিনামূল্যের টেমপ্লেট, সম্পূর্ণ AI-লেখা নয়।"
                }
            },
            modifier = Modifier.fillMaxWidth(), enabled = !running
        ) { Text("বিষয় থেকে খসড়া তৈরি করুন") }
        OutlinedTextField(
            value = script, onValueChange = { script = it },
            modifier = Modifier.fillMaxWidth().height(210.dp),
            label = { Text(if (mode == "clone") "নিজের কণ্ঠে পড়ার লেখা (সর্বোচ্চ ৩০০০ অক্ষর)" else "বাংলা বা ইংরেজি লেখা") },
            placeholder = { Text("এখানে সম্পূর্ণ স্ক্রিপ্ট পেস্ট করুন") },
            minLines = 5, enabled = !running,
            supportingText = { Text("সার্ভার লেখা গ্রহণ করে ভিডিও তৈরি করবে।") }
        )
        if (mode == "audio") {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("অডিও ভয়েস ইনপুট", fontWeight = FontWeight.SemiBold)
                    Text(if (audioName.isBlank()) "ভিডিওর জন্য ফোন থেকে একটি অডিও ফাইল বেছে নিন।" else "নির্বাচিত অডিও: $audioName")
                    OutlinedButton(onClick = { audioPicker.launch("audio/*") }, modifier = Modifier.fillMaxWidth(), enabled = !running) {
                        Text(if (audioName.isBlank()) "অডিও ফাইল নির্বাচন করুন" else "অন্য অডিও নির্বাচন করুন")
                    }
                }
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
                Text(if (isRecording) "রেকর্ডিং বন্ধ করুন" else "নিজের কণ্ঠ রেকর্ড করুন")
            }
            if (previewFile != null && !isRecording) {
                OutlinedButton(onClick = {
                    try {
                        runCatching { previewPlayer?.release() }
                        val player = MediaPlayer().apply {
                            setDataSource(previewFile!!.absolutePath)
                            setOnCompletionListener { it.release(); previewPlayer = null; previewPlaying = false; status = "কণ্ঠ শোনা শেষ হয়েছে। ভালো লাগলে সংরক্ষণ করুন।" }
                            prepare()
                            start()
                        }
                        previewPlayer = player
                        previewPlaying = true
                        status = "আপনার রেকর্ড করা কণ্ঠ বাজছে।"
                    } catch (e: Exception) { previewPlaying = false; status = "রেকর্ড করা কণ্ঠ বাজানো যাচ্ছে না। আবার রেকর্ড করুন।" }
                }, modifier = Modifier.fillMaxWidth(), enabled = !previewPlaying) { Text("রেকর্ড করা নিজের কণ্ঠ শুনুন") }
                OutlinedButton(onClick = { runCatching { previewPlayer?.stop() }; runCatching { previewPlayer?.release() }; previewPlayer = null; previewPlaying = false; status = "কণ্ঠ শোনা বন্ধ হয়েছে।" }, modifier = Modifier.fillMaxWidth(), enabled = previewPlaying) { Text("কণ্ঠ শোনা বন্ধ করুন") }
                Button(onClick = {
                    try {
                        val source = previewFile ?: error("রেকর্ডিং পাওয়া যায়নি")
                        val profile = File(context.filesDir, "voice_profile_sample")
                        source.inputStream().use { input -> profile.outputStream().use { output -> input.copyTo(output) } }
                        require(profile.length() > 1000)
                        audioUri = Uri.fromFile(profile)
                        audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
                        hasSavedVoiceProfile = true
                        mode = "clone"
                        source.delete()
                        previewFile = null
                        status = "আপনার কণ্ঠ ফোনে সংরক্ষণ করা হয়েছে। এখন নিজের কণ্ঠের পদ্ধতি বেছে ভিডিও তৈরি করতে পারবেন।"
                    } catch (e: Exception) { status = "কণ্ঠ সংরক্ষণ করা যায়নি। আবার চেষ্টা করুন।" }
                }, modifier = Modifier.fillMaxWidth(), enabled = !running && !previewPlaying) { Text("ভালো হয়েছে, নিজের কণ্ঠ সংরক্ষণ করুন") }
                OutlinedButton(onClick = { runCatching { previewPlayer?.stop() }; runCatching { previewPlayer?.release() }; previewPlayer = null; previewPlaying = false; previewFile?.delete(); previewFile = null; status = "রেকর্ড করা কণ্ঠ বাতিল করা হয়েছে। চাইলে আবার রেকর্ড করুন।" }, modifier = Modifier.fillMaxWidth()) { Text("রেকর্ডিং বাতিল করুন") }
            }
            OutlinedButton(onClick = { audioPicker.launch("audio/*") }, modifier = Modifier.fillMaxWidth(), enabled = !running && !isRecording) {
                Text(if (hasSavedVoiceProfile) "সংরক্ষিত কণ্ঠ বদলান" else "নিজের কণ্ঠের নমুনা নির্বাচন করুন")
            }
            if (hasSavedVoiceProfile) Text("নিজের কণ্ঠের নমুনা ফোনে সংরক্ষিত আছে। মুছতে Settings খুলুন।", style = MaterialTheme.typography.bodySmall)
        }
        Button(
            onClick = {
                online = isInternetAvailable(context)
                val baseUrl = BuildConfig.API_BASE_URL.trim().trimEnd('/')
                when {
                    script.isBlank() -> status = "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।"
                    mode == "clone" && script.trim().length > 3000 -> status = "নিজের কণ্ঠে একবারে সর্বোচ্চ ৩০০০ অক্ষর দিন।"
                    mode == "clone" && !cloneConsent -> status = "আগে বাহ্যিক সার্ভারে কণ্ঠ পাঠানোর সতর্কতা পড়ে সম্মতি দিন।"
                    !online -> status = "ভিডিও তৈরি করতে ইন্টারনেট সংযোগ দিন।"
                    baseUrl.isBlank() -> status = "অনলাইন API ঠিকানা এখনো সেট করা হয়নি। সার্ভার স্থাপন ও API ঠিকানা যুক্ত করার পর ভিডিও তৈরি চালু হবে।"
                    mode in listOf("audio", "clone") && audioUri == null -> status = "অডিও ফাইল নির্বাচন করুন।"
                    else -> {
                        running = true
                        progress = 0
                        downloadPath = ""
                        currentJobId = ""
                        reportText = ""
                        status = "অনলাইন সার্ভারে কাজ পাঠানো হচ্ছে।"
                        scope.launch {
                            try {
                                val job = withContext(Dispatchers.IO) { createJob(context, baseUrl, script.trim(), mode, audioUri, cloneConsent, captionOffset, sceneInterval) }
                                val jobId = job.getString("id")
                                status = "অনুরোধ গ্রহণ করা হয়েছে। ভিডিও তৈরি চলছে।"
                                var finished = false
                                var attempts = 0
                                while (!finished && attempts < 1800) {
                                    delay(2500)
                                    attempts++
                                    val info = withContext(Dispatchers.IO) { getJobStatus(baseUrl, jobId) }
                                    progress = info.optInt("progress", 0)
                                    status = info.optString("message", "ভিডিও তৈরি চলছে।")
                                    when (info.optString("status")) {
                                        "completed" -> {
                                            currentJobId = jobId
                                            downloadPath = info.optString("download_url", "/api/jobs/" + jobId + "/download")
                                            status = "ভিডিও তৈরি হয়েছে। চাইলে আগে ভিডিও পরীক্ষা ও প্রতিবেদন শুনুন, অথবা ভিডিও ডাউনলোড করুন।"
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
        ) { Text(if (running) "ভিডিও তৈরি হচ্ছে" else "ভিডিও তৈরি করুন") }

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
            Button(
                onClick = {
                    val baseUrl = BuildConfig.API_BASE_URL.trim().trimEnd('/')
                    reportRunning = true
                    reportText = ""
                    status = "ভিডিওর প্রযুক্তিগত পরীক্ষা চলছে।"
                    scope.launch {
                        try {
                            val report = withContext(Dispatchers.IO) { getVideoReport(baseUrl, currentJobId) }
                            reportText = report.optString("report_text", "পরীক্ষার প্রতিবেদন পাওয়া যায়নি।")
                            status = "ভিডিও পরীক্ষা সম্পন্ন হয়েছে। নিচের প্রতিবেদন TalkBack দিয়ে পড়ুন।"
                        } catch (e: Exception) {
                            reportText = "ভিডিও পরীক্ষা করা যায়নি: " + (e.message ?: "অজানা সমস্যা")
                            status = reportText
                        } finally {
                            reportRunning = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !reportRunning && currentJobId.isNotBlank()
            ) { Text(if (reportRunning) "ভিডিও পরীক্ষা চলছে" else "ভিডিও পরীক্ষা ও প্রতিবেদন শুনুন") }
            if (reportText.isNotBlank()) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text("ভিডিও পরীক্ষার প্রতিবেদন", fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(6.dp))
                        Text(reportText, modifier = Modifier.semantics { contentDescription = "ভিডিও পরীক্ষার প্রতিবেদন: " + reportText })
                    }
                }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("বর্তমান অবস্থা", fontWeight = FontWeight.SemiBold)
                Text(if (online) "ফোনের ইন্টারনেট: সংযুক্ত" else "ফোনের ইন্টারনেট: সংযোগ নেই")
                Text(serverStatus, modifier = Modifier.semantics { contentDescription = "অনলাইন সার্ভারের অবস্থা: " + serverStatus })
                OutlinedButton(onClick = {
                    online = isInternetAvailable(context)
                    serverCheckRunning = true
                    serverStatus = "অনলাইন সার্ভারের সংযোগ পরীক্ষা চলছে।"
                    scope.launch {
                        serverStatus = withContext(Dispatchers.IO) {
                            try {
                                val base = BuildConfig.API_BASE_URL.trim().trimEnd('/')
                                val conn = (URL(base + "/health").openConnection() as HttpURLConnection).apply { connectTimeout = 10000; readTimeout = 10000; requestMethod = "GET" }
                                try {
                                    val code = conn.responseCode
                                    if (code in 200..299) "সার্ভার অনলাইন। সর্বশেষ পরীক্ষা সফল (HTTP $code)।" else "সার্ভার উত্তর দিয়েছে, তবে সংযোগ সফল নয় (HTTP $code)।"
                                } finally { conn.disconnect() }
                            } catch (_: Exception) { "সার্ভারে সংযোগ করা যায়নি। ইন্টারনেট বা সার্ভার সাময়িকভাবে বন্ধ থাকতে পারে।" }
                        }
                        serverCheckRunning = false
                    }
                }, modifier = Modifier.fillMaxWidth(), enabled = !serverCheckRunning) {
                    Text(if (serverCheckRunning) "সার্ভার পরীক্ষা চলছে" else "সার্ভার সংযোগ পরীক্ষা ও আপডেট")
                }
                Text(status, modifier = Modifier.semantics { contentDescription = "ভিডিও তৈরির বর্তমান অবস্থা: " + status })
            }
        }
        Text("নিজের কণ্ঠের পরীক্ষামূলক সুবিধা বাহ্যিক ফ্রি ডেমোর ওপর নির্ভরশীল; সব সময় কাজ নাও করতে পারে।", style = MaterialTheme.typography.bodySmall)
    }
    }
}

@Composable
private fun SettingsScreen(
    sceneInterval: Int,
    mode: String,
    onModeChange: (String) -> Unit,
    onSceneIntervalChange: (Int) -> Unit,
    hasSavedVoiceProfile: Boolean,
    onDeleteSavedFiles: () -> Unit,
    onBack: () -> Unit
) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("সেটিংস", modifier = Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            TextButton(onClick = onBack) { Text("মূল স্ক্রিন") }
        }

        Text(
            "ভিডিও তৈরি ও সংরক্ষণের পছন্দগুলো এখানে পরিবর্তন করুন।",
            style = MaterialTheme.typography.bodyMedium
        )

        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("১. ভিডিও তৈরির পদ্ধতি", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("যে পদ্ধতি বেছে নেবেন, মূল স্ক্রিনে ফিরে সেই পদ্ধতির প্রয়োজনীয় ইনপুট দেখা যাবে।", style = MaterialTheme.typography.bodyMedium)
                HorizontalDivider()
                listOf(
                    "auto" to "স্বয়ংক্রিয় ভয়েস",
                    "audio" to "অডিও ফাইলের ভয়েস",
                    "clone" to "নিজের ভয়েস"
                ).forEach { (value, label) ->
                    Row(
                        modifier = Modifier.fillMaxWidth()
                            .selectable(selected = mode == value, role = Role.RadioButton, onClick = { onModeChange(value) })
                            .padding(vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(selected = mode == value, onClick = null)
                        Spacer(Modifier.width(8.dp))
                        Text(label, style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("২. ভিডিওর দৃশ্য", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "ভিডিও চলার সময় কত সেকেন্ড পরপর ছবি বদলাবে তা বেছে নিন। ছোট সময়ে ছবি বেশি ঘন ঘন বদলাবে।",
                    style = MaterialTheme.typography.bodyMedium
                )
                HorizontalDivider()
                listOf(3, 5, 10, 15, 20).forEach { seconds ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectable(
                                selected = sceneInterval == seconds,
                                role = Role.RadioButton,
                                onClick = { onSceneIntervalChange(seconds) }
                            )
                            .padding(vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(selected = sceneInterval == seconds, onClick = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "প্রতি $seconds সেকেন্ডে ছবি পরিবর্তন",
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("৩. সংরক্ষিত ফাইল ও গোপনীয়তা", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    if (hasSavedVoiceProfile) {
                        "নিজের কণ্ঠের নমুনা এই ফোনের অ্যাপ-স্টোরেজে সংরক্ষিত আছে।"
                    } else {
                        "নিজের কণ্ঠের কোনো সংরক্ষিত নমুনা পাওয়া যায়নি।"
                    },
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    "নিচের বোতামটি নিজের কণ্ঠের নমুনা ও অস্থায়ী অ্যাপ ফাইল মুছবে। Downloads ফোল্ডারে ডাউনলোড করা ভিডিও মুছবে না।",
                    style = MaterialTheme.typography.bodyMedium
                )
                OutlinedButton(
                    onClick = onDeleteSavedFiles,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("কণ্ঠের নমুনা ও অস্থায়ী ফাইল মুছুন")
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("৪. মূল স্ক্রিনে ফেরা", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "মূল স্ক্রিনে ফিরে বিষয়, স্ক্রিপ্ট, ভিডিও তৈরির বোতাম এবং সার্ভারের অবস্থা দেখতে পারবেন। ফোনের Back বোতাম চাপলেও সেটিংস থেকে মূল স্ক্রিনে ফিরবেন।",
                    style = MaterialTheme.typography.bodyMedium
                )
                Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
                    Text("মূল স্ক্রিনে ফিরে যান")
                }
            }
        }
    }
}

private fun makeTopicDraft(topic: String): String {
    val clean = topic.trim().trimEnd('।', '.', '!', '?')
    val lower = clean.lowercase()
    val body = when {
        listOf("প্রতিবন্ধী", "দৃষ্টি", "অন্ধ", "disability", "blind").any { lower.contains(it) } -> "প্রতিবন্ধী মানুষের অধিকার, মর্যাদা ও সমান সুযোগ নিশ্চিত করা আমাদের সবার দায়িত্ব। সহায়তার পাশাপাশি শিক্ষা, প্রশিক্ষণ, সহজগম্য সেবা এবং সম্মানজনক কর্মসংস্থানের সুযোগ বাড়াতে হবে। নীতি থাকলেই যথেষ্ট নয়; বাস্তবে তা কার্যকর হচ্ছে কি না সেটিও পর্যবেক্ষণ করা জরুরি।"
        listOf("চাকরি", "কর্মসংস্থান", "আয়", "কাজ", "job", "income").any { lower.contains(it) } -> "সম্মানজনক জীবনের জন্য কাজের সুযোগ অত্যন্ত গুরুত্বপূর্ণ। দক্ষতা ও যোগ্যতা থাকা সত্ত্বেও অনেক মানুষ উপযুক্ত কাজ পান না। নিয়োগে বৈষম্য কমানো, দক্ষতাভিত্তিক প্রশিক্ষণ বাড়ানো এবং কর্মক্ষেত্রকে সবার জন্য সহজগম্য করা দরকার।"
        listOf("স্বাস্থ্য", "চিকিৎসা", "হাসপাতাল", "health", "hospital").any { lower.contains(it) } -> "স্বাস্থ্যসেবা মানুষের মৌলিক প্রয়োজন। চিকিৎসার খরচ, দূরত্ব ও তথ্যের অভাব যেন বাধা না হয়, সে বিষয়ে গুরুত্ব দিতে হবে। সেবাকেন্দ্রে স্বচ্ছ তথ্য, ন্যায্য খরচ এবং রোগীর প্রতি সম্মান থাকা দরকার।"
        listOf("পরিবেশ", "গাছ", "দূষণ", "নদী", "environment").any { lower.contains(it) } -> "পরিবেশ রক্ষা সবার দায়িত্ব। বর্জ্য কমানো, গাছ লাগানো, পানি ও বিদ্যুতের অপচয় রোধ এবং দূষণ নিয়ন্ত্রণে সচেতনতা বাড়ানো জরুরি। ছোট ছোট দায়িত্বশীল পদক্ষেপ মিলেই ইতিবাচক পরিবর্তন আনতে পারে।"
        else -> "এই বিষয়টি আমাদের দৈনন্দিন জীবন ও সমাজের সঙ্গে কীভাবে সম্পর্কিত, তা বোঝা জরুরি। প্রথমে নির্ভরযোগ্য তথ্য জানা, বিভিন্ন দিক বিবেচনা করা এবং বাস্তব অভিজ্ঞতা থেকে শিক্ষা নেওয়া দরকার। সিদ্ধান্তে পৌঁছানোর আগে তথ্য যাচাই করা উচিত এবং ভিন্নমত থাকলেও পারস্পরিক সম্মান বজায় রাখা প্রয়োজন।"
    }
    return listOf("আসসালামু আলাইকুম।", "আজকের ভিডিওর বিষয়: $clean।", body, "আপনার মতামত কমেন্টে জানাতে পারেন। তথ্যটি উপকারী মনে হলে অন্যদের সঙ্গেও শেয়ার করুন। ধন্যবাদ।").joinToString("\n\n")
}
private fun createJob(context: Context, baseUrl: String, script: String, mode: String, audioUri: Uri?, cloneConsent: Boolean, captionOffset: Float, sceneInterval: Int): JSONObject {
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
            field("scene_interval", sceneInterval.toString())
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


private fun getVideoReport(baseUrl: String, jobId: String): JSONObject {
    require(jobId.matches(Regex("[a-fA-F0-9]{16,64}"))) { "ভিডিওর পরিচয় পাওয়া যায়নি।" }
    val connection = (URL(baseUrl + "/api/jobs/" + jobId + "/report").openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 15000
        readTimeout = 120000
    }
    try {
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        if (body.isBlank()) {
            throw IllegalStateException("পরীক্ষার প্রতিবেদন খালি এসেছে (HTTP $code)।")
        }
        if (code !in 200..299) {
            val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull().orEmpty()
            throw IllegalStateException(detail.ifBlank { "প্রতিবেদন পাওয়া যায়নি (HTTP $code)।" })
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
