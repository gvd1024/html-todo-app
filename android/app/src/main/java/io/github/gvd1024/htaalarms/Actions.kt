package io.github.gvd1024.htaalarms

import android.content.Context
import io.github.gvd1024.htaalarms.core.Reminder
import io.github.gvd1024.htaalarms.core.Remind
import io.github.gvd1024.htaalarms.core.WriteBack
import java.time.Instant
import java.time.ZoneId

/**
 * Dismiss / Snooze / Reschedule one reminder (R2-22). A task that doesn't repeat: the entry is removed or replaced in
 * the task file (line-level edit, If-Match; on 412 re-read once; gone elsewhere → just stop). A repeating task: its
 * reminders are a schedule that moves with the due date, so the answer stays on this phone (same rule as HTA).
 * Offline or signed out: the answer is kept on this phone and the file is left as it is (said in the result).
 */
object Actions {
    /** kind: dismiss | 10m | 1h | tomorrow | at (with [to] = "YYYY-MM-DD HH:MM"). → a short message for the screen. */
    fun answer(ctx: Context, key: String, kind: String, to0: String?): String {
        RingService.stopKey(ctx, key)
        Notify.cancelMissed(ctx, key)
        if (key.startsWith("test|")) { State.edit(ctx) { it.tests.remove(key) }; Scheduler.replan(ctx); return "Test reminder done" }
        val st = State.load(ctx)
        val r = find(st, key) ?: run { Scheduler.replan(ctx); return "That reminder is gone (changed elsewhere)." }
        val zone = ZoneId.systemDefault()
        val to = when (kind) { "dismiss" -> null; "at" -> to0; else -> Remind.snooze(kind, r.entry, Instant.now(), zone) }
        if (kind != "dismiss" && (to == null || !Remind.isValid(to))) return "Not a valid time."
        val local = { why: String ->
            State.edit(ctx) { s -> s.rung[key] = System.currentTimeMillis(); if (to != null) s.snoozed[key] = Remind.epochMillis(to, zone)!! else s.snoozed.remove(key) }
            Scheduler.replan(ctx); why
        }
        if (r.repeats) return local(if (to == null) "Dismissed — it comes back with the next repeat." else "Snoozed on this phone.")
        if (st.folderFormat > Checker.KNOWN_FORMAT) return local("This folder is from a newer HTA (format ${st.folderFormat}): changed on this phone only.")
        val res = try { WriteBack.edit(Graph { Auth.token(ctx) }, r.itemId, r.path, r.entry, to) }
            catch (e: Auth.SignInNeeded) { return local("Sign-in needed: changed on this phone only.") }
            catch (e: Exception) { return local("No connection: changed on this phone only.") }
        return when (res) {
            WriteBack.Result.WRITTEN -> { State.edit(ctx) { it.rung[key] = System.currentTimeMillis() }; Checker.check(ctx, "after $kind"); if (to == null) "Dismissed" else "Moved to $to" }
            WriteBack.Result.GONE -> { Checker.check(ctx, "gone"); "It was already changed elsewhere." }
            WriteBack.Result.REFUSED -> local("The task file can't be edited safely (check it in HTA): changed on this phone only.")
            WriteBack.Result.CONFLICT -> local("The task keeps changing elsewhere: changed on this phone only.")
        }
    }

    fun find(st: State, key: String): Reminder? = st.index.values.asSequence().flatMap { it.reminders() }.firstOrNull { it.key == key }
}
