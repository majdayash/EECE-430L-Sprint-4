package com.example.currencyexchange

import android.app.Activity
import android.os.Handler
import android.os.Looper
import android.widget.TextView
import com.example.currencyexchange.api.Authentication
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class ProofPanelManager(activity: Activity, screenName: String) {

    private val handler = Handler(Looper.getMainLooper())
    private val clockFormat = SimpleDateFormat("yyyy-MM-dd  HH:mm:ss", Locale.getDefault())

    private val tvUser: TextView = activity.findViewById(R.id.tvProofUser)
    private val tvClock: TextView = activity.findViewById(R.id.tvProofClock)

    private val clockRunnable = object : Runnable {
        override fun run() {
            tvClock.text = clockFormat.format(Date())
            handler.postDelayed(this, 1000)
        }
    }

    init {
        tvUser.text = Authentication.getUsername() ?: "Guest"
        activity.findViewById<TextView>(R.id.tvProofScreen).text = screenName
        handler.post(clockRunnable)
    }

    fun refreshUsername() {
        tvUser.text = Authentication.getUsername() ?: "Guest"
    }

    fun stop() {
        handler.removeCallbacks(clockRunnable)
    }
}
