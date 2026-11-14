package io.github.gvd1024.htaalarms

import io.github.gvd1024.htaalarms.core.FileApi
import io.github.gvd1024.htaalarms.core.GraphJson
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Microsoft Graph over plain HTTPS, only what HTA Alarms needs: the task folder's id, its change feed (delta),
 * downloading a task file, and writing one back with If-Match (never without). Tokens go only in the
 * Authorization header to graph.microsoft.com and are never logged.
 */
class Graph(private val token: () -> String) : FileApi {
    class HttpError(val code: Int, msg: String) : IOException("HTTP $code: $msg")

    private fun open(url: String, method: String = "GET", auth: Boolean = true): HttpURLConnection {
        val c = URL(url).openConnection() as HttpURLConnection
        c.requestMethod = method
        c.connectTimeout = 15_000; c.readTimeout = 20_000
        c.instanceFollowRedirects = false
        if (auth) c.setRequestProperty("Authorization", "Bearer " + token())
        return c
    }

    private fun body(c: HttpURLConnection): String {
        val code = c.responseCode
        val stream = if (code in 200..299) c.inputStream else c.errorStream
        val text = stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        if (code !in 200..299) throw HttpError(code, text.take(200).replace(Regex("[\\r\\n]+"), " "))
        return text
    }

    private fun get(url: String): String = open(url).let { c -> try { body(c) } finally { c.disconnect() } }

    private fun enc(path: String) = path.split('/').joinToString("/") { URLEncoder.encode(it, "UTF-8").replace("+", "%20") }

    /** The task folder's item id (the folder path from the top of OneDrive, e.g. "HTML-ToDo-App"). */
    fun folderId(folder: String): String = JSONObject(get("$G/me/drive/root:/${enc(folder)}?select=id,name,folder")).getString("id")

    fun me(): String = JSONObject(get("$G/me?select=userPrincipalName,mail")).let { it.optString("userPrincipalName").ifEmpty { it.optString("mail") } }

    /** One round of the change feed: from [link] (a saved deltaLink) or from the start. → all items + the new deltaLink.
     *  A 410 (feed reset) is thrown as HttpError(410): the caller starts over. */
    fun delta(folderId: String, link: String?): GraphJson.DeltaPage {
        var url: String? = link ?: "$G/me/drive/items/$folderId/delta?select=id,name,parentReference,folder,file,deleted,eTag,cTag"
        val items = mutableListOf<io.github.gvd1024.htaalarms.core.DeltaState.Item>()
        var deltaLink: String? = null
        var pages = 0
        while (url != null && pages++ < 200) {
            val p = GraphJson.deltaPage(get(url))
            items.addAll(p.items); deltaLink = p.deltaLink ?: deltaLink; url = p.nextLink
        }
        return GraphJson.DeltaPage(items, null, deltaLink)
    }

    /** The file's text and its current eTag (for a write-back). */
    override fun download(itemId: String): Pair<String, String> {
        val meta = try { JSONObject(get("$G/me/drive/items/$itemId?select=id,eTag")) } catch (e: HttpError) { if (e.code == 404) throw FileApi.NotFound() else throw e }
        return content(itemId) to meta.getString("eTag")
    }

    /** Only the text (the checker already has the eTag from the change feed). The content comes from a short-lived
     *  download link, fetched without our token. */
    fun content(itemId: String): String {
        val c = open("$G/me/drive/items/$itemId/content")
        return try {
            when (c.responseCode) {
                302, 301, 303, 307 -> { val loc = c.getHeaderField("Location"); val d = open(loc, auth = false); try { body(d) } finally { d.disconnect() } }
                404 -> throw FileApi.NotFound()
                else -> body(c)
            }
        } finally { c.disconnect() }
    }

    /** PUT with If-Match: the file is written only if nobody changed it since [ifMatch]. */
    override fun upload(itemId: String, text: String, ifMatch: String): String {
        val c = open("$G/me/drive/items/$itemId/content", "PUT")
        c.doOutput = true
        c.setRequestProperty("If-Match", ifMatch)
        c.setRequestProperty("Content-Type", "text/plain")
        try {
            c.outputStream.use { it.write(text.toByteArray(Charsets.UTF_8)) }
            return when (c.responseCode) {
                412 -> throw FileApi.PreconditionFailed()
                404 -> throw FileApi.NotFound()
                else -> JSONObject(body(c)).optString("eTag")
            }
        } finally { c.disconnect() }
    }

    companion object { const val G = "https://graph.microsoft.com/v1.0" }
}
