package io.github.gvd1024.htaalarms

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import io.github.gvd1024.htaalarms.core.Reminder

/** Notification channels and the notifications HTA Alarms posts. */
object Notify {
    const val CH_RING = "ring"          // the ringing alarm (full-screen, category ALARM; the voice is the sound)
    const val CH_MISSED = "missed"      // "Missed: …" after 3 minutes without an answer
    const val CH_STATUS = "status"      // sign-in needed
    const val RING_ID = 1
    const val SIGNIN_ID = 2

    fun channels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_RING, "Ringing reminders", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "A reminder that is speaking now"; setSound(null, null); enableVibration(true); setBypassDnd(true) })
        nm.createNotificationChannel(NotificationChannel(CH_MISSED, "Missed reminders", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Reminders nobody answered within 3 minutes" })
        nm.createNotificationChannel(NotificationChannel(CH_STATUS, "Status", NotificationManager.IMPORTANCE_DEFAULT).apply {
            description = "Sign-in needed and other problems" })
    }

    fun action(ctx: Context, key: String, kind: String, label: String, code: Int): Notification.Action {
        val i = Intent(ctx, ActionReceiver::class.java).setAction("act.$kind.$code").putExtra("key", key).putExtra("kind", kind)
        val pi = PendingIntent.getBroadcast(ctx, code, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Action.Builder(null as android.graphics.drawable.Icon?, label, pi).build()
    }

    private fun missedId(key: String) = 1000 + (key.hashCode() and 0xfffff)

    /** Persistent until answered; tap → HTA Alarms with this reminder's buttons. */
    fun missed(ctx: Context, key: String, text: String, title: String, entry: String) {
        val id = missedId(key)
        val open = PendingIntent.getActivity(ctx, id, Intent(ctx, MainActivity::class.java).putExtra("key", key).setAction("missed.$id"),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(ctx, CH_MISSED).setSmallIcon(R.drawable.ic_bell)
            .setContentTitle("Missed: $text").setContentText(if (title != text) "$title · $entry" else entry)
            .setCategory(Notification.CATEGORY_REMINDER).setOngoing(true).setAutoCancel(false).setContentIntent(open)
            .addAction(action(ctx, key, "dismiss", "Dismiss", id * 4))
            .addAction(action(ctx, key, "10m", "Snooze 10 min", id * 4 + 1))
            .addAction(action(ctx, key, "1h", "1 hour", id * 4 + 2))
            .build()
        ctx.getSystemService(NotificationManager::class.java).notify(id, n)
    }

    fun cancelMissed(ctx: Context, key: String) = ctx.getSystemService(NotificationManager::class.java).cancel(missedId(key))

    fun signInNeeded(ctx: Context) {
        val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(ctx, CH_STATUS).setSmallIcon(R.drawable.ic_bell).setContentTitle("HTA Alarms: sign in again")
            .setContentText("New or changed reminders can't be read until you sign in. Alarms already set still ring.")
            .setContentIntent(open).setAutoCancel(true).setOnlyAlertOnce(true).build()
        ctx.getSystemService(NotificationManager::class.java).notify(SIGNIN_ID, n)
    }

    fun cancelSignIn(ctx: Context) = ctx.getSystemService(NotificationManager::class.java).cancel(SIGNIN_ID)

    fun reminderLine(r: Reminder) = r.speak
}
