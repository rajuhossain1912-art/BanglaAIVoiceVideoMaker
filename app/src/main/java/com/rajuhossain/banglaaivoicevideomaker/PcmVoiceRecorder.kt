package com.rajuhossain.banglaaivoicevideomaker

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile

/**
 * Records mono PCM through AudioRecord so Android's capture effects can attach
 * to the real audio session. Effects are best-effort and device-dependent.
 */
internal class PcmVoiceRecorder(private val outputFile: File) {
    data class Result(
        val durationMs: Long,
        val usedVoiceCommunication: Boolean,
        val enabledEffects: List<String>
    )

    private var audioRecord: AudioRecord? = null
    private var output: BufferedOutputStream? = null
    private var worker: Thread? = null
    private var noiseSuppressor: NoiseSuppressor? = null
    private var echoCanceler: AcousticEchoCanceler? = null
    private var automaticGainControl: AutomaticGainControl? = null
    private var sampleRate = 48_000
    private var bufferSize = 0
    private var usedVoiceCommunication = false
    private val enabledEffects = mutableListOf<String>()

    @Volatile private var recording = false
    @Volatile private var workerError: Throwable? = null

    fun prepare() {
        check(audioRecord == null) { "রেকর্ডার ইতিমধ্যে প্রস্তুত।" }
        val options = listOf(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION to 48_000,
            MediaRecorder.AudioSource.VOICE_COMMUNICATION to 44_100,
            MediaRecorder.AudioSource.MIC to 48_000,
            MediaRecorder.AudioSource.MIC to 44_100
        )
        var lastError: Exception? = null
        for ((source, rate) in options) {
            var candidate: AudioRecord? = null
            try {
                val minimum = AudioRecord.getMinBufferSize(
                    rate,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT
                )
                check(minimum > 0) { "এই ফোনের অডিও বাফার সমর্থিত নয়।" }
                val bytes = maxOf(minimum * 2, rate / 5)
                candidate = AudioRecord.Builder()
                    .setAudioSource(source)
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setSampleRate(rate)
                            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .build()
                    )
                    .setBufferSizeInBytes(bytes)
                    .build()
                check(candidate.state == AudioRecord.STATE_INITIALIZED) {
                    "ফোনের মাইক্রোফোন প্রস্তুত হয়নি।"
                }

                releaseEffects()
                val session = candidate.audioSessionId
                noiseSuppressor = runCatching { NoiseSuppressor.create(session) }.getOrNull()
                echoCanceler = runCatching { AcousticEchoCanceler.create(session) }.getOrNull()
                automaticGainControl = runCatching { AutomaticGainControl.create(session) }.getOrNull()
                enableEffect(noiseSuppressor, "নয়েজ কমানো")
                enableEffect(echoCanceler, "ইকো কমানো")
                enableEffect(automaticGainControl, "ভলিউম সমান করা")

                audioRecord = candidate
                sampleRate = rate
                bufferSize = bytes
                usedVoiceCommunication = source == MediaRecorder.AudioSource.VOICE_COMMUNICATION
                outputFile.parentFile?.mkdirs()
                outputFile.delete()
                output = BufferedOutputStream(FileOutputStream(outputFile, false), bytes)
                output!!.write(ByteArray(44))
                workerError = null
                return
            } catch (error: Exception) {
                lastError = error
                runCatching { candidate?.stop() }
                runCatching { candidate?.release() }
                releaseEffects()
                audioRecord = null
                runCatching { output?.close() }
                output = null
                outputFile.delete()
            }
        }
        throw IllegalStateException("এই ফোনে সমর্থিত অডিও রেকর্ডার চালু করা যায়নি।", lastError)
    }

    private fun enableEffect(effect: android.media.audiofx.AudioEffect?, label: String) {
        if (effect == null) return
        runCatching {
            if (effect.hasControl()) {
                effect.enabled = true
                if (effect.enabled) enabledEffects.add(label)
            }
        }
    }

    fun start() {
        val recorder = checkNotNull(audioRecord) { "রেকর্ডার প্রস্তুত নয়।" }
        check(!recording) { "রেকর্ডিং ইতিমধ্যে চলছে।" }
        try {
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                "মাইক্রোফোন রেকর্ডিং শুরু করেনি।"
            }
            recording = true
            worker = Thread({
                val buffer = ByteArray(bufferSize)
                try {
                    while (recording) {
                        val count = recorder.read(buffer, 0, buffer.size, AudioRecord.READ_BLOCKING)
                        if (count > 0) {
                            output?.write(buffer, 0, count)
                        } else if (count != AudioRecord.ERROR_INVALID_OPERATION &&
                            count != AudioRecord.ERROR_BAD_VALUE &&
                            count != AudioRecord.ERROR_DEAD_OBJECT
                        ) {
                            if (recording) throw IOException("মাইক্রোফোন থেকে অডিও পড়া যায়নি।")
                        } else if (recording) {
                            throw IOException("মাইক্রোফোন সংযোগ বিচ্ছিন্ন হয়েছে।")
                        }
                    }
                } catch (error: Throwable) {
                    if (recording) workerError = error
                } finally {
                    runCatching { output?.flush() }
                    runCatching { output?.close() }
                    output = null
                }
            }, "BanglaAI-AudioCapture").apply {
                priority = Thread.MAX_PRIORITY
                start()
            }
        } catch (error: Exception) {
            recording = false
            runCatching { recorder.stop() }
            throw error
        }
    }

    @Synchronized
    fun stop(): Result {
        val recorder = audioRecord ?: throw IllegalStateException("রেকর্ডার চালু ছিল না।")
        recording = false
        runCatching { recorder.stop() }
        worker?.join(5_000L)
        check(worker?.isAlive != true) { "অডিও রেকর্ডিং নিরাপদে বন্ধ করা যায়নি।" }
        runCatching { output?.flush() }
        runCatching { output?.close() }
        output = null
        releaseCapture()
        workerError?.let { throw IOException("রেকর্ডিংয়ের সময় অডিও ত্রুটি হয়েছে।", it) }

        val dataLength = (outputFile.length() - 44L).coerceAtLeast(0L)
        check(dataLength > 1_000L) { "রেকর্ড করা অডিও খালি বা অসম্পূর্ণ।" }
        writeWaveHeader(outputFile, dataLength, sampleRate)
        return Result(
            durationMs = dataLength * 1000L / (sampleRate * 2L),
            usedVoiceCommunication = usedVoiceCommunication,
            enabledEffects = enabledEffects.toList()
        )
    }

    fun release() {
        recording = false
        audioRecord?.let { runCatching { it.stop() } }
        runCatching { worker?.join(1_000L) }
        runCatching { output?.close() }
        output = null
        releaseCapture()
    }

    private fun releaseCapture() {
        releaseEffects()
        runCatching { audioRecord?.release() }
        audioRecord = null
        worker = null
    }

    private fun releaseEffects() {
        runCatching { noiseSuppressor?.release() }
        runCatching { echoCanceler?.release() }
        runCatching { automaticGainControl?.release() }
        noiseSuppressor = null
        echoCanceler = null
        automaticGainControl = null
        enabledEffects.clear()
    }

    private fun writeWaveHeader(file: File, dataLength: Long, rate: Int) {
        RandomAccessFile(file, "rw").use { wave ->
            wave.seek(0)
            wave.writeBytes("RIFF")
            writeIntLe(wave, dataLength + 36L)
            wave.writeBytes("WAVE")
            wave.writeBytes("fmt ")
            writeIntLe(wave, 16L)
            writeShortLe(wave, 1)
            writeShortLe(wave, 1)
            writeIntLe(wave, rate.toLong())
            writeIntLe(wave, rate * 2L)
            writeShortLe(wave, 2)
            writeShortLe(wave, 16)
            wave.writeBytes("data")
            writeIntLe(wave, dataLength)
        }
    }

    private fun writeIntLe(file: RandomAccessFile, value: Long) {
        file.write(value.toInt() and 0xff)
        file.write((value shr 8).toInt() and 0xff)
        file.write((value shr 16).toInt() and 0xff)
        file.write((value shr 24).toInt() and 0xff)
    }

    private fun writeShortLe(file: RandomAccessFile, value: Int) {
        file.write(value and 0xff)
        file.write((value shr 8) and 0xff)
    }
}
