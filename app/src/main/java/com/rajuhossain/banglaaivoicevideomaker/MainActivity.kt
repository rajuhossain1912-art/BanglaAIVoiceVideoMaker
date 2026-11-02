// PR build validation trigger: keep this comment while CI verifies the UI changes.
package com.rajuhossain.banglaaivoicevideomaker

import android.Manifest
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.media.MediaMetadataRetriever
import android.media.MediaPlayer
import android.media.AudioManager
import android.media.ToneGenerator
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.WindowManager
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
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.Color
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
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = Color(0xFF176B5B),
                    secondary = Color(0xFF4C7168),
                    background = Color(0xFFF5F8F7),
                    surface = Color(0xFFFFFFFF)
                )
            ) {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { VideoMakerScreen() }
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
    var captionOffset by remember { mutableStateOf(context.getSharedPreferences("video_settings", Context.MODE_PRIVATE).getFloat("caption_offset", 0f)) }
    var sceneInterval by remember { mutableStateOf(context.getSharedPreferences("video_settings", Context.MODE_PRIVATE).getInt("scene_interval", 3)) }
    var showSettings by remember { mutableStateOf(false) }
    var serverStatus by remember { mutableStateOf("সার্ভারের সংযোগ এখনো পরীক্ষা করা হয়নি।") }
    var serverCheckRunning by remember { mutableStateOf(false) }
    var hasSavedVoiceProfile by remember { mutableStateOf(File(context.filesDir, "voice_profile_sample").exists()) }
    var isRecording by remember { mutableStateOf(false) }
    DisposableEffect(isRecording) {
        val window = (context as? ComponentActivity)?.window
        if (isRecording) {
            window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        onDispose {
            window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    var recordingStartedAt by remember { mutableLongStateOf(0L) }
    var autoStopTriggered by remember { mutableStateOf(false) }
    var recorder by remember { mutableStateOf<MediaRecorder?>(null) }
    var recordingFile by remember { mutableStateOf<File?>(null) }
    var previewFile by remember { mutableStateOf(File(context.cacheDir, "voice_recording_preview.m4a").takeIf { it.exists() && it.length() > 1000L }) }
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
            recordingStartedAt = System.currentTimeMillis()
            autoStopTriggered = false
            val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
            tone.startTone(ToneGenerator.TONE_PROP_BEEP, 250)
            scope.launch { delay(350); tone.release() }
            status = "রেকর্ডিং শুরু হয়েছে। শান্ত ঘরে স্বাভাবিক স্বরে কথা বলুন। সর্বোচ্চ ২ মিনিট পর অ্যাপ নিজে থেকেই রেকর্ড বন্ধ করবে। বন্ধ করার জন্য স্ক্রিনে চাপ দিতে হবে না।"
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
        var tooShort = false
        try {
            currentRecorder?.stop()
            if (target != null && target.exists() && target.length() > 1000) {
                val metadata = MediaMetadataRetriever()
                val durationMs = try {
                    metadata.setDataSource(target.absolutePath)
                    metadata.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
                } finally {
                    metadata.release()
                }
                saved = durationMs >= 10_000L
                tooShort = !saved
            }
        } catch (_: Exception) {
            status = "রেকর্ডিং খুব ছোট হয়েছে বা সংরক্ষণ করা যায়নি। আবার ২০ থেকে ৩০ সেকেন্ড রেকর্ড করুন।"
        } finally {
            runCatching { currentRecorder?.reset() }
            runCatching { currentRecorder?.release() }
            recorder = null
            recordingFile = null
            isRecording = false
            recordingStartedAt = 0L
        }
        if (saved && target != null) {
            previewFile = target
            runCatching { previewPlayer?.release() }
            previewPlayer = null
            previewPlaying = false

            // Keep the first completed recording as a private, reusable voice sample.
            // Never silently replace an already-saved sample.
            var autoSaved = false
            var saveFailed = false
            val profile = File(context.filesDir, "voice_profile_sample")
            if (!profile.exists()) {
                val pendingProfile = File(context.filesDir, "voice_profile_sample.pending")
                try {
                    pendingProfile.delete()
                    target.inputStream().use { input ->
                        pendingProfile.outputStream().use { output -> input.copyTo(output) }
                    }
                    require(pendingProfile.exists() && pendingProfile.length() > 1000L) {
                        "রেকর্ড করা অডিও খালি বা অসম্পূর্ণ।"
                    }
                    if (!pendingProfile.renameTo(profile)) {
                        error("ফোনে কণ্ঠের নমুনা সংরক্ষণ করা যায়নি।")
                    }
                    audioUri = Uri.fromFile(profile)
                    audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
                    hasSavedVoiceProfile = true
                    autoSaved = true
                } catch (_: Exception) {
                    saveFailed = true
                } finally {
                    pendingProfile.delete()
                }
            }

            val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80)
            tone.startTone(ToneGenerator.TONE_PROP_ACK, 250)
            scope.launch { delay(350); tone.release() }
            val completion = when {
                autoSaved -> "আপনার রেকর্ড করা কণ্ঠ স্বয়ংক্রিয়ভাবে এই ফোনে নিরাপদ অ্যাপ-স্টোরেজে সংরক্ষণ করা হয়েছে।"
                saveFailed -> "রেকর্ডিং সম্পন্ন হয়েছে, কিন্তু স্বয়ংক্রিয়ভাবে সংরক্ষণ করা যায়নি। শুনে ভালো লাগলে নিচের সংরক্ষণ বোতাম চাপুন।"
                profile.exists() -> "রেকর্ডিং সম্পন্ন হয়েছে। আগের সংরক্ষিত কণ্ঠ অক্ষত রাখা হয়েছে। নতুন রেকর্ডিংটি ব্যবহার করতে চাইলে নিচের বোতাম চাপুন।"
                else -> "রেকর্ডিং সম্পন্ন হয়েছে। নিচে সংরক্ষণের অবস্থা দেখুন।"
            }
            status = (if (autoStopTriggered) "দুই মিনিট পূর্ণ হওয়ায় রেকর্ডিং স্বয়ংক্রিয়ভাবে বন্ধ হয়েছে। " else "রেকর্ডিং সম্পন্ন হয়েছে। ") +
                completion + " এখন নিজের কণ্ঠ শুনে দেখুন।"
        } else {
            target?.delete()
            previewFile = null
            status = if (tooShort) {
                "রেকর্ডিং অন্তত ১০ সেকেন্ড হতে হবে। ভালো ফলের জন্য ২০ থেকে ৩০ সেকেন্ড স্বাভাবিক স্বরে কথা বলুন।"
            } else {
                "রেকর্ডিং পাওয়া যায়নি বা সংরক্ষণ করা যায়নি। আবার ২০ থেকে ৩০ সেকেন্ড কথা বলে রেকর্ড করুন।"
            }
        }
    }

    LaunchedEffect(recordingStartedAt) {
        val startedAt = recordingStartedAt
        if (startedAt > 0L) {
            delay(120_000L)
            if (isRecording && recordingStartedAt == startedAt) {
                autoStopTriggered = true
                stopVoiceRecording()
            }
        }
    }

    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            if (mode == "clone") {
                try {
                    val metadata = MediaMetadataRetriever()
                    val durationMs = try {
                        metadata.setDataSource(context, uri)
                        metadata.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
                    } finally {
                        metadata.release()
                    }
                    require(durationMs >= 10_000L) {
                        "অডিও নমুনা অন্তত ১০ সেকেন্ড হতে হবে। ভালো ফলের জন্য ২০ থেকে ৩০ সেকেন্ডের পরিষ্কার কণ্ঠ নির্বাচন করুন।"
                    }
                    val profile = File(context.filesDir, "voice_profile_sample")
                    val pendingProfile = File(context.filesDir, "voice_profile_sample.pending")
                    pendingProfile.delete()
                    try {
                        context.contentResolver.openInputStream(uri).use { input ->
                            requireNotNull(input) { "অডিও ফাইল খোলা যায়নি" }
                            pendingProfile.outputStream().use { output -> input.copyTo(output) }
                        }
                        require(pendingProfile.exists() && pendingProfile.length() > 1000L) {
                            "নির্বাচিত অডিও ফাইলটি খালি বা অসম্পূর্ণ। অন্য একটি অডিও নির্বাচন করুন।"
                        }
                        val backupProfile = File(context.filesDir, "voice_profile_sample.backup")
                        backupProfile.delete()
                        val hadPreviousProfile = profile.exists()
                        if (hadPreviousProfile && !profile.renameTo(backupProfile)) {
                            throw IllegalStateException("আগের কণ্ঠের নমুনা নিরাপদ রাখা যায়নি।")
                        }
                        if (!pendingProfile.renameTo(profile)) {
                            if (hadPreviousProfile) backupProfile.renameTo(profile)
                            throw IllegalStateException("নতুন কণ্ঠের নমুনা সংরক্ষণ করা যায়নি। আগের নমুনা অক্ষত রাখা হয়েছে।")
                        }
                        backupProfile.delete()
                    } finally {
                        pendingProfile.delete()
                    }
                    audioUri = Uri.fromFile(profile)
                    audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
                    hasSavedVoiceProfile = true
                    status = "কণ্ঠের নমুনা শুধু এই ফোনের অ্যাপের ব্যক্তিগত স্টোরেজে সংরক্ষিত হয়েছে। ক্লোনিং চালালে সম্মতি দেওয়ার পর বাহ্যিক সার্ভারে পাঠানো হবে।"
                } catch (e: Exception) {
                    status = e.message ?: "কণ্ঠের নমুনা ফোনে সংরক্ষণ করা যায়নি।"
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
    BackHandler(enabled = isRecording && !showSettings) { stopVoiceRecording() }

    if (showSettings) {
        SettingsScreen(
            sceneInterval = sceneInterval,
            captionOffset = captionOffset,
            onCaptionOffsetChange = { seconds ->
                captionOffset = seconds
                context.getSharedPreferences("video_settings", Context.MODE_PRIVATE).edit().putFloat("caption_offset", seconds).apply()
            },
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
            Text("বাংলা এআই ভিডিও মেকার", modifier = Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            IconButton(onClick = { showSettings = true }, enabled = !running && !isRecording, modifier = Modifier.semantics { contentDescription = "সেটিংস খুলুন" }) {
                Icon(Icons.Filled.Settings, contentDescription = "সেটিংস")
            }
        }

        OutlinedButton(
            onClick = { showSettings = true },
            modifier = Modifier.fillMaxWidth(),
            enabled = !running && !isRecording
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
            singleLine = true, enabled = !running && !isRecording,
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
            modifier = Modifier.fillMaxWidth(), enabled = !running && !isRecording
        ) { Text("বিষয় থেকে খসড়া তৈরি করুন") }
        OutlinedTextField(
            value = script, onValueChange = { script = it },
            modifier = Modifier.fillMaxWidth().height(210.dp),
            label = { Text(if (mode == "clone") "নিজের কণ্ঠে পড়ার লেখা (সর্বোচ্চ ৩০০০ অক্ষর)" else "বাংলা বা ইংরেজি লেখা") },
            placeholder = { Text("এখানে সম্পূর্ণ স্ক্রিপ্ট পেস্ট করুন") },
            minLines = 5, enabled = !running && !isRecording,
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
            if (previewFile == null && !isRecording) {
                Text(
                    "ভালো কণ্ঠের নমুনার জন্য শান্ত ঘরে ২০ থেকে ১২০ সেকেন্ড স্বাভাবিক স্বরে কথা বলুন। সর্বোচ্চ ২ মিনিট হলে অ্যাপ নিজে থেকে রেকর্ড বন্ধ করবে। ফোন মুখ থেকে প্রায় এক হাত দূরে রাখুন। ফ্যান, গান বা অন্য মানুষের কথা যেন পেছনে না থাকে। নিজের স্বাভাবিক উচ্চারণ ও কথার গতি বজায় রাখুন; ফিসফিস বা চিৎকার করবেন না।",
                    style = MaterialTheme.typography.bodyMedium
                )
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
                        val pendingProfile = File(context.filesDir, "voice_profile_sample.pending")
                        val backupProfile = File(context.filesDir, "voice_profile_sample.backup")
                        pendingProfile.delete()
                        backupProfile.delete()
                        try {
                            source.inputStream().use { input ->
                                pendingProfile.outputStream().use { output -> input.copyTo(output) }
                            }
                            require(pendingProfile.exists() && pendingProfile.length() > 1000L) {
                                "রেকর্ড করা অডিও খালি বা অসম্পূর্ণ। আবার রেকর্ড করুন।"
                            }
                            val hadPreviousProfile = profile.exists()
                            if (hadPreviousProfile && !profile.renameTo(backupProfile)) {
                                error("আগের কণ্ঠের নমুনা নিরাপদ রাখা যায়নি।")
                            }
                            if (!pendingProfile.renameTo(profile)) {
                                if (hadPreviousProfile) backupProfile.renameTo(profile)
                                error("নতুন কণ্ঠের নমুনা সংরক্ষণ করা যায়নি। আগের নমুনা অক্ষত রাখা হয়েছে।")
                            }
                            backupProfile.delete()
                        } finally {
                            pendingProfile.delete()
                        }
                        audioUri = Uri.fromFile(profile)
                        audioName = "ফোনে সংরক্ষিত নিজের কণ্ঠের নমুনা"
                        hasSavedVoiceProfile = true
                        mode = "clone"
                        source.delete()
                        previewFile = null
                        status = "আপনার কণ্ঠ ফোনে সংরক্ষণ করা হয়েছে। এখন নিজের কণ্ঠের পদ্ধতি বেছে ভিডিও তৈরি করতে পারবেন।"
                    } catch (e: Exception) { status = "কণ্ঠ সংরক্ষণ করা যায়নি। আবার চেষ্টা করুন।" }
                }, modifier = Modifier.fillMaxWidth(), enabled = !running && !previewPlaying) { Text(if (hasSavedVoiceProfile) "এই রেকর্ডিং দিয়ে সংরক্ষিত কণ্ঠ বদলান" else "নিজের কণ্ঠ সংরক্ষণ করুন") }
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
                        ContextCompat.startForegroundService(
                            context,
                            Intent(context, VideoWorkService::class.java).setAction(VideoWorkService.ACTION_START)
                        )
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
                                var consecutiveStatusErrors = 0
                                while (!finished && attempts < 1800) {
                                    delay(2500)
                                    attempts++
                                    val info = try {
                                        withContext(Dispatchers.IO) { getJobStatus(baseUrl, jobId) }
                                    } catch (statusError: Exception) {
                                        consecutiveStatusErrors++
                                        if (consecutiveStatusErrors >= 4) {
                                            throw IllegalStateException("সার্ভারের অগ্রগতি বারবার পাওয়া যায়নি। ইন্টারনেট সংযোগ পরীক্ষা করে পরে আবার চেষ্টা করুন।", statusError)
                                        }
                                        status = "সার্ভারের অগ্রগতি সাময়িকভাবে পাওয়া যাচ্ছে না। আবার সংযোগের চেষ্টা করা হচ্ছে।"
                                        continue
                                    }
                                    consecutiveStatusErrors = 0
                                    progress = maxOf(progress, info.optInt("progress", 0))
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
                                runCatching {
                                    context.startService(Intent(context, VideoWorkService::class.java).setAction(VideoWorkService.ACTION_STOP))
                                }
                            }
                        }
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(), enabled = !running && !isRecording
        ) { Text(if (running) "ভিডিও তৈরি হচ্ছে" else "ভিডিও তৈরি করুন") }

        if (running) {
            Row(
                modifier = Modifier.semantics {
                    liveRegion = LiveRegionMode.Polite
                    contentDescription = "ভিডিও তৈরির অগ্রগতি $progress শতাংশ"
                },
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
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
                Text(serverStatus, modifier = Modifier.semantics {
                    liveRegion = LiveRegionMode.Polite
                    contentDescription = "অনলাইন সার্ভারের অবস্থা: " + serverStatus
                })
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
                Text(status, modifier = Modifier.semantics {
                    liveRegion = LiveRegionMode.Polite
                    contentDescription = "ভিডিও তৈরির বর্তমান অবস্থা: " + status
                })
            }
        }
    }
    }
}

