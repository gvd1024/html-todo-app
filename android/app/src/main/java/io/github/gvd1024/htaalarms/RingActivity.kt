package io.github.gvd1024.htaalarms

import android.app.Activity
import android.os.Bundle
import android.view.WindowManager
import android.widget.ScrollView

/**
 * The ringing screen, over the lock screen (showWhenLocked + turnScreenOn in the manifest). Lists everything that
 * is ringing, each with Dismiss / Snooze / Reschedule.
 */
class RingActivity : Activity() {
    private lateinit var box: android.widget.LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true); setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        box = Ui.column(this)
        setContentView(ScrollView(this).apply { addView(box) })
    }

    override fun onResume() { super.onResume(); refresh = { runOnUiThread { draw() } }; draw() }
    override fun onPause() { super.onPause(); refresh = null }

    private fun draw() {
        box.removeAllViews()
        val q = synchronized(RingService.queue) { RingService.queue.toList() }
        if (q.isEmpty()) { finish(); return }
        box.addView(Ui.text(this, "⏰ HTA reminder" + if (q.size > 1) "s (${q.size})" else "", 16f, Ui.MUTED))
        for (r in q) {
            box.addView(Ui.text(this, r.text, 28f, bold = true).apply { setPadding(0, Ui.dp(this@RingActivity, 16), 0, 0) })
            if (r.title != r.text) box.addView(Ui.text(this, r.title, 16f, Ui.MUTED))
            box.addView(Ui.text(this, (if (r.entry == "now") "" else Ui.nice(r.entry)) + RingService.lateText(r), 16f, if (r.late) Ui.WARN else Ui.MUTED))
            val row1 = Ui.row(this)
            row1.addView(Ui.weight(Ui.button(this, "Dismiss") { Ui.run(this, r.key, "dismiss", null) { draw() } }))
            row1.addView(Ui.weight(Ui.button(this, "10 min") { Ui.run(this, r.key, "10m", null) { draw() } }))
            row1.addView(Ui.weight(Ui.button(this, "1 hour") { Ui.run(this, r.key, "1h", null) { draw() } }))
            box.addView(row1)
            val row2 = Ui.row(this)
            row2.addView(Ui.weight(Ui.button(this, "Tomorrow") { Ui.run(this, r.key, "tomorrow", null) { draw() } }))
            row2.addView(Ui.weight(Ui.button(this, "Snooze until…") { Ui.pickTime(this) { t -> Ui.run(this, r.key, "at", t) { draw() } } }))
            row2.addView(Ui.weight(Ui.button(this, "Reschedule…") { Ui.pickDateTime(this, r.entry) { t -> Ui.run(this, r.key, "at", t) { draw() } } }))
            box.addView(row2)
        }
    }

    companion object { @Volatile var refresh: (() -> Unit)? = null }
}
