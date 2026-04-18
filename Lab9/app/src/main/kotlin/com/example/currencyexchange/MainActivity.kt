package com.example.currencyexchange

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.LayoutInflater
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.Button
import android.widget.RadioGroup
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.coordinatorlayout.widget.CoordinatorLayout
import androidx.viewpager2.widget.ViewPager2
import com.example.currencyexchange.api.Authentication
import com.example.currencyexchange.api.ExchangeService
import com.example.currencyexchange.api.model.Transaction
import com.example.currencyexchange.api.model.TransactionResponse
import com.example.currencyexchange.api.model.Wallet
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.snackbar.Snackbar
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator
import com.google.android.material.textfield.TextInputLayout
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MainActivity : AppCompatActivity() {

    private lateinit var fab: FloatingActionButton
    private lateinit var btnLogin: Button
    private lateinit var btnRegister: Button
    private lateinit var btnFundWallet: Button
    private lateinit var rootLayout: CoordinatorLayout
    private lateinit var tabLayout: TabLayout
    private lateinit var viewPager: ViewPager2
    private var menu: Menu? = null

    private var token: String? = null

    private lateinit var proofPanelManager: ProofPanelManager
    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Authentication.initialize(this)
        setContentView(R.layout.activity_main)
        proofPanelManager = ProofPanelManager(this, "Main")

        fab = findViewById(R.id.fab)
        btnLogin = findViewById(R.id.btnLogin)
        btnRegister = findViewById(R.id.btnRegister)
        btnFundWallet = findViewById(R.id.btnFundWallet)
        rootLayout = findViewById(R.id.rootLayout)
        tabLayout = findViewById(R.id.tabLayout)
        viewPager = findViewById(R.id.viewPager)

        token = Authentication.getToken()

        viewPager.adapter = TabsPagerAdapter(this)
        TabLayoutMediator(tabLayout, viewPager) { tab, position ->
            tab.text = when (position) {
                0 -> "Exchange"
                else -> "Transactions"
            }
        }.attach()

        fab.setOnClickListener { showDialog() }
        btnLogin.setOnClickListener { startActivity(Intent(this, LoginActivity::class.java)) }
        btnRegister.setOnClickListener { startActivity(Intent(this, RegistrationActivity::class.java)) }
        btnFundWallet.setOnClickListener { showFundWalletDialog() }

        updateAuthUI()
    }

    override fun onResume() {
        super.onResume()
        token = Authentication.getToken()
        proofPanelManager.refreshUsername()
        updateAuthUI()
        invalidateOptionsMenu()
    }

    override fun onDestroy() {
        super.onDestroy()
        proofPanelManager.stop()
        handler.removeCallbacksAndMessages(null)
    }

    override fun onCreateOptionsMenu(menu: Menu?): Boolean {
        this.menu = menu
        setMenu()
        return true
    }

    private fun setMenu() {
        val currentMenu = menu ?: return
        currentMenu.clear()
        if (token.isNullOrBlank()) {
            menuInflater.inflate(R.menu.menu_logged_out, currentMenu)
        } else {
            menuInflater.inflate(R.menu.menu_logged_in, currentMenu)
        }
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.menu_register -> {
                startActivity(Intent(this, RegistrationActivity::class.java))
                true
            }
            R.id.menu_login -> {
                startActivity(Intent(this, LoginActivity::class.java))
                true
            }
            R.id.menu_logout -> {
                Authentication.clearToken()
                Authentication.clearUsername()
                token = null
                proofPanelManager.refreshUsername()
                updateAuthUI()
                Snackbar.make(rootLayout, "Logged out successfully", Snackbar.LENGTH_SHORT).show()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun updateAuthUI() {
        if (!token.isNullOrBlank()) {
            btnLogin.visibility = View.GONE
            btnRegister.visibility = View.GONE
            fab.visibility = View.VISIBLE
            btnFundWallet.visibility = View.VISIBLE
        } else {
            btnLogin.visibility = View.VISIBLE
            btnRegister.visibility = View.VISIBLE
            fab.visibility = View.GONE
            btnFundWallet.visibility = View.GONE
        }
        setMenu()
        invalidateOptionsMenu()
    }

    private fun showFundWalletDialog() {
        if (token.isNullOrBlank()) {
            Snackbar.make(rootLayout, "Please log in first", Snackbar.LENGTH_SHORT).show()
            return
        }

        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_wallet, null)
        AlertDialog.Builder(this)
            .setTitle("Fund Wallet")
            .setView(dialogView)
            .setPositiveButton("Save") { _, _ ->
                val usdBalance = dialogView.findViewById<TextInputLayout>(R.id.txtInptUsdBalance)
                    .editText?.text.toString().toFloatOrNull()
                val lbpBalance = dialogView.findViewById<TextInputLayout>(R.id.txtInptLbpBalance)
                    .editText?.text.toString().toFloatOrNull()
                if (usdBalance != null && lbpBalance != null) {
                    fundWallet(Wallet(usdBalance, lbpBalance))
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun fundWallet(wallet: Wallet) {
        if (token.isNullOrBlank()) {
            Snackbar.make(rootLayout, "Please log in first", Snackbar.LENGTH_SHORT).show()
            return
        }

        ExchangeService.instance.updateWallet("Bearer $token", wallet)
            .enqueue(object : Callback<Wallet> {
                override fun onResponse(call: Call<Wallet>, response: Response<Wallet>) {
                    if (response.isSuccessful) {
                        Snackbar.make(rootLayout, "Wallet funded successfully", Snackbar.LENGTH_SHORT).show()
                    } else {
                        Snackbar.make(rootLayout, "Wallet error: ${response.code()}", Snackbar.LENGTH_LONG).show()
                    }
                }

                override fun onFailure(call: Call<Wallet>, t: Throwable) {
                    Snackbar.make(rootLayout, "Wallet error: ${t.message}", Snackbar.LENGTH_LONG).show()
                }
            })
    }

    private fun showDialog() {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_transaction, null)
        val tilUsd = dialogView.findViewById<TextInputLayout>(R.id.txtInptUsdAmount)
        val tilLbp = dialogView.findViewById<TextInputLayout>(R.id.txtInptLbpAmount)
        val rdGrp = dialogView.findViewById<RadioGroup>(R.id.rdGrpTransactionType)

        val dialog = AlertDialog.Builder(this)
            .setTitle("Add Transaction")
            .setView(dialogView)
            .setPositiveButton("Add", null) // null listener — we set it manually to prevent auto-dismiss
            .setNegativeButton("Cancel", null)
            .create()

        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                tilUsd.error = null
                tilLbp.error = null

                val usdRaw = tilUsd.editText?.text?.toString()?.trim()
                val lbpRaw = tilLbp.editText?.text?.toString()?.trim()
                val usdAmount = usdRaw?.toFloatOrNull()
                val lbpAmount = lbpRaw?.toFloatOrNull()
                val directionId = rdGrp.checkedRadioButtonId

                var valid = true

                if (usdRaw.isNullOrEmpty() || usdAmount == null || usdAmount <= 0f) {
                    tilUsd.error = "Enter a positive USD amount"
                    valid = false
                }
                if (lbpRaw.isNullOrEmpty() || lbpAmount == null || lbpAmount <= 0f) {
                    tilLbp.error = "Enter a positive LBP amount"
                    valid = false
                }
                if (directionId == -1) {
                    Snackbar.make(rootLayout, "Please select Buy USD or Sell USD", Snackbar.LENGTH_SHORT).show()
                    valid = false
                }

                if (!valid) return@setOnClickListener

                val isBuyUsd = directionId == R.id.rdBtnBuyUsd
                addTransaction(Transaction(usdAmount!!, lbpAmount!!, isBuyUsd), dialog)
            }
        }

        dialog.show()
    }

    private fun addTransaction(transaction: Transaction, dialog: AlertDialog) {
        val authorization = token?.takeIf { it.isNotBlank() }?.let { "Bearer $it" }

        ExchangeService.instance.addTransaction(authorization, transaction)
            .enqueue(object : Callback<TransactionResponse> {
                override fun onResponse(
                    call: Call<TransactionResponse>,
                    response: Response<TransactionResponse>
                ) {
                    Log.d("Transaction", "HTTP ${response.code()} body=${response.body()}")
                    when {
                        response.isSuccessful && response.body()?.ok == true -> {
                            Snackbar.make(rootLayout, "Transaction added!", Snackbar.LENGTH_SHORT).show()
                            dialog.dismiss()
                        }
                        response.code() == 400 ->
                            Snackbar.make(rootLayout, "Invalid transaction data", Snackbar.LENGTH_LONG).show()
                        response.code() == 401 ->
                            handleSessionExpired(this@MainActivity)
                        response.code() == 403 ->
                            Snackbar.make(rootLayout, "Permission denied", Snackbar.LENGTH_LONG).show()
                        response.code() == 429 -> {
                            Snackbar.make(rootLayout, "Too many requests. Wait and try again.", Snackbar.LENGTH_LONG).show()
                            disableFabTemporarily()
                        }
                        else ->
                            Snackbar.make(rootLayout, "Server error: ${response.code()}", Snackbar.LENGTH_LONG).show()
                    }
                }

                override fun onFailure(call: Call<TransactionResponse>, t: Throwable) {
                    Log.e("Transaction", "onFailure: ${t.message}", t)
                    Snackbar.make(rootLayout, "Network error: ${t.message}", Snackbar.LENGTH_LONG).show()
                }
            })
    }

    private fun disableFabTemporarily() {
        fab.isEnabled = false
        handler.postDelayed({ fab.isEnabled = true }, 30_000L)
    }
}
