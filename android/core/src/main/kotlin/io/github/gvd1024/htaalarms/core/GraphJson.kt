package io.github.gvd1024.htaalarms.core

import org.json.JSONObject

/** Reading Microsoft Graph's driveItem JSON (org.json: part of Android, a plain jar in the JVM tests). */
object GraphJson {
    data class DeltaPage(val items: List<DeltaState.Item>, val nextLink: String?, val deltaLink: String?)

    fun item(o: JSONObject) = DeltaState.Item(
        id = o.getString("id"),
        name = o.optString("name", "").ifEmpty { null },
        parentId = o.optJSONObject("parentReference")?.optString("id", "")?.ifEmpty { null },
        isFolder = o.has("folder"),
        deleted = o.has("deleted"),
        eTag = o.optString("eTag", ""),
        cTag = o.optString("cTag", "").ifEmpty { o.optString("eTag", "") },
    )

    fun deltaPage(json: String): DeltaPage {
        val o = JSONObject(json)
        val arr = o.optJSONArray("value")
        val items = (0 until (arr?.length() ?: 0)).map { item(arr!!.getJSONObject(it)) }
        return DeltaPage(items, o.optString("@odata.nextLink", "").ifEmpty { null }, o.optString("@odata.deltaLink", "").ifEmpty { null })
    }
}
