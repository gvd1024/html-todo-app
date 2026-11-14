package io.github.gvd1024.htaalarms.core

/** The few Graph calls a write-back needs (the app implements it over HTTPS; tests use a fake). */
interface FileApi {
    /** → (text, eTag) or throws [NotFound]. */
    fun download(itemId: String): Pair<String, String>
    /** PUT with If-Match: eTag. → the new eTag, or throws [PreconditionFailed] (412) / [NotFound]. */
    fun upload(itemId: String, text: String, ifMatch: String): String
    class PreconditionFailed : Exception("412: changed elsewhere")
    class NotFound : Exception("404: not found")
}

/**
 * Dismiss (to = null) or move (to = a new entry) one reminder in its task file: re-download with its eTag, edit only
 * the remind line(s), PUT with If-Match. On 412: re-read and try once more. If the entry is gone, nothing to do.
 */
object WriteBack {
    enum class Result { WRITTEN, GONE, REFUSED, CONFLICT }

    fun edit(api: FileApi, itemId: String, path: String, entry: String, to: String?): Result {
        repeat(2) {
            val (text, eTag) = try { api.download(itemId) } catch (e: FileApi.NotFound) { return Result.GONE }
            val task = Frontmatter.readTask(path, text) ?: return Result.REFUSED
            val cur = task.remind ?: return Result.REFUSED
            if (entry !in cur) return Result.GONE
            if (!Remind.ringable(task.status)) return Result.GONE
            val next = cur.filter { it != entry } + listOfNotNull(to)
            val patched = Frontmatter.remindPatch(text, next) ?: return Result.REFUSED
            try { api.upload(itemId, patched, eTag); return Result.WRITTEN }
            catch (e: FileApi.PreconditionFailed) { /* changed elsewhere: read again */ }
            catch (e: FileApi.NotFound) { return Result.GONE }
        }
        return Result.CONFLICT
    }
}
