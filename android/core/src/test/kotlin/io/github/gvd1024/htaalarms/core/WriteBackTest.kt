package io.github.gvd1024.htaalarms.core

import org.junit.Assert.assertEquals
import org.junit.Test

class WriteBackTest {
    /** A strict fake: every upload must carry the current eTag (like OneDrive's If-Match → 412). */
    class Fake(var text: String) : FileApi {
        var n = 1; var uploads = 0; var failNext = 0; var gone = false; var before: (() -> Unit)? = null
        override fun download(itemId: String): Pair<String, String> { if (gone) throw FileApi.NotFound(); return text to "e$n" }
        override fun upload(itemId: String, text: String, ifMatch: String): String {
            before?.invoke(); before = null
            if (gone) throw FileApi.NotFound()
            if (failNext > 0) { failNext--; n++; throw FileApi.PreconditionFailed() }
            if (ifMatch != "e$n") throw FileApi.PreconditionFailed()
            this.text = text; n++; uploads++; return "e$n"
        }
    }
    private val file = "---\r\nid: t-1\r\ntitle: Gate\r\nstatus: open\r\ndue: 2026-11-14\r\nremind: [2026-11-14 09:00, 2026-11-14 17:00]\r\nweird: [1, 2]\r\n---\r\nbody --- stays\r\n"

    @Test fun dismissAndSnooze() {
        val f = Fake(file)
        assertEquals(WriteBack.Result.WRITTEN, WriteBack.edit(f, "I", "gate.md", "2026-11-14 09:00", null))
        assertEquals(file.replace("[2026-11-14 09:00, 2026-11-14 17:00]", "2026-11-14 17:00"), f.text)
        assertEquals(WriteBack.Result.WRITTEN, WriteBack.edit(f, "I", "gate.md", "2026-11-14 17:00", "2026-11-14 17:10"))
        assertEquals(file.replace("[2026-11-14 09:00, 2026-11-14 17:00]", "2026-11-14 17:10"), f.text)
    }

    @Test fun conflictRetriesOnce() {
        val f = Fake(file); f.failNext = 1
        assertEquals(WriteBack.Result.WRITTEN, WriteBack.edit(f, "I", "gate.md", "2026-11-14 09:00", null))
        val g = Fake(file); g.failNext = 2
        assertEquals(WriteBack.Result.CONFLICT, WriteBack.edit(g, "I", "gate.md", "2026-11-14 09:00", null))
        assertEquals(file, g.text)
    }

    @Test fun changedElsewhereMeanwhile() {
        val f = Fake(file)
        f.before = { f.text = file.replace("remind: [2026-11-14 09:00, 2026-11-14 17:00]", "remind: 2026-11-14 17:00"); f.n++ }   // HTA dismissed it first
        assertEquals(WriteBack.Result.GONE, WriteBack.edit(f, "I", "gate.md", "2026-11-14 09:00", null))
        assertEquals(0, f.uploads)
        val d = Fake(file.replace("status: open", "status: done"))
        assertEquals("a task checked off elsewhere: just stop", WriteBack.Result.GONE, WriteBack.edit(d, "I", "gate.md", "2026-11-14 09:00", null))
        val g = Fake(file); g.gone = true
        assertEquals("a task deleted while ringing", WriteBack.Result.GONE, WriteBack.edit(g, "I", "gate.md", "2026-11-14 09:00", null))
        val r = Fake(file.replace("weird:", "remind: 2026-11-15 10:00\r\nweird:"))
        assertEquals("two remind keys: never written", WriteBack.Result.REFUSED, WriteBack.edit(r, "I", "gate.md", "2026-11-14 09:00", null))
    }
}
