package io.github.gvd1024.htaalarms.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class RemindTest {
    private val la = ZoneId.of("America/Los_Angeles")     // DST: 2026-03-08 02:00 → 03:00, 2026-11-01 02:00 → 01:00
    private fun at(s: String, z: ZoneId = la) = ZonedDateTime.of(LocalDateTime.parse(s), z).toInstant()

    @Test fun validity() {
        assertTrue(Remind.isValid("2026-11-14 17:00"))
        assertTrue(Remind.isValid("2028-02-29 23:59"))
        listOf("2026-02-30 10:00", "2026-11-14 24:00", "2026-11-14 7:00", "2026-11-14T17:00", "tomorrow", "", "2026-11-14 17:60", " 2026-11-14 17:00")
            .forEach { assertFalse(it, Remind.isValid(it)) }
    }

    @Test fun snooze() {
        assertEquals("2026-11-14 17:10", Remind.snooze("10m", "2026-11-14 17:00", at("2026-11-14T17:00:40"), la))
        assertEquals("2026-11-15 00:30", Remind.snooze("1h", "x", at("2026-11-14T23:30:05"), la))
        // tomorrow = the entry's time of day on tomorrow's date, also across both DST changes
        assertEquals("2026-03-08 09:00", Remind.snooze("tomorrow", "2026-03-07 09:00", at("2026-03-07T09:01"), la))
        assertEquals("2026-03-08 02:30", Remind.snooze("tomorrow", "2026-03-07 02:30", at("2026-03-07T02:31"), la))
        assertEquals("2026-11-01 01:30", Remind.snooze("tomorrow", "2026-10-31 01:30", at("2026-10-31T01:31"), la))
        // 1 hour across the fall-back hour counts real time (01:30 PDT + 1 h = 01:30 PST)
        val first0130 = ZonedDateTime.ofLocal(LocalDateTime.parse("2026-11-01T01:30"), la, java.time.ZoneOffset.ofHours(-7)).toInstant()
        assertEquals("2026-11-01 01:30", Remind.snooze("1h", "x", first0130, la))
        assertNull(Remind.snooze("nope", "x", Instant.EPOCH, la))
    }

    @Test fun ringTimeAcrossDst() {
        // 02:30 doesn't exist on 2026-03-08 → rings at 03:30 PDT (one hour later in wall time = the gap)
        assertEquals(at("2026-03-08T03:30").toEpochMilli(), Remind.epochMillis("2026-03-08 02:30", la))
        // 01:30 happens twice on 2026-11-01 → the first one (PDT)
        assertEquals(ZonedDateTime.ofLocal(LocalDateTime.parse("2026-11-01T01:30"), la, java.time.ZoneOffset.ofHours(-7)).toInstant().toEpochMilli(),
            Remind.epochMillis("2026-11-01 01:30", la))
        // a time-zone change: the same entry is a different instant (local time, no zone, as decided)
        assertEquals(3 * 3600_000L, Remind.epochMillis("2026-11-14 09:00", la)!! - Remind.epochMillis("2026-11-14 09:00", ZoneId.of("America/New_York"))!!)
    }

    @Test fun nextQuarter() {
        fun nq(s: String) = Remind.nextQuarter(ZonedDateTime.of(LocalDateTime.parse(s), la)).toLocalDateTime().toString()
        assertEquals("2026-11-14T10:15", nq("2026-11-14T10:00"))
        assertEquals("2026-11-14T10:15", nq("2026-11-14T10:00:01"))
        assertEquals("2026-11-14T10:15", nq("2026-11-14T10:14:59"))
        assertEquals("2026-11-14T11:00", nq("2026-11-14T10:45:00.001"))
        assertEquals("2026-11-15T00:00", nq("2026-11-14T23:59"))
        assertEquals("2026-03-08T03:00", nq("2026-03-08T01:50"))      // spring forward: 01:50 PST → 03:00 PDT (10 min later)
        val fb = Remind.nextQuarter(ZonedDateTime.ofLocal(LocalDateTime.parse("2026-11-01T01:50"), la, java.time.ZoneOffset.ofHours(-7)))
        assertEquals("2026-11-01T01:00-08:00", fb.toOffsetDateTime().toString())   // fall back: 10 min later is 01:00 PST
    }

    @Test fun repeatsAndStatus() {
        assertTrue(Remind.repeats("daily", "2026-11-14"))
        assertFalse(Remind.repeats("daily", ""))
        assertFalse(Remind.repeats("", "2026-11-14"))
        assertTrue(Remind.ringable("open") && Remind.ringable("active"))
        listOf("done", "archived", "doing", "").forEach { assertFalse(Remind.ringable(it)) }
    }
}
