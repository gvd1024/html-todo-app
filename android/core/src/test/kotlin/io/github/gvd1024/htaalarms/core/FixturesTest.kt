package io.github.gvd1024.htaalarms.core

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File

/** tests/fixtures/frontmatter: the same files and expected bytes as HTA's own test (run_tests.py, group r222). */
class FixturesTest {
    private val dir = File(System.getProperty("fixtures") ?: "../../tests/fixtures/frontmatter")
    private fun bytes(f: String) = File(dir, f).readBytes().toString(Charsets.UTF_8)
    private fun list(a: JSONArray?) = a?.let { (0 until it.length()).map { i -> it.getString(i) } }

    @Test fun everyCase() {
        val cases = JSONObject(bytes("cases.json")).getJSONArray("cases")
        var edits = 0
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val name = c.getString("name")
            val text = bytes(c.getString("file"))
            val p = c.getJSONObject("parsed")
            val unread = p.optBoolean("unreadable") || p.optBoolean("noFrontmatter")
            val t = Frontmatter.readTask(c.getString("file"), text)
            if (unread) assertNull("$name: not readable as a task", t)
            else {
                t!!
                assertEquals("$name id", p.getString("id"), t.id)
                assertEquals("$name title", p.getString("title"), t.title)
                assertEquals("$name status", p.getString("status"), t.status)
                assertEquals("$name due", p.getString("due"), t.due)
                assertEquals("$name repeat", p.getString("repeat"), t.repeat)
                assertEquals("$name remind_text", p.getString("remind_text"), t.remindText)
                val want = if (p.has("remindLine")) list(p.optJSONArray("remindLine")) else list(p.getJSONArray("remind"))
                assertEquals("$name remind", want, t.remind)
            }
            val es = c.getJSONArray("edits")
            for (k in 0 until es.length()) {
                val e = es.getJSONObject(k)
                val cur = if (unread) emptyList() else (t!!.remind ?: list(p.getJSONArray("remind"))!!)
                val op = e.getString("op")
                val got: String? = if (!unread && op != "add" && e.getString("entry") !in cur) "gone" else {
                    val next = when (op) {
                        "remove" -> cur.filter { it != e.getString("entry") }
                        "replace" -> cur.filter { it != e.getString("entry") } + e.getString("to")
                        else -> cur + e.getString("to")
                    }
                    Frontmatter.remindPatch(text, next)
                }
                val want: String? = when {
                    e.isNull("expect") -> null
                    e.getString("expect") == "gone" -> "gone"
                    else -> bytes("expected/" + e.getString("expect"))
                }
                assertEquals("$name edit ${k + 1} ($op): byte-identical", want, got)
                edits++
            }
        }
        assert(edits >= 20) { "only $edits edits ran" }
    }
}
