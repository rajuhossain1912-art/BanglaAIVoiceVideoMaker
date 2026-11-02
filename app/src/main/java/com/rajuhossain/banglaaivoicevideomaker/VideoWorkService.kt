package com.rajuhossain.banglaaivoicevideomaker

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat

/**
 * Keeps the app process and CPU available while a user-started video job runs.
 * The actual API job remains owned by the app process; this service provides
 * the foreground execution priority and a partial wake lock while the UI polls.
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
            else -> {
                startForeground(NOTIFICATION_ID, buildNotification())
                acquireWakeLock()
                return START_STICKY
            }
        }
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BanglaAIVoiceVideoMaker:VideoWork")
            .apply {
                setReferenceCounted(false)
                acquire(MAX_WAKE_LOCK_MS)
            }
    }

    private fun buildNotification(): Notification {
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("ভিডিও তৈরি চলছে")
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
                "ভিডিও তৈরির অগ্রগতি",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "ভিডিও তৈরি চলাকালে কাজ চালু রাখার বিজ্ঞপ্তি"
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
        const val ACTION_STOP = "com.rajuhossain.banglaaivoicevideomaker.action.STOP_VIDEO_WORK"
        private const val CHANNEL_ID = "video_work"
        private const val NOTIFICATION_ID = 7301
        private const val MAX_WAKE_LOCK_MS = 4L * 60L * 60L * 1000L
    }
}
