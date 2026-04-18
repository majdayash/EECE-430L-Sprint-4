package com.example.currencyexchange

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.ProgressBar
import androidx.appcompat.app.AppCompatActivity
import com.example.currencyexchange.api.Authentication
import com.example.currencyexchange.api.ExchangeService
import com.example.currencyexchange.api.model.Token
import com.example.currencyexchange.api.model.User
import com.google.android.material.snackbar.Snackbar
import com.google.android.material.textfield.TextInputEditText
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class LoginActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_SESSION_EXPIRED = "session_expired"
    }

    private lateinit var txtUsername: TextInputEditText
    private lateinit var txtPassword: TextInputEditText
    private lateinit var btnSubmit: Button
    private lateinit var progress: ProgressBar
    private lateinit var proofPanelManager: ProofPanelManager

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Authentication.initialize(this)
        setContentView(R.layout.activity_login)
        proofPanelManager = ProofPanelManager(this, "Login")

        txtUsername = findViewById(R.id.txtInptUsername)
        txtPassword = findViewById(R.id.txtInptPassword)
        btnSubmit = findViewById(R.id.btnSubmit)
        progress = findViewById(R.id.progressLogin)

        btnSubmit.setOnClickListener { login() }

        if (intent.getBooleanExtra(EXTRA_SESSION_EXPIRED, false)) {
            snack("Session expired. Please log in again.")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        proofPanelManager.stop()
        handler.removeCallbacksAndMessages(null)
    }

    private fun login() {
        val username = txtUsername.text?.toString()?.trim().orEmpty()
        val password = txtPassword.text?.toString()?.trim().orEmpty()

        if (username.isEmpty() || password.isEmpty()) {
            snack("Username and password are required")
            return
        }

        setLoading(true)
        val user = User(username, password)
        ExchangeService.instance.authenticate(user).enqueue(object : Callback<Token> {
            override fun onResponse(call: Call<Token>, response: Response<Token>) {
                setLoading(false)
                val body = response.body()
                when {
                    response.isSuccessful && body != null -> {
                        Authentication.saveToken(body.token)
                        Authentication.saveUsername(username)
                        finish()
                    }
                    response.code() == 401 || response.code() == 403 ->
                        snack("Invalid username or password")
                    response.code() == 429 ->
                        disableSubmitTemporarily()
                    else ->
                        snack("Login failed (${response.code()})")
                }
            }

            override fun onFailure(call: Call<Token>, t: Throwable) {
                setLoading(false)
                snack("Network error: ${t.message}")
            }
        })
    }

    private fun setLoading(loading: Boolean) {
        progress.visibility = if (loading) View.VISIBLE else View.GONE
        btnSubmit.isEnabled = !loading
    }

    private fun disableSubmitTemporarily() {
        snack("Too many requests. Wait and try again.")
        btnSubmit.isEnabled = false
        handler.postDelayed({ btnSubmit.isEnabled = true }, 30_000L)
    }

    private fun snack(msg: String) {
        Snackbar.make(findViewById(android.R.id.content), msg, Snackbar.LENGTH_LONG).show()
    }
}
