package io.github.gvd1024.htaalarms

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/** htaalarms://sync — HTA's handoff after a reminder change: check OneDrive now (in the background) and close at once. */
class SyncLinkActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        sendBroadcast(Intent(this, CheckReceiver::class.java).setAction(CheckReceiver.ACTION).putExtra("why", "HTA handoff"))
        finish()
        overridePendingTransition(0, 0)
    }
}
