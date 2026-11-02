package com.rajuhossain.banglaaivoicevideomaker

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat

/**
 * Gives user-started recording and video generation foreground priority,
 * with a partial wake lock so screen-off does not suspend CPU work.
 */
class VideoWorkService : Service() {
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopWork()
                return START_NOT_STICKY
            }
            ACTION_START_RECORDING -> {
                promoteToForeground(isRecording = true)
                acquireWakeLock()
                return START_NOT_STICKY
            }
            else -> {
                promoteToForeground(isRecording = false)
                acquireWakeLock()
                return START_NOT_STICKY
            }
        }
    }

    private fun promoteToForeground(isRecording: Boolean) {
        val notification = buildNotification(isRecording)
        when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && isRecording ->
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q ->
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            else -> startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BanglaAIVoiceVideoMaker:ActiveWork")
            .apply {
                setReferenceCounted(false)
                acquire(MAX_WAKE_LOCK_MS)
            }
    }

    private fun buildNotification(isRecording: Boolean): Notification {
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(if (isRecording) "কণ্ঠ রেকর্ড হচ্ছে" else "ভিডিও তৈরি চলছে")
            .setContentText("স্ক্রিন বন্ধ থাকলেও কাজ চালু থাকবে")
            .setContentIntent(openApp)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "অ্যাপের চলমান কাজ",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "রেকর্ডিং বা ভিডিও তৈরি চলাকালে কাজ চালু রাখার বিজ্ঞপ্তি"
                setShowBadge(false)
            }
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(channel)
        }
    }

    private fun stopWork() {
        if (wakeLock?.isHeld == true) wakeLock?.release()
        wakeLock = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        if (wakeLock?.isHeld == true) wakeLock?.release()
        wakeLock = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.rajuhossain.banglaaivoicevideomaker.action.START_VIDEO_WORK"
        const val ACTION_START_RECORDING = "com.rajuhossain.banglaaivoicevideomaker.action.START_RECORDING_WORK"
        const val ACTION_STOP = "com.rajuhossain.banglaaivoicevideomaker.action.STOP_ACTIVE_WORK"
        private const val CHANNEL_ID = "active_work"
        private const val NOTIFICATION_ID = 7301
        private const val MAX_WAKE_LOCK_MS = 4L * 60L * 60L * 1000L
    }
}
