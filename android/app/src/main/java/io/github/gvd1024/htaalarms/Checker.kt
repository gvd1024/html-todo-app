package io.github.gvd1024.htaalarms

import android.content.Context
import android.util.Log
import io.github.gvd1024.htaalarms.core.DeltaState
import io.github.gvd1024.htaalarms.core.Frontmatter
import io.github.gvd1024.htaalarms.core.IndexEntry
import org.json.JSONObject

/**
 * One check (R2-22): arm the next quarter-hour check first (so a failure never breaks the chain), then read the task
 * folder's change feed, download only the task files that changed, update the index, and re-plan every alarm.
 * Offline or signed out, the alarms already planned stay and ring.
 */
object Checker {
    private const val TAG = "HTAAlarms"
    private val running = Any()

    /**
     * [budgetMs]: how long downloads may take. A broadcast has ~25 s, so a big first read (every task file) is done in
     * parts: progress is saved, and a follow-up check is set for a minute later. A file is read again only when its
     * cTag (content tag) differs from the one in the index, so nothing seen but unread is ever skipped.
     */
    fun check(ctx: Context, reason: String, budgetMs: Long = 18_000): String = synchronized(running) {
        Scheduler.armNextCheck(ctx)
        val settings = Settings(ctx)
        val now = System.currentTimeMillis()
        var result: String
        var more = false
        try {
            val graph = Graph { Auth.token(ctx) }
            var st = State.load(ctx)
            if (st.folder != settings.folder) {          // another folder: start from scratch (the alarms are re-planned below)
                st = State().also { it.rung.putAll(st.rung); it.snoozed.putAll(st.snoozed); it.ids.putAll(st.ids); it.tests.putAll(st.tests) }
                st.folder = settings.folder
            }
            if (st.delta.rootId == null) { st.delta = DeltaState(graph.folderId(settings.folder)); st.deltaLink = null }
            val page = try { graph.delta(st.delta.rootId!!, st.deltaLink) } catch (e: Graph.HttpError) {
                if (e.code != 410 && e.code != 404) throw e
                st.delta = DeltaState(graph.folderId(settings.folder)); graph.delta(st.delta.rootId!!, null)   // feed reset (or the folder was replaced): start over
            }
            val (changed, _) = st.delta.apply(page.items)
            st.deltaLink = page.deltaLink ?: st.deltaLink
            // the index follows the feed: drop what's gone or out of reach, re-path renamed folders, list what to read
            val toRead = mutableListOf<Pair<String, String>>()
            st.index.keys.retainAll(st.delta.files.keys)
            for ((id, f) in st.delta.files) {
                val path = st.delta.pathOf(id)
                if (path == "_todo.json") { if (id in changed || st.folderFormat == 0) readFormat(graph, id, st); continue }
                if (path == null || !DeltaState.isTaskPath(path)) { st.index.remove(id); continue }
                val old = st.index[id]
                if (old != null && old.cTag == f.cTag) { if (old.path != path) st.index[id] = old.copy(path = path); continue }
                toRead.add(id to path)
            }
            val deadline = System.currentTimeMillis() + budgetMs
            val files = st.delta.files.toMap()
            val pool = java.util.concurrent.Executors.newFixedThreadPool(4)
            val read = java.util.concurrent.ConcurrentHashMap<String, IndexEntry>()
            try {
                val jobs = toRead.map { (id, path) -> pool.submit(Runnable {
                    if (System.currentTimeMillis() > deadline) return@Runnable
                    val f = files[id] ?: return@Runnable
                    try { read[id] = IndexEntry(id, path, f.eTag, f.cTag, Frontmatter.readTask(path, graph.content(id))) }
                    catch (e: Exception) { Log.w(TAG, "read failed: ${e.javaClass.simpleName}") }
                }) }
                jobs.forEach { try { it.get() } catch (e: Exception) { } }
            } finally { pool.shutdownNow() }
            st.index.putAll(read)
            more = read.size < toRead.size
            st.lastOk = now; st.lastError = if (more) "Still reading: ${toRead.size - read.size} task files left" else ""; st.signInNeeded = false
            st.lastCheck = now
            State.edit(ctx) { cur -> mergeInto(cur, st) }
            result = "ok ($reason): ${page.items.size} changes, ${read.size} read" + if (more) ", ${toRead.size - read.size} left" else ""
        } catch (e: Auth.SignInNeeded) {
            State.edit(ctx) { it.lastCheck = now; it.signInNeeded = true; it.lastError = "Sign-in needed: ${e.message}" }
            Notify.signInNeeded(ctx)
            result = "sign-in needed"
        } catch (e: Exception) {
            val msg = if (e is Graph.HttpError) "OneDrive answered ${e.code}" else "No connection (${e.javaClass.simpleName})"
            State.edit(ctx) { it.lastCheck = now; it.lastError = msg }
            result = "failed: $msg"
        }
        Scheduler.replan(ctx)
        if (more) Scheduler.armFollowUp(ctx)
        Log.i(TAG, "check $result")
        result
    }

    /** Keep what other parts changed meanwhile (rung, snoozes, test alarms, ids); take the folder data from the check. */
    private fun mergeInto(cur: State, st: State) {
        cur.folder = st.folder; cur.deltaLink = st.deltaLink; cur.delta = st.delta
        cur.index.clear(); cur.index.putAll(st.index)
        cur.folderFormat = st.folderFormat; cur.lastOk = st.lastOk; cur.lastCheck = st.lastCheck
        cur.lastError = st.lastError; cur.signInNeeded = st.signInNeeded
    }

    private fun readFormat(graph: Graph, id: String, st: State) {
        try { st.folderFormat = JSONObject(graph.content(id)).optInt("format", 0) } catch (e: Exception) { }
    }

    /** HTA's format check: a folder from a newer HTA (format > 5) is never written to (alarms still ring). */
    const val KNOWN_FORMAT = 5
}
