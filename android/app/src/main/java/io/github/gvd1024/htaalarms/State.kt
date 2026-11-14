package io.github.gvd1024.htaalarms

import android.content.Context
import io.github.gvd1024.htaalarms.core.AlarmIds
import io.github.gvd1024.htaalarms.core.DeltaState
import io.github.gvd1024.htaalarms.core.Frontmatter
import io.github.gvd1024.htaalarms.core.IndexEntry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Settings (SharedPreferences). No tokens here: MSAL keeps its own encrypted cache. */
class Settings(ctx: Context) {
    private val p = ctx.getSharedPreferences("settings", Context.MODE_PRIVATE)
    var folder: String
        get() = p.getString("folder", DEFAULT_FOLDER) ?: DEFAULT_FOLDER
        set(v) = p.edit().putString("folder", v.trim().trim('/').ifEmpty { DEFAULT_FOLDER }).apply()
    /** "exact" (default): a check as soon as possible after :00 :15 :30 :45. "battery": Android may batch it. */
    var mode: String
        get() = p.getString("mode", "exact") ?: "exact"
        set(v) = p.edit().putString("mode", v).apply()
    var account: String
        get() = p.getString("account", "") ?: ""
        set(v) = p.edit().putString("account", v).apply()

    companion object { const val DEFAULT_FOLDER = "HTML-ToDo-App" }
}

/**
 * Everything HTA Alarms remembers between checks, in one JSON file (files/state.json): the change-feed position,
 * folders and files by item id, the task index (only the fields it needs), which reminders already rang here, local
 * snoozes (repeating tasks), alarm request codes, and the status-panel facts.
 */
class State {
    var folder = ""
    var deltaLink: String? = null
    var delta = DeltaState()
    val index = mutableMapOf<String, IndexEntry>()        // file item id → entry
    val rung = mutableMapOf<String, Long>()                // reminder key → when it rang here
    val snoozed = mutableMapOf<String, Long>()             // reminder key → ring again at (epoch ms), this phone only
    val ids = mutableMapOf<String, Int>()                  // reminder key → alarm request code
    val tests = mutableMapOf<String, Long>()               // test alarm key → epoch ms
    var folderFormat = 0
    var lastCheck = 0L
    var lastOk = 0L
    var nextCheck = 0L
    var lastError = ""
    var signInNeeded = false

    val alarmIds get() = AlarmIds(ids)

    fun toJson(): JSONObject = JSONObject().apply {
        put("folder", folder); put("deltaLink", deltaLink ?: ""); put("rootId", delta.rootId ?: "")
        put("folders", JSONObject().apply { delta.folders.forEach { (k, v) -> put(k, JSONObject().put("name", v.name).put("parent", v.parentId ?: "")) } })
        put("files", JSONObject().apply { delta.files.forEach { (k, v) -> put(k, JSONObject().put("name", v.name).put("parent", v.parentId ?: "").put("eTag", v.eTag).put("cTag", v.cTag)) } })
        put("index", JSONObject().apply { index.forEach { (k, e) -> put(k, entryJson(e)) } })
        put("rung", JSONObject(rung as Map<*, *>)); put("snoozed", JSONObject(snoozed as Map<*, *>)); put("ids", JSONObject(ids as Map<*, *>)); put("tests", JSONObject(tests as Map<*, *>))
        put("folderFormat", folderFormat); put("lastCheck", lastCheck); put("lastOk", lastOk); put("nextCheck", nextCheck)
        put("lastError", lastError); put("signInNeeded", signInNeeded)
    }

    private fun entryJson(e: IndexEntry) = JSONObject().apply {
        put("path", e.path); put("eTag", e.eTag); put("cTag", e.cTag)
        e.task?.let { t ->
            put("task", JSONObject().put("id", t.id).put("title", t.title).put("status", t.status).put("due", t.due)
                .put("remind", t.remind?.let { JSONArray(it) } ?: JSONObject.NULL).put("remindText", t.remindText).put("repeat", t.repeat))
        }
    }

    companion object {
        private fun file(ctx: Context) = File(ctx.filesDir, "state.json")
        private val lock = Any()

        fun load(ctx: Context): State = synchronized(lock) {
            val s = State()
            val f = file(ctx)
            if (!f.exists()) return s
            try {
                val o = JSONObject(f.readText())
                s.folder = o.optString("folder"); s.deltaLink = o.optString("deltaLink").ifEmpty { null }
                s.delta = DeltaState(o.optString("rootId").ifEmpty { null })
                o.optJSONObject("folders")?.let { fo -> fo.keys().forEach { k -> val v = fo.getJSONObject(k); s.delta.folders[k] = DeltaState.Folder(v.optString("name"), v.optString("parent").ifEmpty { null }) } }
                o.optJSONObject("files")?.let { fo -> fo.keys().forEach { k -> val v = fo.getJSONObject(k); s.delta.files[k] = DeltaState.File(v.optString("name"), v.optString("parent").ifEmpty { null }, v.optString("eTag"), v.optString("cTag")) } }
                o.optJSONObject("index")?.let { io -> io.keys().forEach { k ->
                    val v = io.getJSONObject(k); val t = v.optJSONObject("task")
                    val task = t?.let {
                        val r = it.opt("remind")
                        Frontmatter.Task(it.optString("id"), it.optString("title"), it.optString("status"), it.optString("due"),
                            if (r is JSONArray) (0 until r.length()).map { i -> r.getString(i) } else null, it.optString("remindText"), it.optString("repeat"))
                    }
                    s.index[k] = IndexEntry(k, v.optString("path"), v.optString("eTag"), v.optString("cTag"), task)
                } }
                fun longs(name: String, into: MutableMap<String, Long>) = o.optJSONObject(name)?.let { m -> m.keys().forEach { k -> into[k] = m.getLong(k) } }
                longs("rung", s.rung); longs("snoozed", s.snoozed); longs("tests", s.tests)
                o.optJSONObject("ids")?.let { m -> m.keys().forEach { k -> s.ids[k] = m.getInt(k) } }
                s.folderFormat = o.optInt("folderFormat"); s.lastCheck = o.optLong("lastCheck"); s.lastOk = o.optLong("lastOk"); s.nextCheck = o.optLong("nextCheck")
                s.lastError = o.optString("lastError"); s.signInNeeded = o.optBoolean("signInNeeded")
            } catch (e: Exception) {
                android.util.Log.w("HTAAlarms", "state unreadable, starting fresh: ${e.javaClass.simpleName}")
            }
            s
        }

        fun save(ctx: Context, s: State) = synchronized(lock) {
            val f = file(ctx); val tmp = File(f.parentFile, "state.json.tmp")
            tmp.writeText(s.toJson().toString()); tmp.renameTo(f)
        }

        /** Load, change, save, under one lock (the checker, the ringing service and the buttons all touch it). */
        fun <T> edit(ctx: Context, fn: (State) -> T): T = synchronized(lock) { val s = load(ctx); val r = fn(s); save(ctx, s); r }
    }
}
