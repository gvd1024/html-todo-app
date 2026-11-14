package io.github.gvd1024.htaalarms

import android.app.Activity
import android.app.AlertDialog
import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.graphics.Color
import android.graphics.Typeface
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import io.github.gvd1024.htaalarms.core.Remind
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Small view helpers (no UI library: the app is a status panel and a ringing screen). */
object Ui {
    const val GREEN = 0xFF3ECF8E.toInt(); const val RED = 0xFFFF6B6B.toInt(); const val MUTED = 0xFF8B97A6.toInt(); const val WARN = 0xFFF5B545.toInt()

    fun dp(a: Activity, v: Int) = (v * a.resources.displayMetrics.density).toInt()

    fun column(a: Activity) = LinearLayout(a).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(a, 16), dp(a, 12), dp(a, 16), dp(a, 24)) }
    fun row(a: Activity) = LinearLayout(a).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(a, 4), 0, dp(a, 4)) }

    fun text(a: Activity, s: CharSequence, size: Float = 15f, color: Int? = null, bold: Boolean = false) = TextView(a).apply {
        text = s; textSize = size; color?.let { setTextColor(it) }; if (bold) setTypeface(typeface, Typeface.BOLD)
        setPadding(0, dp(a, 4), 0, dp(a, 4))
    }

    fun button(a: Activity, label: String, onClick: () -> Unit) = Button(a).apply { text = label; isAllCaps = false; setOnClickListener { onClick() } }

    fun heading(a: Activity, s: String) = text(a, s, 18f, bold = true).apply { setPadding(0, dp(a, 16), 0, dp(a, 4)) }

    fun weight(v: View) = v.apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) }

    fun toast(a: Activity, s: String) = a.runOnUiThread { Toast.makeText(a, s, Toast.LENGTH_LONG).show() }

    private val NICE = DateTimeFormatter.ofPattern("EEE d MMM, HH:mm")
    fun nice(entry: String): String = Remind.parse(entry)?.format(NICE) ?: entry
    fun niceMs(ms: Long): String = if (ms <= 0) "—" else LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(ms), java.time.ZoneId.systemDefault()).format(NICE)

    /** Date then time pickers → "YYYY-MM-DD HH:MM". */
    fun pickDateTime(a: Activity, start: String, done: (String) -> Unit) {
        val s = Remind.parse(start) ?: LocalDateTime.now().plusHours(1).withMinute(0)
        DatePickerDialog(a, { _, y, m, d ->
            TimePickerDialog(a, { _, h, mi -> done(Remind.format(LocalDateTime.of(y, m + 1, d, h, mi))) }, s.hour, s.minute, true).show()
        }, s.year, s.monthValue - 1, s.dayOfMonth).show()
    }

    /** Time picker for today (or tomorrow if that time has passed) → custom snooze. */
    fun pickTime(a: Activity, done: (String) -> Unit) {
        val n = LocalDateTime.now().plusMinutes(30)
        TimePickerDialog(a, { _, h, mi ->
            var t = LocalDateTime.now().withHour(h).withMinute(mi).withSecond(0).withNano(0)
            if (!t.isAfter(LocalDateTime.now())) t = t.plusDays(1)
            done(Remind.format(t))
        }, n.hour, n.minute, true).show()
    }

    /** Dismiss / Snooze (10 min, 1 hour, tomorrow, custom) / Reschedule for one reminder; runs the answer off the UI thread. */
    fun answerDialog(a: Activity, key: String, label: String, entry: String, after: () -> Unit) {
        val items = arrayOf("Dismiss", "Snooze 10 min", "Snooze 1 hour", "Snooze until tomorrow, same time", "Snooze until… (pick a time)", "Reschedule… (date and time)")
        AlertDialog.Builder(a).setTitle(label).setItems(items) { _, which ->
            when (which) {
                0 -> run(a, key, "dismiss", null, after)
                1 -> run(a, key, "10m", null, after)
                2 -> run(a, key, "1h", null, after)
                3 -> run(a, key, "tomorrow", null, after)
                4 -> pickTime(a) { run(a, key, "at", it, after) }
                5 -> pickDateTime(a, entry) { run(a, key, "at", it, after) }
            }
        }.setNegativeButton("Cancel", null).show()
    }

    fun run(a: Activity, key: String, kind: String, to: String?, after: () -> Unit) {
        worker.execute { val msg = Actions.answer(a.applicationContext, key, kind, to); toast(a, msg); a.runOnUiThread(after) }
    }

    fun dot(a: Activity, ok: Boolean?) = TextView(a).apply {
        text = when (ok) { true -> "●"; false -> "●"; null -> "○" }; textSize = 18f
        setTextColor(when (ok) { true -> GREEN; false -> RED; null -> WARN }); setPadding(0, 0, dp(a, 10), 0)
    }

    const val BG = Color.BLACK
}
