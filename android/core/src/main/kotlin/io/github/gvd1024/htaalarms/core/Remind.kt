package io.github.gvd1024.htaalarms.core

import java.time.DateTimeException
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit

/**
 * Reminder values and time math (R2-22). `remind:` entries are `YYYY-MM-DD HH:MM`, 24-hour, local time, no zone.
 * Same rules as HTA (isRemind, snoozeTo, remindRepeats in app/index.html).
 */
object Remind {
    private val RE = Regex("^(\\d{4})-(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2})$")
    private val YMD = Regex("^(\\d{4})-(\\d{2})-(\\d{2})$")

    fun parse(s: String): LocalDateTime? {
        val m = RE.matchEntire(s) ?: return null
        val (y, mo, d, h, mi) = m.destructured
        if (h.toInt() > 23 || mi.toInt() > 59) return null
        return try { LocalDateTime.of(y.toInt(), mo.toInt(), d.toInt(), h.toInt(), mi.toInt()) } catch (e: DateTimeException) { null }
    }

    fun isValid(s: String) = parse(s) != null

    fun isYmd(s: String): Boolean {
        val m = YMD.matchEntire(s) ?: return false
        return try { LocalDate.of(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt()); true } catch (e: DateTimeException) { false }
    }

    fun format(t: LocalDateTime): String = "%04d-%02d-%02d %02d:%02d".format(t.year, t.monthValue, t.dayOfMonth, t.hour, t.minute)

    /**
     * When an entry rings, as an instant in [zone]. A time that doesn't exist (the hour skipped when clocks go
     * forward) rings that many minutes later; a time that happens twice (clocks go back) rings the first time.
     */
    fun epochMillis(entry: String, zone: ZoneId): Long? = parse(entry)?.let { ZonedDateTime.of(it, zone).toInstant().toEpochMilli() }

    /** Snooze: "10m" / "1h" from now (whole minutes), "tomorrow" = the entry's time of day on tomorrow's calendar date. */
    fun snooze(kind: String, entry: String, now: Instant, zone: ZoneId): String? {
        val base = now.truncatedTo(ChronoUnit.MINUTES)
        return when (kind) {
            "10m" -> format(LocalDateTime.ofInstant(base.plus(10, ChronoUnit.MINUTES), zone))
            "1h" -> format(LocalDateTime.ofInstant(base.plus(60, ChronoUnit.MINUTES), zone))
            "tomorrow" -> {
                val today = LocalDate.ofInstant(now, zone)
                val tod = parse(entry)?.toLocalTime() ?: LocalDateTime.ofInstant(base, zone).toLocalTime()
                format(LocalDateTime.of(today.plusDays(1), tod))
            }
            else -> null
        }
    }

    /** The next quarter hour (:00 :15 :30 :45) strictly after [now], in local time. */
    fun nextQuarter(now: ZonedDateTime): ZonedDateTime {
        val hour = now.truncatedTo(ChronoUnit.HOURS)
        var n = hour.plusMinutes((now.minute - now.minute % 15).toLong())
        while (!n.isAfter(now)) n = n.plusMinutes(15)
        return n
    }

    /** Only open and active tasks ring (done, archived, deleted and unknown statuses never do). */
    fun ringable(status: String) = status == "open" || status == "active"

    /** A repeating task (a repeat phrase and a real due date): its reminders are a schedule that moves with the due
     *  date when HTA checks it off. Dismiss/Snooze there stay on this phone, so the schedule isn't destroyed. */
    fun repeats(repeat: String, due: String) = repeat.isNotBlank() && isYmd(due)
}
