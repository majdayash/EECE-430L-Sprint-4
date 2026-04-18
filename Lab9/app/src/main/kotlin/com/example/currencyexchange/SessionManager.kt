package com.example.currencyexchange

import android.app.Activity
import android.content.Intent
import com.example.currencyexchange.api.Authentication

fun handleSessionExpired(activity: Activity) {
    Authentication.clearToken()
    Authentication.clearUsername()
    activity.startActivity(
        Intent(activity, LoginActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            putExtra(LoginActivity.EXTRA_SESSION_EXPIRED, true)
        }
    )
    activity.finish()
}
