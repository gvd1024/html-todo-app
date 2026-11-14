package io.github.gvd1024.htaalarms.core

/**
 * The task-file contract, line by line (R2-22; CLAUDE.md "Task file contract"). The same rules as HTA's
 * remindPatch/rpValue/rpScalar in app/index.html, proven byte for byte by tests/fixtures/frontmatter.
 *
 * Nothing here rewrites a file through a YAML library: reading picks out the few keys HTA Alarms needs, and the
 * only edit replaces the `remind:` line(s), keeping every other byte (key order, unknown keys, comments, quoting,
 * CRLF/LF, BOM, body).
 */
object Frontmatter {
    data class Line(val text: String, val eol: String)
    data class Token(val value: String, val raw: String)
    data class Key(val key: String, val start: Int, val end: Int, val rest: String)
    class Doc(val bom: String, val lines: MutableList<Line>, val close: Int, val keys: List<Key>) {
        val eol: String get() = lines[0].eol
        fun cont(k: Key): List<String> = (k.start + 1 until k.end).map { lines[it].text }
    }

    private val KEY = Regex("^([A-Za-z_][A-Za-z0-9_-]*)[ \\t]*:(?:[ \\t]|$)")
    private val FENCE = Regex("^---[ \\t]*$")
    private val COMMENT = Regex("(^|[ \\t])#.*$")
    private val BEFORE = listOf("id", "title", "status", "prefix", "collections", "parent", "order", "due")

    /** The file's lines with their own terminators (\n or \r\n); the last one may have none. */
    fun lines(text: String): MutableList<Line> {
        val out = mutableListOf<Line>()
        var i = 0
        while (i < text.length) {
            val j = text.indexOf('\n', i)
            if (j < 0) { out.add(Line(text.substring(i), "")); break }
            val line = text.substring(i, j)
            if (line.endsWith("\r")) out.add(Line(line.dropLast(1), "\r\n")) else out.add(Line(line, "\n"))
            i = j + 1
        }
        return out
    }

    /** The frontmatter's structure, or null when the file has none (no opening or no closing ---). */
    fun doc(text: String): Doc? {
        val bom = if (text.startsWith("\uFEFF")) "\uFEFF" else ""
        val lines = lines(if (bom.isNotEmpty()) text.substring(1) else text)
        if (lines.isEmpty() || !FENCE.matches(lines[0].text) || lines[0].eol.isEmpty()) return null
        var close = -1
        for (i in 1 until lines.size) if (FENCE.matches(lines[i].text)) { close = i; break }
        if (close < 0) return null
        val keys = mutableListOf<Key>()
        for (i in 1 until close) {
            val m = KEY.find(lines[i].text) ?: continue
            val rest = lines[i].text.substring(m.value.length)
            val emptyVal = COMMENT.replace(rest, "").isBlank()
            var j = i + 1
            while (j < close && lines[j].text.isNotEmpty() &&
                (lines[j].text[0] == ' ' || lines[j].text[0] == '\t' || (emptyVal && Regex("^-([ \\t]|$)").containsMatchIn(lines[j].text)))) j++
            keys.add(Key(m.groupValues[1], i, j, rest))
        }
        return Doc(bom, lines, close, keys)
    }

    /** One YAML scalar token → its value and raw text, or null when it isn't a simple scalar. */
    fun scalar(s0: String): Token? {
        val s = s0.trim()
        if (s.isEmpty()) return null
        if (s[0] == '"') {
            val v = StringBuilder(); var i = 1
            while (i < s.length) {
                val c = s[i]
                if (c == '"') break
                if (c == '\\') {
                    i++
                    val n = if (i < s.length) s[i] else return null
                    when (n) {
                        'u' -> { val h = s.substring(i + 1, minOf(i + 5, s.length)); if (!Regex("^[0-9a-fA-F]{4}$").matches(h)) return null; v.append(h.toInt(16).toChar()); i += 4 }
                        'n' -> v.append('\n'); 't' -> v.append('\t'); 'r' -> v.append('\r')
                        '"' -> v.append('"'); '\\' -> v.append('\\'); '/' -> v.append('/')
                        else -> return null
                    }
                } else v.append(c)
                i++
            }
            return if (i == s.length - 1) Token(v.toString(), s) else null
        }
        if (s[0] == '\'') {
            val v = StringBuilder(); var i = 1
            while (i < s.length) {
                if (s[i] == '\'') { if (i + 1 < s.length && s[i + 1] == '\'') { v.append('\''); i += 2; continue }; break }
                v.append(s[i]); i++
            }
            return if (i == s.length - 1) Token(v.toString(), s) else null
        }
        if ("[]{}&*!|>%@`".indexOf(s[0]) >= 0 || s.contains(": ")) return null
        return Token(s, s)
    }

