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

class RegistrationActivity : AppCompatActivity() {

    private lateinit var txtUsername: TextInputEditText
    private lateinit var txtPassword: TextInputEditText
    private lateinit var btnSubmit: Button
    private lateinit var progress: ProgressBar
    private lateinit var proofPanelManager: ProofPanelManager

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Authentication.initialize(this)
        setContentView(R.layout.activity_registration)
        proofPanelManager = ProofPanelManager(this, "Registration")

        txtUsername = findViewById(R.id.txtInptUsername)
        txtPassword = findViewById(R.id.txtInptPassword)
        btnSubmit = findViewById(R.id.btnSubmit)
        progress = findViewById(R.id.progressRegister)

        btnSubmit.setOnClickListener { createUser() }
    }

    override fun onDestroy() {
        super.onDestroy()
        proofPanelManager.stop()
        handler.removeCallbacksAndMessages(null)
    }

    private fun createUser() {
        val username = txtUsername.text?.toString()?.trim().orEmpty()
        val password = txtPassword.text?.toString()?.trim().orEmpty()

        if (username.isEmpty() || password.isEmpty()) {
            snack("Username and password are required")
            return
        }

        setLoading(true)
        val user = User(username, password)
        ExchangeService.instance.addUser(user).enqueue(object : Callback<User> {
            override fun onResponse(call: Call<User>, response: Response<User>) {
                when {
                    response.isSuccessful -> authenticateUser(user)
                    response.code() == 401 || response.code() == 409 -> {
                        setLoading(false)
                        snack("Username already taken")
                    }
                    response.code() == 403 -> {
                        setLoading(false)
                        snack("Access forbidden")
                    }
                    response.code() == 429 -> {
                        setLoading(false)
                        disableSubmitTemporarily()
                    }
                    else -> {
                        setLoading(false)
                        snack("Registration failed (${response.code()})")
                    }
                }
            }

            override fun onFailure(call: Call<User>, t: Throwable) {
                setLoading(false)
                snack("Network error: ${t.message}")
            }
        })
    }

    private fun authenticateUser(user: User) {
        ExchangeService.instance.authenticate(user).enqueue(object : Callback<Token> {
            override fun onResponse(call: Call<Token>, response: Response<Token>) {
                setLoading(false)
                val body = response.body()
                when {
                    response.isSuccessful && body != null -> {
                        Authentication.saveToken(body.token)
                        Authentication.saveUsername(user.userName)
                        finish()
                    }
                    response.code() == 429 -> disableSubmitTemporarily()
                    else -> snack("Auto-login failed (${response.code()})")
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
