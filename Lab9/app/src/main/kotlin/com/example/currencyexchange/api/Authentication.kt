package com.example.currencyexchange.api

import android.content.Context
import android.content.SharedPreferences

object Authentication {
    private const val PREFS_NAME = "auth_prefs"
    private const val TOKEN_KEY = "token"
    private const val USERNAME_KEY = "username"

    private lateinit var prefs: SharedPreferences

    fun initialize(context: Context) {
        prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getToken(): String? {
        if (!::prefs.isInitialized) return null
        return prefs.getString(TOKEN_KEY, null)
    }

    fun saveToken(token: String) {
        if (!::prefs.isInitialized) return
        prefs.edit().putString(TOKEN_KEY, token).apply()
    }

    fun clearToken() {
        if (!::prefs.isInitialized) return
        prefs.edit().remove(TOKEN_KEY).apply()
    }

    fun getUsername(): String? {
        if (!::prefs.isInitialized) return null
        return prefs.getString(USERNAME_KEY, null)
    }

    fun saveUsername(username: String) {
        if (!::prefs.isInitialized) return
        prefs.edit().putString(USERNAME_KEY, username).apply()
    }

    fun clearUsername() {
        if (!::prefs.isInitialized) return
        prefs.edit().remove(USERNAME_KEY).apply()
    }
}