    /** The value of a key: its line's rest + continuation lines → tokens ([] = empty/null), or null (not ours to read). */
    fun value(first: String, cont: List<String>): List<Token>? {
        val v = COMMENT.replace(first, "").trim()
        if (v.isEmpty() || v == "~" || v == "null") {
            if (cont.isEmpty()) return emptyList()
            val out = mutableListOf<Token>()
            for (l in cont) {
                val m = Regex("^[ \\t]*-(?:[ \\t]+(.*))?$").find(l) ?: return null
                out.add(scalar(COMMENT.replace(m.groupValues[1], "")) ?: return null)
            }
            return out
        }
        if (cont.isNotEmpty()) return null
        if (v == "[]") return emptyList()
        if (v[0] == '[') {
            if (!v.endsWith("]")) return null
            val inner = v.substring(1, v.length - 1)
            val items = mutableListOf<String>(); val cur = StringBuilder(); var q = 0.toChar()
            var i = 0
            while (i < inner.length) {
                val c = inner[i]
                if (q != 0.toChar()) {
                    cur.append(c)
                    if (c == q && !(q == '"' && i > 0 && inner[i - 1] == '\\')) {
                        if (q == '\'' && i + 1 < inner.length && inner[i + 1] == '\'') { cur.append(inner[i + 1]); i += 2; continue }
                        q = 0.toChar()
                    }
                    i++; continue
                }
                when (c) {
                    '"', '\'' -> { q = c; cur.append(c) }
                    '[', ']', '{', '}' -> return null
                    ',' -> { items.add(cur.toString()); cur.setLength(0) }
                    else -> cur.append(c)
                }
                i++
            }
            if (q != 0.toChar()) return null
            if (cur.isNotBlank() || items.isNotEmpty()) items.add(cur.toString())
            val out = mutableListOf<Token>()
            for (it in items) { if (it.isBlank()) continue; out.add(scalar(it) ?: return null) }
            return out
        }
        return scalar(v)?.let { listOf(it) }
    }

    private fun plainOk(v: String): Boolean =
        Regex("^[^\\s\\[\\]{}#&*!|>'\"%@`,-][^\\[\\]{},#]*$").matches(v) && !Regex(": |:$|\\s$").containsMatchIn(v) &&
            !Regex("^(null|~|true|false)$", RegexOption.IGNORE_CASE).matches(v)

    private fun quote(v: String) = "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\t", "\\t") + "\""

    /** Sorted, without duplicates (string order = time order for YYYY-MM-DD HH:MM). */
    fun norm(entries: List<String>): List<String> = entries.toSortedSet().toList()

    /**
     * The line-level edit of `remind:`. Returns the new text, or null when it can't be done safely (no frontmatter,
     * two remind keys, a value it can't read). Entries already in the file keep their raw text (quotes and all).
     */
    fun remindPatch(text: String, entries: List<String>): String? {
        val d = doc(text) ?: return null
        val rk = d.keys.filter { it.key == "remind" }
        if (rk.size > 1) return null
        val old = if (rk.isNotEmpty()) value(rk[0].rest, d.cont(rk[0])) ?: return null else emptyList()
        val rawOf = old.associate { it.value to it.raw }
        val toks = norm(entries).map { v -> rawOf[v] ?: if (plainOk(v)) v else quote(v) }
        val lines = d.lines
        val out = if (toks.isEmpty()) emptyList() else listOf(
            Line("remind: " + if (toks.size == 1) toks[0] else toks.joinToString(", ", "[", "]"),
                if (rk.isNotEmpty()) lines[rk[0].end - 1].eol.ifEmpty { d.eol } else d.eol))
        val at: Int; var del = 0
        if (rk.isNotEmpty()) { at = rk[0].start; del = rk[0].end - rk[0].start }
        else {
            if (out.isEmpty()) return d.bom + lines.joinToString("") { it.text + it.eol }
            val due = d.keys.firstOrNull { it.key == "due" }
            val before = d.keys.lastOrNull { it.key in BEFORE }
            at = (due ?: before)?.end ?: d.close
        }
        repeat(del) { lines.removeAt(at) }
        lines.addAll(at, out)
        return d.bom + lines.joinToString("") { it.text + it.eol }
    }

    /** What HTA Alarms needs from a task file. `remind` is null when the value can't be read (never rings, ⚠ in HTA). */
    data class Task(
        val id: String, val title: String, val status: String, val due: String,
        val remind: List<String>?, val remindText: String, val repeat: String,
    )

    fun titleFromName(path: String): String {
        val base = path.substringAfterLast('/').removeSuffix(".md").replace(Regex("[-_]+"), " ")
        return base.replaceFirstChar { if (it.isLetterOrDigit() && it.isLowerCase()) it.uppercaseChar() else it }
    }

    /** null = not a task HTA Alarms can read (no frontmatter, or a key written twice, which HTA opens read-only). */
    fun readTask(path: String, text: String): Task? {
        val d = doc(text) ?: return null
        if (d.keys.groupBy { it.key }.any { it.value.size > 1 }) return null
        fun one(k: String): String? {
            val key = d.keys.firstOrNull { it.key == k } ?: return null
            val v = value(key.rest, d.cont(key)) ?: return null
            return if (v.size == 1) v[0].value else null
        }
        val rk = d.keys.firstOrNull { it.key == "remind" }
        val remind = if (rk == null) emptyList() else value(rk.rest, d.cont(rk))?.map { it.value }
        return Task(
            id = one("id")?.takeIf { it.isNotEmpty() } ?: ("f-" + path.removeSuffix(".md")),
            title = one("title") ?: titleFromName(path),
            status = one("status")?.takeIf { it.isNotEmpty() } ?: "open",
            due = one("due") ?: "",
            remind = remind,
            remindText = one("remind_text") ?: "",
            repeat = one("repeat") ?: "",
        )
    }
}
