package io.github.gvd1024.htaalarms

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import io.github.gvd1024.htaalarms.core.Remind
import java.time.ZoneId

/**
 * The ringing (R2-22): a foreground service that speaks the reminder text (or the title) with Android's
 * text-to-speech on the ALARM stream (it plays in silent mode, at the alarm volume), pauses about 4 s, and repeats
 * for 3 minutes. Several due at once are spoken one after another, and the ringing screen lists them all. After 3
 * minutes without an answer it stops and leaves a persistent "Missed: …" notification for each.
 *
 * Foreground-service type: mediaPlayback — the service's whole job is audible playback that the user expects
 * (Android 14+ needs a declared type; shortService has a 3-minute timeout, which is the ringing time itself, and
 * specialUse is meant for the Play Store's review). An exact alarm (setAlarmClock) lets it start from the background.
 */
class RingService : Service() {
    data class Ringing(val key: String, val text: String, val title: String, val entry: String, val late: Boolean)

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var started = 0L
    private var wake: PowerManager.WakeLock? = null
    private var focus: AudioFocusRequest? = null
    private val attrs = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_RING -> {
                // started with startForegroundService: go foreground at once, whatever happens next
                startForeground(Notify.RING_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
                val key = intent.getStringExtra("key")
                val r = key?.let { describe(it, intent.getBooleanExtra("late", false)) }
                if (r == null) { if (queue.isEmpty()) finishAll(false); return START_NOT_STICKY }
                if (queue.none { it.key == key }) queue.add(r)
                State.edit(this) { it.rung[r.key] = System.currentTimeMillis() }     // never rings twice for the same entry
                if (started == 0L) begin()
                showScreen()
            }
            ACTION_STOP_KEY -> { val key = intent.getStringExtra("key"); queue.removeAll { it.key == key }; if (queue.isEmpty()) finishAll(false) else refresh() }
            else -> if (queue.isEmpty()) stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun describe(key: String, late: Boolean): Ringing? {
        if (key.startsWith("test|")) return Ringing(key, "This is a test reminder from HTA Alarms.", "Test reminder", "now", false)
        val st = State.load(this)
        val r = Actions.find(st, key) ?: return null                         // answered, changed or deleted meanwhile
        return Ringing(key, r.speak, r.title, r.entry, late)
    }

    private fun begin() {
        started = System.currentTimeMillis()
        wake = getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "HTAAlarms:ring").apply { acquire(RING_MS + 30_000) }
        val am = getSystemService(AudioManager::class.java)
        focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT).setAudioAttributes(attrs).build().also { am.requestAudioFocus(it) }
        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) {
                tts?.setAudioAttributes(attrs)
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(id: String?) {}
                    override fun onDone(id: String?) { if (id == LAST) handler.postDelayed({ speakRound() }, PAUSE_MS) }
                    @Deprecated("old API") override fun onError(id: String?) { if (id == LAST) handler.postDelayed({ speakRound() }, PAUSE_MS) }
                })
                speakRound()
            } else {
                handler.postDelayed({ finishAll(true) }, RING_MS)            // no voice engine: the screen and notification still show
            }
        }
        handler.postDelayed({ finishAll(true) }, RING_MS)
    }

    private fun speakRound() {
        if (queue.isEmpty() || System.currentTimeMillis() - started >= RING_MS) return
        val t = tts ?: return
        queue.forEachIndexed { i, r ->
            val p = Bundle().apply { putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_ALARM) }
            t.speak(r.text, if (i == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD, p, if (i == queue.size - 1) LAST else "r$i")
        }
    }

    private fun notification(): Notification {
        val first = queue.firstOrNull()
        val screen = PendingIntent.getActivity(this, 0, Intent(this, RingActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val b = Notification.Builder(this, Notify.CH_RING).setSmallIcon(R.drawable.ic_bell)
            .setContentTitle(first?.text ?: "Reminder").setContentText(if (queue.size > 1) "+${queue.size - 1} more" else first?.title ?: "")
            .setCategory(Notification.CATEGORY_ALARM).setOngoing(true).setFullScreenIntent(screen, true).setContentIntent(screen)
        if (first != null) {
            b.addAction(Notify.action(this, first.key, "dismiss", "Dismiss", 11))
            b.addAction(Notify.action(this, first.key, "10m", "Snooze 10 min", 12))
        }
        return b.build()
    }

    private fun refresh() {
        getSystemService(android.app.NotificationManager::class.java).notify(Notify.RING_ID, notification())
        RingActivity.refresh?.invoke()
    }

    private fun showScreen() {
        refresh()
        // the full-screen intent opens it over the lock screen; when the phone is in use Android shows a heads-up
        // notification instead, so also try to open it directly (allowed while an alarm is ringing)
        try { startActivity(Intent(this, RingActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (e: Exception) { }
    }

    /** missed = true: 3 minutes passed without an answer → "Missed: …" for each, then stop. */
    private fun finishAll(missed: Boolean) {
        if (missed) for (r in queue) if (!r.key.startsWith("test|")) Notify.missed(this, r.key, r.text, r.title, r.entry)
        queue.clear()
        handler.removeCallbacksAndMessages(null)
        tts?.stop(); tts?.shutdown(); tts = null
        focus?.let { getSystemService(AudioManager::class.java).abandonAudioFocusRequest(it) }
        wake?.let { if (it.isHeld) it.release() }
        started = 0L
        RingActivity.refresh?.invoke()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() { if (started != 0L) finishAll(false); super.onDestroy() }

    companion object {
        const val ACTION_RING = "ring"
        const val ACTION_STOP_KEY = "stopKey"
        const val RING_MS = 3 * 60_000L
        const val PAUSE_MS = 4_000L
        private const val LAST = "last"
        /** What is ringing now (read by the ringing screen). */
        val queue: MutableList<Ringing> = java.util.Collections.synchronizedList(mutableListOf())

        fun start(ctx: Context, key: String, late: Boolean) {
            ctx.startForegroundService(Intent(ctx, RingService::class.java).setAction(ACTION_RING).putExtra("key", key).putExtra("late", late))
        }

        fun stopKey(ctx: Context, key: String) {
            if (queue.none { it.key == key }) return
            ctx.startService(Intent(ctx, RingService::class.java).setAction(ACTION_STOP_KEY).putExtra("key", key))
        }

        fun lateText(r: Ringing) = if (r.late) " · late" else ""
        fun zone(): ZoneId = ZoneId.systemDefault()
        fun valid(s: String) = Remind.isValid(s)
    }
}
