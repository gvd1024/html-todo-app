package io.github.gvd1024.htaalarms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

internal val worker = Executors.newCachedThreadPool()   // checks are serialized by Checker; a button never waits behind a long check

/** Runs [fn] on the worker thread while the broadcast is kept alive (goAsync), with a time limit. */
internal fun BroadcastReceiver.async(fn: () -> Unit) {
    val pending = goAsync()
    val f = worker.submit(Runnable { try { fn() } catch (e: Exception) { android.util.Log.w("HTAAlarms", "background: ${e.javaClass.simpleName}") } })
    Thread { try { f.get(25, TimeUnit.SECONDS) } catch (e: Exception) { } finally { pending.finish() } }.start()
}

/** The quarter-hour check, the handoff from HTA, and "check now". */
class CheckReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) { async { Checker.check(ctx, intent.getStringExtra("why") ?: "quarter hour") } }
    companion object { const val ACTION = "io.github.gvd1024.htaalarms.CHECK" }
}

/** Boot, clock or time-zone change, app update: re-arm everything (alarms are lost on reboot; times move with the zone). */
class SystemReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        async { Scheduler.replan(ctx); Checker.check(ctx, intent.action?.substringAfterLast('.') ?: "system") }
    }
}

/** A reminder's alarm went off: ring it (unless it was answered or removed meanwhile). */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val key = intent.getStringExtra("key") ?: return
        RingService.start(ctx, key, intent.getBooleanExtra("late", false))
    }
    companion object { const val ACTION = "io.github.gvd1024.htaalarms.REMIND." }
}

/** The buttons on the ringing and "Missed" notifications. */
class ActionReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val key = intent.getStringExtra("key") ?: return
        val kind = intent.getStringExtra("kind") ?: return
        async { Actions.answer(ctx, key, kind, null) }
    }
}
