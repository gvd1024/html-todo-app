package io.github.gvd1024.htaalarms

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings as AndroidSettings
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import io.github.gvd1024.htaalarms.core.Planner
import java.time.ZoneId

/**
 * The status panel (R2-22): last and next check, the account and folder, the upcoming reminders (tap → snooze,
 * reschedule, dismiss), a green/red line for each thing the phone must allow (each with a button to the right
 * Android setting), and the honest limits.
 */
class MainActivity : Activity() {
    private lateinit var box: LinearLayout
    private var account: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        box = Ui.column(this)
        setContentView(ScrollView(this).apply { addView(box) })
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        handleKey(intent)
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); handleKey(intent) }

    /** Opened from a "Missed" notification: show that reminder's buttons. */
    private fun handleKey(i: Intent?) {
        val key = i?.getStringExtra("key") ?: return
        i.removeExtra("key")
        val r = Actions.find(State.load(this), key) ?: return
        Ui.answerDialog(this, key, r.speak, r.entry) { draw() }
    }

    override fun onResume() {
        super.onResume()
        draw()
        worker.execute {                               // app open: re-arm and check now
            account = Auth.account(this)?.username
            Checker.check(applicationContext, "app opened")
            runOnUiThread { draw() }
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) { draw() }

    private fun draw() {
        val st = State.load(this)
        val set = Settings(this)
        box.removeAllViews()
        box.addView(Ui.text(this, "HTA Alarms", 24f, bold = true))
        box.addView(Ui.text(this, "Speaks your HTA reminders on this phone. v${packageManager.getPackageInfo(packageName, 0).versionName}", 13f, Ui.MUTED))

        // --- sign-in and folder
        box.addView(Ui.heading(this, "OneDrive"))
        val acc = account ?: set.account.ifEmpty { null }
        line(acc != null && !st.signInNeeded, if (acc == null) "Not signed in" else if (st.signInNeeded) "Sign-in expired ($acc) — alarms already set still ring" else "Signed in as $acc",
            if (acc == null || st.signInNeeded) "Sign in" else "Sign out") {
            if (acc == null || st.signInNeeded) Auth.signIn(this) { user, err ->
                if (user != null) { set.account = user; account = user; Notify.cancelSignIn(this); worker.execute { Checker.check(applicationContext, "signed in"); runOnUiThread { draw() } } }
                else Ui.toast(this, "Sign-in didn't finish: $err")
                draw()
            } else AlertDialog.Builder(this).setTitle("Sign out?").setMessage("New and changed reminders stop arriving until you sign in again.")
                .setPositiveButton("Sign out") { _, _ -> worker.execute { Auth.signOut(this); set.account = ""; account = null; runOnUiThread { draw() } } }
                .setNegativeButton("Cancel", null).show()
        }
        box.addView(Ui.text(this, "Folder: ${set.folder}" + if (st.folderFormat > 0) " (data format ${st.folderFormat})" else "", 15f))
        if (st.folderFormat > Checker.KNOWN_FORMAT) box.addView(Ui.text(this, "This folder was updated by a newer HTA (format ${st.folderFormat}). Reminders still ring, but buttons only change this phone. Update HTA Alarms.", 14f, Ui.RED))
        box.addView(Ui.text(this, "Last check: ${Ui.niceMs(st.lastCheck)}" + (if (st.lastError.isNotEmpty()) " — ${st.lastError}" else if (st.lastOk == st.lastCheck && st.lastOk > 0) " ✓" else ""), 15f, if (st.lastError.isNotEmpty()) Ui.RED else null))
        box.addView(Ui.text(this, "Next check: ${Ui.niceMs(st.nextCheck)} (${if (set.mode == "exact") "on the quarter hour" else "battery-friendly, may be up to 10 min later"})", 15f))
        val r1 = Ui.row(this)
        r1.addView(Ui.weight(Ui.button(this, "Check now") { worker.execute { val m = Checker.check(applicationContext, "check now"); Ui.toast(this, "Check: $m"); runOnUiThread { draw() } } }))
        r1.addView(Ui.weight(Ui.button(this, "Test alarm in 1 min") { worker.execute { Scheduler.testAlarm(applicationContext) }; Ui.toast(this, "A test reminder will speak in about 1 minute. Try it with the screen off, in silent mode and in Do Not Disturb.") }))
        box.addView(r1)
        box.addView(Ui.button(this, "Settings") { settingsDialog() })

        // --- upcoming and missed
        box.addView(Ui.heading(this, "Reminders"))
        val now = System.currentTimeMillis(); val zone = ZoneId.systemDefault()
        val plans = Planner.plan(st.index.values, now, zone, st.rung.keys, st.snoozed)
        val missed = Planner.missed(st.index.values, now, zone, st.rung.keys, st.snoozed)
        if (plans.isEmpty() && missed.isEmpty()) box.addView(Ui.text(this, "None. Set them in HTA (Remind, in a task's editor).", 15f, Ui.MUTED))
        for (p in plans) reminderRow(p.reminder.key, p.reminder.speak, p.reminder.entry, (if (p.snoozed) "snoozed to ${Ui.niceMs(p.atMillis)}" else Ui.nice(p.reminder.entry)) + if (p.reminder.repeats) " · repeats" else "", null)
        for (r in missed) reminderRow(r.key, r.speak, r.entry, "missed · ${Ui.nice(r.entry)}", Ui.WARN)

        // --- what the phone must allow
        box.addView(Ui.heading(this, "This phone"))
        val nm = getSystemService(NotificationManager::class.java)
        line(nm.areNotificationsEnabled(), "Notifications", "Open") { open(Intent(AndroidSettings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(AndroidSettings.EXTRA_APP_PACKAGE, packageName)) }
        line(Scheduler.canExact(this), "Exact alarms (Alarms & reminders)", "Open") {
            if (Build.VERSION.SDK_INT >= 31) open(Intent(AndroidSettings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:$packageName"))) }
        val fsi = if (Build.VERSION.SDK_INT >= 34) nm.canUseFullScreenIntent() else true
        line(fsi, "Full-screen alerts (the ringing screen over the lock screen)", "Open") {
            if (Build.VERSION.SDK_INT >= 34) open(Intent(AndroidSettings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:$packageName"))) }
        val pm = getSystemService(PowerManager::class.java)
        line(pm.isIgnoringBatteryOptimizations(packageName), "No battery restriction", "Open") {
            open(Intent(AndroidSettings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")),
                Intent(AndroidSettings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        line(dndAllowsAlarms(nm), "Alarms allowed in Do Not Disturb", "Open") {
            open(Intent("android.settings.ZEN_MODE_SETTINGS"), Intent(AndroidSettings.ACTION_SOUND_SETTINGS)) }
        val am = getSystemService(AudioManager::class.java)
        line(am.getStreamVolume(AudioManager.STREAM_ALARM) > 0, "Alarm volume above zero (${am.getStreamVolume(AudioManager.STREAM_ALARM)}/${am.getStreamMaxVolume(AudioManager.STREAM_ALARM)})", "Open") {
            open(Intent(AndroidSettings.ACTION_SOUND_SETTINGS)) }
        val samsung = Build.MANUFACTURER.equals("samsung", ignoreCase = true)
        line(null, if (samsung) "Samsung: add HTA Alarms to “Never sleeping apps” (can't be checked from here): Settings → Battery → Background usage limits → Never sleeping apps → +"
                   else "Some phone makers stop background apps: allow HTA Alarms to run in the background (can't be checked from here)", "Open") {
            open(*(if (samsung) arrayOf(Intent().setComponent(ComponentName("com.samsung.android.lool", "com.samsung.android.sm.battery.ui.BatteryActivity")),
                    Intent().setComponent(ComponentName("com.samsung.android.lool", "com.samsung.android.sm.ui.battery.BatteryActivity"))) else emptyArray()),
                Intent(AndroidSettings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) }

        // --- limits
        box.addView(Ui.heading(this, "Limits"))
        box.addView(Ui.text(this, "• It rings only if the phone is on and HTA Alarms isn't force-stopped.\n" +
            "• Reminders set or changed elsewhere (PC, HTA in a browser) arrive by the next quarter hour. Set on this phone in HTA, they arrive at once when HTA's handoff is on.\n" +
            "• Times are local clock times: after a time-zone change a reminder rings at that clock time where you are.\n" +
            "• Signed out or offline, alarms already set still ring; new changes wait.\n" +
            "• A repeating task's reminders follow its due date: Dismiss and Snooze stay on this phone, and the next one comes when you check the task off in HTA.", 14f, Ui.MUTED))
    }

    private fun reminderRow(key: String, text: String, entry: String, sub: String, color: Int?) {
        val v = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 6), 0, Ui.dp(this@MainActivity, 6)) }
        v.addView(Ui.text(this, text, 16f, bold = true))
        v.addView(Ui.text(this, sub, 13f, color ?: Ui.MUTED))
        v.setOnClickListener { Ui.answerDialog(this, key, text, entry) { draw() } }
        box.addView(v)
    }

    private fun line(ok: Boolean?, label: String, button: String, onClick: () -> Unit) {
        val r = Ui.row(this)
        r.addView(Ui.dot(this, ok))
        r.addView(Ui.weight(Ui.text(this, label, 15f)))
        if (ok != true) r.addView(Ui.button(this, button, onClick))
        box.addView(r)
    }

    /** Tries each intent in turn (maker-specific screens first, then Android's generic one). */
    private fun open(vararg intents: Intent) {
        for (i in intents) try { startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return } catch (e: Exception) { }
        Ui.toast(this, "Couldn't open that setting on this phone — find it in Settings.")
    }

    /** null when it can't be told; false when Do Not Disturb is on and blocks alarms. */
    private fun dndAllowsAlarms(nm: NotificationManager): Boolean? = try {
        when (nm.currentInterruptionFilter) {
            NotificationManager.INTERRUPTION_FILTER_ALL -> true
            NotificationManager.INTERRUPTION_FILTER_NONE -> false
            NotificationManager.INTERRUPTION_FILTER_ALARMS -> true
            NotificationManager.INTERRUPTION_FILTER_PRIORITY -> (nm.notificationPolicy.priorityCategories and NotificationManager.Policy.PRIORITY_CATEGORY_ALARMS) != 0
            else -> null
        }
    } catch (e: Exception) { null }

    private fun settingsDialog() {
        val set = Settings(this)
        val col = Ui.column(this)
        col.addView(Ui.text(this, "OneDrive folder (from the top of your OneDrive; the same as HTA's setting)", 14f, Ui.MUTED))
        val folder = EditText(this).apply { setText(set.folder); setSingleLine() }
        col.addView(folder)
        col.addView(Ui.text(this, "Checks for new or changed reminders", 14f, Ui.MUTED))
        val g = RadioGroup(this)
        val exact = RadioButton(this).apply { text = "On the quarter hour (exact, default)"; id = 1 }
        val batt = RadioButton(this).apply { text = "Battery-friendly (Android may batch it, up to 10 min later)"; id = 2 }
        g.addView(exact); g.addView(batt); g.check(if (set.mode == "exact") 1 else 2)
        col.addView(g)
        AlertDialog.Builder(this).setTitle("Settings").setView(col)
            .setPositiveButton("Save") { _, _ ->
                set.folder = folder.text.toString(); set.mode = if (g.checkedRadioButtonId == 1) "exact" else "battery"
                worker.execute { Checker.check(applicationContext, "settings"); runOnUiThread { draw() } }
            }.setNegativeButton("Cancel", null).show()
    }
}
