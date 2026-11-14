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

    fun check(ctx: Context, reason: String): String = synchronized(running) {
        Scheduler.armNextCheck(ctx)
        val settings = Settings(ctx)
        val now = System.currentTimeMillis()
        var result: String
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
                st.delta = DeltaState(graph.folderId(settings.folder)); st.index.clear(); graph.delta(st.delta.rootId!!, null)   // feed reset (or the folder was replaced): start over
            }
            val (changed, gone) = st.delta.apply(page.items)
            gone.forEach { st.index.remove(it) }
            var reads = 0
            // files whose path changed (a folder renamed) keep their entry; only content changes are downloaded
            for ((id, f) in st.delta.files) {
                val path = st.delta.pathOf(id)
                if (path == null) { st.index.remove(id); continue }
                if (path == "_todo.json") { if (id in changed) readFormat(graph, id, st); continue }
                if (!DeltaState.isTaskPath(path)) { st.index.remove(id); continue }
                val old = st.index[id]
                if (old != null && id !in changed) { if (old.path != path) st.index[id] = old.copy(path = path); continue }
                if (old != null && old.cTag == f.cTag) { st.index[id] = old.copy(path = path); continue }
                val (text, eTag) = try { graph.download(id) } catch (e: Exception) { Log.w(TAG, "read failed: ${e.javaClass.simpleName}"); continue }
                st.index[id] = IndexEntry(id, path, eTag, f.cTag, Frontmatter.readTask(path, text))
                reads++
            }
            st.deltaLink = page.deltaLink ?: st.deltaLink
            st.lastOk = now; st.lastError = ""; st.signInNeeded = false
            st.lastCheck = now
            State.edit(ctx) { cur -> mergeInto(cur, st) }
            result = "ok ($reason): ${page.items.size} changes, $reads read"
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
        try { st.folderFormat = JSONObject(graph.download(id).first).optInt("format", 0) } catch (e: Exception) { }
    }

    /** HTA's format check: a folder from a newer HTA (format > 5) is never written to (alarms still ring). */
    const val KNOWN_FORMAT = 5
}
