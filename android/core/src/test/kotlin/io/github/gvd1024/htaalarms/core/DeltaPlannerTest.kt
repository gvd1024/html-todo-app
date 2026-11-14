package io.github.gvd1024.htaalarms.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class DeltaPlannerTest {
    private fun item(id: String, name: String?, parent: String?, folder: Boolean = false, deleted: Boolean = false, tag: String = "c1") =
        DeltaState.Item(id, name, parent, folder, deleted, "e-$tag", tag)

    @Test fun deltaBookkeeping() {
        val d = DeltaState("ROOT")
        val json = """{"value":[{"id":"ROOT","name":"HTML-ToDo-App","folder":{}},
            {"id":"F1","name":"Real Todo","folder":{"childCount":1},"parentReference":{"id":"ROOT"}},
            {"id":"A","name":"a.md","file":{},"eTag":"e1","cTag":"c1","parentReference":{"id":"ROOT"}},
            {"id":"B","name":"b.md","file":{},"eTag":"e1","cTag":"c1","parentReference":{"id":"F1"}},
            {"id":"T","name":".trash","folder":{},"parentReference":{"id":"ROOT"}},
            {"id":"X","name":"x.md","file":{},"eTag":"e1","cTag":"c1","parentReference":{"id":"T"}},
            {"id":"F2","name":"Deep","folder":{},"parentReference":{"id":"F1"}},
            {"id":"C","name":"c.md","file":{},"eTag":"e1","cTag":"c1","parentReference":{"id":"F2"}}],
            "@odata.deltaLink":"https://graph/delta?token=1"}"""
        val page = GraphJson.deltaPage(json)
        assertEquals("https://graph/delta?token=1", page.deltaLink)
        val (changed, gone) = d.apply(page.items)
        assertEquals(setOf("A", "B", "X", "C"), changed)
        assertTrue(gone.isEmpty())
        assertEquals("a.md", d.pathOf("A")); assertEquals("Real Todo/b.md", d.pathOf("B"))
        assertNull("inside .trash", d.pathOf("X")); assertNull("two levels down", d.pathOf("C"))
        // a folder renamed elsewhere: Graph sends only the folder; its files get the new path
        d.apply(listOf(item("F1", "Work", "ROOT", folder = true)))
        assertEquals("Work/b.md", d.pathOf("B"))
        // an unchanged file (same cTag, e.g. only metadata) isn't re-read; a content change is
        assertEquals(emptySet<String>(), d.apply(listOf(item("A", "a.md", "ROOT"))).first)
        assertEquals(setOf("A"), d.apply(listOf(item("A", "a.md", "ROOT", tag = "c2"))).first)
        // deleted: the file, and a deleted folder's files
        assertEquals(setOf("A"), d.apply(listOf(item("A", null, null, deleted = true))).second)
        assertEquals(setOf("B"), d.apply(listOf(item("F1", null, null, folder = true, deleted = true))).second)
    }

    @Test fun taskPaths() {
        listOf("a.md", "Real Todo/b.md", "x.MD").forEach { assertTrue(it, DeltaState.isTaskPath(it)) }
        listOf("_todo.json", "_x.md", ".hidden.md", "README.md", ".trash/a.md", "_sys/a.md", "a/b/c.md", "notes.txt").forEach { assertFalse(it, DeltaState.isTaskPath(it)) }
    }

    private val zone = ZoneId.of("Europe/London")
    private fun ms(s: String) = ZonedDateTime.of(LocalDateTime.parse(s), zone).toInstant().toEpochMilli()
    private fun task(id: String, remind: List<String>?, status: String = "open", repeat: String = "", due: String = "") =
        IndexEntry("I-$id", "$id.md", "e", "c", Frontmatter.Task(id, "Title $id", status, due, remind, "", repeat))

    @Test fun planner() {
        val now = ms("2026-11-14T12:00")
        val idx = listOf(
            task("fut", listOf("2026-11-14 17:00", "2026-11-14 17:00", "bad value")),
            task("late", listOf("2026-11-14 11:00")),
            task("justnow", listOf("2026-11-14 11:59")),
            task("rung", listOf("2026-11-14 10:00")),
            task("done", listOf("2026-11-14 17:00"), status = "done"),
            task("arch", listOf("2026-11-14 17:00"), status = "archived"),
            task("odd", null),
            task("same1", listOf("2026-11-14 18:00")), task("same2", listOf("2026-11-14 18:00")),
            task("snz", listOf("2026-11-14 09:00"), repeat = "daily", due = "2026-11-14"),
        )
        val rung = setOf("I-rung|2026-11-14 10:00", "I-snz|2026-11-14 09:00")
        val p = Planner.plan(idx, now, zone, rung, mapOf("I-snz|2026-11-14 09:00" to ms("2026-11-14T12:10")))
        val byKey = p.associateBy { it.reminder.key }
        assertEquals(ms("2026-11-14T17:00"), byKey["I-fut|2026-11-14 17:00"]!!.atMillis)
        assertEquals("duplicates and invalid entries are skipped", 1, p.count { it.reminder.taskId == "fut" })
        assertTrue("found past → rings now, late", byKey["I-late|2026-11-14 11:00"]!!.let { it.atMillis == now && it.late })
        assertFalse("a minute ago isn't 'late'", byKey["I-justnow|2026-11-14 11:59"]!!.late)
        assertNull("already rung here", byKey["I-rung|2026-11-14 10:00"])
        assertNull(byKey["I-done|2026-11-14 17:00"]); assertNull(byKey["I-arch|2026-11-14 17:00"])
        assertEquals("two at the same minute: both", 2, p.count { it.atMillis == ms("2026-11-14T18:00") })
        assertTrue("local snooze", byKey["I-snz|2026-11-14 09:00"]!!.let { it.snoozed && it.atMillis == ms("2026-11-14T12:10") && it.reminder.repeats })
        assertEquals(listOf("I-rung|2026-11-14 10:00"), Planner.missed(idx, now, zone, rung, mapOf("I-snz|2026-11-14 09:00" to 1L)).map { it.key })
        assertEquals("the title is spoken when there's no text", "Title fut", byKey["I-fut|2026-11-14 17:00"]!!.reminder.speak)
    }

    @Test fun alarmIds() {
        val ids = AlarmIds()
        val a = ids.codeFor("a"); val b = ids.codeFor("b")
        assertEquals(a, ids.codeFor("a")); assertTrue(a != b)
        assertEquals(mapOf("a" to a), ids.retain(setOf("b")))
        assertEquals(a, ids.codeFor("c"))      // freed codes are reused
    }
}
