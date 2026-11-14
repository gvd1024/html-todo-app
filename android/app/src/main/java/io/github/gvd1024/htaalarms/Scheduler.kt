package io.github.gvd1024.htaalarms

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import io.github.gvd1024.htaalarms.core.Planner
import io.github.gvd1024.htaalarms.core.Remind
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * Android alarms. Each reminder = one AlarmManager.setAlarmClock (exact to the minute, wakes the phone, exempt from
 * battery saving, ⏰ in the status bar) with a stable request code; reminders that are gone are cancelled.
 * The checks = setExactAndAllowWhileIdle at the next quarter hour (or an inexact one in battery mode).
 */
object Scheduler {
    const val CHECK_CODE = 1

    private fun am(ctx: Context) = ctx.getSystemService(AlarmManager::class.java)

    fun canExact(ctx: Context) = Build.VERSION.SDK_INT < 31 || am(ctx).canScheduleExactAlarms()

    fun armNextCheck(ctx: Context) {
        val next = Remind.nextQuarter(ZonedDateTime.now()).toInstant().toEpochMilli()
        val pi = PendingIntent.getBroadcast(ctx, CHECK_CODE, Intent(ctx, CheckReceiver::class.java).setAction(CheckReceiver.ACTION),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val am = am(ctx)
        if (Settings(ctx).mode == "exact" && canExact(ctx)) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next, pi)
        else am.setWindow(AlarmManager.RTC_WAKEUP, next, 10 * 60_000L, pi)     // battery mode: Android may batch it within 10 min
        State.edit(ctx) { it.nextCheck = next }
    }

    /** A big first read didn't finish within one check: carry on in a minute (replaces the quarter-hour alarm
     *  only if it's sooner; the next full check re-arms the quarter hour). */
    fun armFollowUp(ctx: Context) {
        val at = System.currentTimeMillis() + 60_000L
        val pi = PendingIntent.getBroadcast(ctx, CHECK_CODE + 1, Intent(ctx, CheckReceiver::class.java).setAction(CheckReceiver.ACTION + ".more").putExtra("why", "continue reading"),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        if (canExact(ctx)) am(ctx).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi) else am(ctx).set(AlarmManager.RTC_WAKEUP, at, pi)
    }

    private fun reminderIntent(ctx: Context, code: Int, key: String?, plan: Planner.Plan?): PendingIntent {
        val i = Intent(ctx, ReminderReceiver::class.java).setAction(ReminderReceiver.ACTION + code)
        if (key != null) i.putExtra("key", key)
        plan?.let { i.putExtra("late", it.late).putExtra("snoozed", it.snoozed) }
        return PendingIntent.getBroadcast(ctx, code, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    /** Plan every reminder from the index and set/cancel alarms to match. */
    fun replan(ctx: Context) {
        val now = System.currentTimeMillis()
        val zone = ZoneId.systemDefault()
        State.edit(ctx) { st ->
            // forget "rang here" notes and local snoozes for reminders that no longer exist (keeps the file small)
            val live = st.index.values.flatMap { it.reminders() }.map { it.key }.toSet()
            st.rung.keys.retainAll(live + st.tests.keys); st.snoozed.keys.retainAll(live)
            st.tests.entries.removeIf { it.value < now - 3600_000L }               // a test that never rang (phone off) is dropped after an hour
            val plans = Planner.plan(st.index.values, now, zone, st.rung.keys, st.snoozed)
            val ids = st.alarmIds
            val keys = plans.map { it.reminder.key }.toSet() + st.tests.keys
            for ((key, code) in ids.retain(keys)) am(ctx).cancel(reminderIntent(ctx, code, key, null))
            val show = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
            for (p in plans) setClock(ctx, ids.codeFor(p.reminder.key), p.atMillis, reminderIntent(ctx, ids.codeFor(p.reminder.key), p.reminder.key, p), show)
            for ((key, at) in st.tests) setClock(ctx, ids.codeFor(key), maxOf(at, now), reminderIntent(ctx, ids.codeFor(key), key, null), show)
        }
    }

    private fun setClock(ctx: Context, code: Int, at: Long, pi: PendingIntent, show: PendingIntent) {
        try { am(ctx).setAlarmClock(AlarmManager.AlarmClockInfo(at, show), pi) }
        catch (e: SecurityException) {                      // no exact-alarm permission: still try to ring, maybe late
            am(ctx).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
        }
    }

    /** "Speak a test reminder in 1 minute". */
    fun testAlarm(ctx: Context) {
        val key = "test|" + System.currentTimeMillis()
        State.edit(ctx) { it.tests[key] = System.currentTimeMillis() + 60_000L }
        replan(ctx)
    }
}
