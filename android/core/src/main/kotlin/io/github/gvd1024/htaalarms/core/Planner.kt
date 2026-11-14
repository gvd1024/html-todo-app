package io.github.gvd1024.htaalarms.core

import java.time.ZoneId

/** One reminder that HTA Alarms knows about: a task file's entry. key = "<file item id>|<entry>". */
data class Reminder(val itemId: String, val path: String, val taskId: String, val title: String, val text: String, val entry: String, val repeats: Boolean) {
    val key get() = "$itemId|$entry"
    val speak get() = text.ifBlank { title }
}

/** What the local index holds for one task file. */
data class IndexEntry(val itemId: String, val path: String, val eTag: String, val cTag: String, val task: Frontmatter.Task?) {
    fun reminders(): List<Reminder> {
        val t = task ?: return emptyList()
        if (!Remind.ringable(t.status)) return emptyList()
        val rep = Remind.repeats(t.repeat, t.due)
        return (t.remind ?: emptyList()).filter { Remind.isValid(it) }.distinct()
            .map { Reminder(itemId, path, t.id, t.title, t.remindText, it, rep) }
    }
}

/**
 * Decides what to schedule. [rung] = keys that already rang (or were answered) on this phone; [snoozed] = local
 * snoozes (repeating tasks) key → epoch ms.
 */
object Planner {
    data class Plan(val reminder: Reminder, val atMillis: Long, val late: Boolean, val snoozed: Boolean)

    fun plan(index: Collection<IndexEntry>, nowMillis: Long, zone: ZoneId, rung: Set<String>, snoozed: Map<String, Long>): List<Plan> {
        val out = mutableListOf<Plan>()
        for (r in all(index)) {
            val at = Remind.epochMillis(r.entry, zone) ?: continue
            val z = snoozed[r.key]
            when {
                z != null -> out.add(Plan(r, maxOf(z, nowMillis), false, true))
                r.key in rung -> {}                                   // rang or answered on this phone already
                at > nowMillis -> out.add(Plan(r, at, false, false))
                nowMillis - at > LATE_LIMIT_MS -> {}                  // more than a day old: listed as missed, never rung late
                else -> out.add(Plan(r, nowMillis, nowMillis - at > 2 * 60_000, false))   // found already past: ring at once, "late"
            }
        }
        return out.sortedBy { it.atMillis }
    }

    /** Missed = past, already rung here, not snoozed (the status list shows these with their buttons). */
    fun missed(index: Collection<IndexEntry>, nowMillis: Long, zone: ZoneId, rung: Set<String>, snoozed: Map<String, Long>) =
        all(index).filter { r -> val at = Remind.epochMillis(r.entry, zone)
            at != null && at <= nowMillis && r.key !in snoozed && (r.key in rung || nowMillis - at > LATE_LIMIT_MS) }

    /** A reminder found past rings late only within a day (HTA's popup has the same limit); older ones are just missed. */
    const val LATE_LIMIT_MS = 24 * 3600_000L

    /** Every reminder once: two files with the same task id (a conflict copy) ring once, like HTA (it flags the twin ⚠). */
    private fun all(index: Collection<IndexEntry>) =
        index.sortedBy { it.path }.flatMap { it.reminders() }.distinctBy { it.taskId + "|" + it.entry }
}

/** Stable alarm request codes: one per reminder key, kept across restarts; codes of keys that are gone are freed. */
class AlarmIds(private val map: MutableMap<String, Int> = mutableMapOf()) {
    fun codeFor(key: String): Int = map.getOrPut(key) { var c = 1000; val used = map.values.toSet(); while (c in used) c++; c }
    fun retain(keys: Set<String>): Map<String, Int> { val gone = map.filterKeys { it !in keys }; gone.keys.forEach { map.remove(it) }; return gone }
    fun all(): Map<String, Int> = map.toMap()
}
