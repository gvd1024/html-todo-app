package io.github.gvd1024.htaalarms

import android.app.Application

class App : Application() {
    override fun onCreate() { super.onCreate(); Notify.channels(this) }
}
