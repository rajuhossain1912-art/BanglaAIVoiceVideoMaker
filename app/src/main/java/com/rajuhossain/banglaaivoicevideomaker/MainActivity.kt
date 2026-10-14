package com.rajuhossain.banglaaivoicevideomaker

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    VideoMakerScreen()
                }
            }
        }
    }
}

@Composable
private fun VideoMakerScreen() {
    val context = LocalContext.current
    var script by remember { mutableStateOf("") }
    var audioName by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("auto") }
    var status by remember { mutableStateOf("প্রথম সংস্করণ প্রস্তুতির পর্যায়ে। ভিডিও তৈরির অনলাইন সার্ভার এখনো যুক্ত করা হয়নি।") }
    var online by remember { mutableStateOf(isInternetAvailable(context)) }

    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        audioName = uri?.lastPathSegment ?: if (uri != null) "অডিও ফাইল নির্বাচন করা হয়েছে" else audioName
        if (uri != null) {
            mode = "audio"
            status = "অডিও নির্বাচন করা হয়েছে। সার্ভার যুক্ত হলে অডিও ও লেখার মিল যাচাই করা হবে।"
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Bangla AI Voice Video Maker", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("শুধু লেখা দিন, অথবা লেখা ও নিজের অডিও দিন। লক্ষ্য হলো বাকি কাজ স্বয়ংক্রিয়ভাবে করা।")
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (online) "ইন্টারনেট সংযোগ পাওয়া গেছে" else "ইন্টারনেট সংযোগ পাওয়া যায়নি", fontWeight = FontWeight.SemiBold)
                Text("এই অ্যাপ অনলাইনেই কাজ করবে।")
                OutlinedButton(onClick = { online = isInternetAvailable(context) }) { Text("ইন্টারনেট আবার পরীক্ষা করুন") }
            }
        }
        Text("ভিডিও তৈরির পদ্ধতি", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = mode == "auto", onClick = { mode = "auto" })
            Text("শুধু লেখা: AI ভয়েস তৈরি করবে")
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = mode == "audio", onClick = { mode = "audio" })
            Text("লেখা ও আমার অডিও")
        }
        OutlinedTextField(
            value = script,
            onValueChange = { script = it },
            modifier = Modifier.fillMaxWidth().height(210.dp),
            label = { Text("বাংলা বা ইংরেজি লেখা") },
            placeholder = { Text("এখানে সম্পূর্ণ স্ক্রিপ্ট পেস্ট করুন") },
            minLines = 5,
            supportingText = { Text("লেখার বিষয় বুঝে শিরোনাম, দৃশ্য ও সাবটাইটেল তৈরির পরিকল্পনা রয়েছে।") }
        )
        OutlinedButton(onClick = { audioPicker.launch("audio/*") }, modifier = Modifier.fillMaxWidth()) {
            Text(if (audioName.isBlank()) "অডিও ফাইল নির্বাচন করুন" else "অডিও: $audioName")
        }
        Button(
            onClick = {
                online = isInternetAvailable(context)
                status = when {
                    script.isBlank() -> "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।"
                    !online -> "ভিডিও তৈরি করতে ইন্টারনেট সংযোগ দিন।"
                    mode == "audio" && audioName.isBlank() -> "লেখার সঙ্গে মিলানোর জন্য অডিও ফাইল নির্বাচন করুন।"
                    BuildConfig.API_BASE_URL.isBlank() -> "লেখা গ্রহণ করা হয়েছে। তবে ভিডিও তৈরির সার্ভার এখনো সেটআপ করা হয়নি; সার্ভার যুক্ত হলে স্বয়ংক্রিয় ভিডিও তৈরি চালু হবে।"
                    else -> "অনলাইন সার্ভারের সঙ্গে সংযোগের ব্যবস্থা পরবর্তী ধাপে যুক্ত হবে।"
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text("স্বয়ংক্রিয় ভিডিও তৈরি করুন") }
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(14.dp)) {
                Text("বর্তমান অবস্থা", fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(6.dp))
                Text(status, modifier = Modifier.semantics { contentDescription = "বর্তমান অবস্থা: $status" })
            }
        }
        Text("পরবর্তী ধাপ: অনলাইন AI সার্ভার, ভয়েস, ছবি/দৃশ্য, সাবটাইটেল টাইমিং ও MP4 রেন্ডারিং যুক্ত করা।", style = MaterialTheme.typography.bodySmall)
    }
}

private fun isInternetAvailable(context: Context): Boolean {
    val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val network = manager.activeNetwork ?: return false
    val capabilities = manager.getNetworkCapabilities(network) ?: return false
    return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
        capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
}