@Composable
private fun SettingsScreen(
    sceneInterval: Int,
    captionOffset: Float,
    onCaptionOffsetChange: (Float) -> Unit,
    mode: String,
    onModeChange: (String) -> Unit,
    onSceneIntervalChange: (Int) -> Unit,
    hasSavedVoiceProfile: Boolean,
    onDeleteSavedFiles: () -> Unit,
    onBack: () -> Unit
) {
    var expandedSection by remember { mutableStateOf("video") }
    var showDeleteConfirmation by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("সেটিংস", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            TextButton(onClick = onBack) { Text("ফিরে যান") }
        }

        SettingsGroup(
            title = "ভিডিও ও ভয়েস",
            summary = "ভিডিও তৈরির পদ্ধতি নির্বাচন",
            expanded = expandedSection == "video",
            onToggle = { expandedSection = if (expandedSection == "video") "" else "video" }
        ) {
            listOf(
                "auto" to "স্বয়ংক্রিয় ভয়েস",
                "audio" to "নিজের অডিও",
                "clone" to "নিজের কণ্ঠ"
            ).forEach { (value, label) ->
                Row(
                    modifier = Modifier.fillMaxWidth()
                        .selectable(selected = mode == value, role = Role.RadioButton, onClick = { onModeChange(value) })
                        .padding(vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    RadioButton(selected = mode == value, onClick = null)
                    Spacer(Modifier.width(10.dp))
                    Text(label, style = MaterialTheme.typography.bodyLarge)
                }
            }
        }

        SettingsGroup(
            title = "ছবি ও সাবটাইটেল",
            summary = "দৃশ্য পরিবর্তন ও লেখার সময়",
            expanded = expandedSection == "visual",
            onToggle = { expandedSection = if (expandedSection == "visual") "" else "visual" }
        ) {
            Text("কত সেকেন্ড পরপর ছবি বদলাবে")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                listOf(3, 5, 10, 15, 20).forEach { seconds ->
                    FilterChip(
                        selected = sceneInterval == seconds,
                        onClick = { onSceneIntervalChange(seconds) },
                        label = { Text("${seconds}s") }
                    )
                }
            }
            HorizontalDivider()
            Text("সাবটাইটেলের সময়: " + String.format(java.util.Locale.US, "%.1f", captionOffset) + " সেকেন্ড")
            Slider(
                value = captionOffset,
                onValueChange = onCaptionOffsetChange,
                valueRange = -1.5f..1.5f,
                steps = 29,
                modifier = Modifier.fillMaxWidth()
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("১.৫ সেকেন্ড আগে")
                Text("১.৫ সেকেন্ড পরে")
            }
            TextButton(onClick = { onCaptionOffsetChange(0f) }) { Text("সময় আগের অবস্থায় ফেরান") }
        }

        SettingsGroup(
            title = "সংরক্ষিত কণ্ঠ",
            summary = if (hasSavedVoiceProfile) "কণ্ঠ ফোনে সংরক্ষিত আছে" else "কোনো কণ্ঠ সংরক্ষিত নেই",
            expanded = expandedSection == "voice",
            onToggle = { expandedSection = if (expandedSection == "voice") "" else "voice" }
        ) {
            Text(
                if (hasSavedVoiceProfile) "আপনার কণ্ঠের নমুনা এই ফোনের ব্যক্তিগত অ্যাপ-স্টোরেজে আছে।"
                else "রেকর্ড করা কণ্ঠ সংরক্ষণ করলে এখানে দেখা যাবে।"
            )
            OutlinedButton(
                onClick = { showDeleteConfirmation = true },
                modifier = Modifier.fillMaxWidth(),
                enabled = hasSavedVoiceProfile
            ) { Text("সংরক্ষিত কণ্ঠ মুছুন") }
        }

        SettingsGroup(
            title = "স্ক্রিন বন্ধ থাকলেও কাজ",
            summary = "ভিডিও তৈরি চলাকালে ব্যাকগ্রাউন্ডে কাজ চালু থাকবে",
            expanded = expandedSection == "background",
            onToggle = { expandedSection = if (expandedSection == "background") "" else "background" }
        ) {
            Text("ভিডিও তৈরি শুরু হলে চলমান বিজ্ঞপ্তি ও CPU চালু রাখার ব্যবস্থা ব্যবহার হবে। তাই স্ক্রিন বন্ধ করলেও ভিডিও তৈরির কাজ চলতে থাকবে।")
            Text("ফোনের ব্যাটারি সেভার বা নির্মাতার ব্যাকগ্রাউন্ড সীমাবদ্ধতা অতিরিক্ত বাধা দিতে পারে।")
        }

        if (showDeleteConfirmation) {
            AlertDialog(
                onDismissRequest = { showDeleteConfirmation = false },
                title = { Text("সংরক্ষিত কণ্ঠ মুছবেন?") },
                text = { Text("এই ফোনে রাখা নিজের কণ্ঠের নমুনা মুছে যাবে। ডাউনলোড করা ভিডিও মুছবে না।") },
                confirmButton = {
                    TextButton(onClick = {
                        showDeleteConfirmation = false
                        onDeleteSavedFiles()
                    }) { Text("মুছে ফেলুন") }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteConfirmation = false }) { Text("বাতিল") }
                }
            )
        }
    }
}

@Composable
private fun SettingsGroup(
    title: String,
    summary: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            TextButton(onClick = onToggle, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(if (expanded) "বন্ধ করতে চাপুন" else summary, style = MaterialTheme.typography.bodySmall)
                }
            }
            if (expanded) {
                HorizontalDivider()
                Spacer(Modifier.height(10.dp))
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    content = content
                )
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
