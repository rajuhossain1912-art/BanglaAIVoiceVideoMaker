package com.rajuhossain.banglaaivoicevideomaker

import android.app.DownloadManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
    var status by remember { mutableStateOf("অনলাইন সার্ভার যুক্ত হলে এখানে ভিডিও তৈরির অবস্থা দেখা যাবে।") }
    var progress by remember { mutableStateOf(0) }
    var online by remember { mutableStateOf(isInternetAvailable(context)) }
    var running by remember { mutableStateOf(false) }
    var downloadPath by remember { mutableStateOf("") }

    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            audioUri = uri
            audioName = uri.lastPathSegment ?: "অডিও ফাইল নির্বাচন করা হয়েছে"
            mode = "audio"
            status = "অডিও ফাইল নির্বাচন করা হয়েছে।"
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Bangla AI Voice Video Maker", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("শুধু লেখা দিন, অথবা লেখা ও নিজের অডিও দিন। অ্যাপটি অনলাইন সার্ভারের মাধ্যমে ভিডিও তৈরি করবে।")
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
                    Text("এই পরীক্ষায় আপনার কণ্ঠের নমুনা ও লেখা Hugging Face-এর বাইরের ডেমো সার্ভারে পাঠানো হবে। সেই সার্ভারের সংরক্ষণ বা লগিং সম্পর্কে আমরা নিশ্চয়তা দিতে পারি না। তাই গোপন বা ব্যক্তিগত কথা দেবেন না। এই সুবিধা পরীক্ষামূলক, একবারে সর্বোচ্চ ৫০০ অক্ষর এবং ফলাফল নিশ্চিত নয়।")
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
        OutlinedButton(onClick = { audioPicker.launch("audio/*") }, modifier = Modifier.fillMaxWidth(), enabled = !running) {
            Text(if (audioName.isBlank()) "অডিও ফাইল নির্বাচন করুন" else "অডিও নির্বাচন করা হয়েছে: " + audioName)
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
                                val job = withContext(Dispatchers.IO) { createJob(context, baseUrl, script.trim(), mode, audioUri, cloneConsent) }
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

private fun createJob(context: Context, baseUrl: String, script: String, mode: String, audioUri: Uri?, cloneConsent: Boolean): JSONObject {
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
        val body = BufferedInputStream(stream).use { it.readBytes().toString(Charsets.UTF_8) }
        if (code !in 200..299) throw IllegalStateException(JSONObject(body).optString("detail", "সার্ভার অনুরোধ গ্রহণ করেনি।"))
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
        val body = BufferedInputStream(stream).use { it.readBytes().toString(Charsets.UTF_8) }
        if (code !in 200..299) throw IllegalStateException(JSONObject(body).optString("detail", "সার্ভারের অবস্থা পাওয়া যায়নি।"))
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
