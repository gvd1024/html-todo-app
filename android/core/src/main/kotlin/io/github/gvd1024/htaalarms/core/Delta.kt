package io.github.gvd1024.htaalarms.core

/**
 * Bookkeeping for the Graph change feed (delta) of the task folder, like HTA's GraphStore: the feed sends items
 * without paths, so folders are tracked by item id and a file's path is worked out from its parent. A renamed
 * folder re-paths its files without them being sent again. Folders are one level deep (MAX_DEPTH = 1).
 */
class DeltaState(var rootId: String? = null) {
    data class Folder(val name: String, val parentId: String?)
    data class File(val name: String, val parentId: String?, val eTag: String, val cTag: String)
    data class Item(val id: String, val name: String?, val parentId: String?, val isFolder: Boolean, val deleted: Boolean, val eTag: String, val cTag: String)

    val folders = mutableMapOf<String, Folder>()
    val files = mutableMapOf<String, File>()

    /** The relative path of an item: "name" (in the root) or "Folder/name" (one level down); null = not in reach. */
    fun pathOf(id: String): String? {
        val f = files[id] ?: return null
        if (f.parentId == rootId) return f.name
        val dir = folders[f.parentId] ?: return null
        if (dir.parentId != rootId || !folderOk(dir.name)) return null
        return dir.name + "/" + f.name
    }

    /** Apply one batch of items. → the ids of files to (re)read and the ids that are gone. */
    fun apply(items: List<Item>): Pair<Set<String>, Set<String>> {
        val changed = mutableSetOf<String>(); val gone = mutableSetOf<String>()
        for (it in items) {
            if (it.id == rootId) continue
            if (it.deleted) {
                if (files.remove(it.id) != null) gone.add(it.id)
                if (folders.remove(it.id) != null) files.filterValues { f -> f.parentId == it.id }.keys.forEach { k -> files.remove(k); gone.add(k) }
                continue
            }
            if (it.isFolder) { folders[it.id] = Folder(it.name ?: "", it.parentId); continue }
            val before = files[it.id]
            files[it.id] = File(it.name ?: "", it.parentId, it.eTag, it.cTag)
            if (before == null || before.cTag != it.cTag || before.name != it.name || before.parentId != it.parentId) changed.add(it.id)
        }
        return changed to gone
    }

    companion object {
        fun folderOk(name: String) = name.isNotEmpty() && !name.startsWith(".") && !name.startsWith("_")
        /** HTA's isTaskPath: .md files, not _x/.x, not README.md, nothing inside a .folder, at most one folder deep. */
        fun isTaskPath(path: String): Boolean {
            val parts = path.split('/')
            if (parts.size > 2) return false
            val name = parts.last()
            if (!name.lowercase().endsWith(".md") || name.startsWith("_") || name.startsWith(".") || name.equals("README.md", ignoreCase = true)) return false
            return parts.size == 1 || folderOk(parts[0])
        }
    }
}
