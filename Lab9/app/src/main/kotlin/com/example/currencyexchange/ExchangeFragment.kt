package com.example.currencyexchange

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.example.currencyexchange.api.Authentication
import com.example.currencyexchange.api.ExchangeService
import com.example.currencyexchange.api.model.ExchangeRates
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.text.NumberFormat
import java.util.Locale

class ExchangeFragment : Fragment() {

    private lateinit var progressRates: ProgressBar
    private lateinit var layoutError: LinearLayout
    private lateinit var txtErrorMessage: TextView
    private lateinit var btnRetry: Button
    private lateinit var layoutRates: LinearLayout
    private lateinit var txtBuyUsdRate: TextView
    private lateinit var txtSellUsdRate: TextView
    private lateinit var btnRefreshRates: Button
    private lateinit var tilAmount: TextInputLayout
    private lateinit var txtAmount: TextInputEditText
    private lateinit var rdGrpConversionDirection: RadioGroup
    private lateinit var btnCalculateExchange: Button
    private lateinit var txtExchangeResult: TextView

    // null means rates have not successfully loaded yet
    private var buyRate: Float? = null   // usd_to_lbp — rate you get when selling USD
    private var sellRate: Float? = null  // lbp_to_usd — rate you get when buying USD

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Authentication.initialize(requireContext())
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.fragment_exchange, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        progressRates = view.findViewById(R.id.progressRates)
        layoutError = view.findViewById(R.id.layoutError)
        txtErrorMessage = view.findViewById(R.id.txtErrorMessage)
        btnRetry = view.findViewById(R.id.btnRetry)
        layoutRates = view.findViewById(R.id.layoutRates)
        txtBuyUsdRate = view.findViewById(R.id.txtBuyUsdRate)
        txtSellUsdRate = view.findViewById(R.id.txtSellUsdRate)
        btnRefreshRates = view.findViewById(R.id.btnRefreshRates)
        tilAmount = view.findViewById(R.id.tilAmount)
        txtAmount = view.findViewById(R.id.txtInptAmount)
        rdGrpConversionDirection = view.findViewById(R.id.rdGrpConversionDirection)
        btnCalculateExchange = view.findViewById(R.id.btnCalculateExchange)
        txtExchangeResult = view.findViewById(R.id.txtExchangeResult)

        btnCalculateExchange.setOnClickListener { calculateExchange() }
        btnRefreshRates.setOnClickListener { fetchRates() }
        btnRetry.setOnClickListener { fetchRates() }

        fetchRates()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        handler.removeCallbacksAndMessages(null)
    }

    private fun showLoading() {
        progressRates.visibility = View.VISIBLE
        layoutError.visibility = View.GONE
        layoutRates.visibility = View.GONE
    }

    private fun showRates() {
        progressRates.visibility = View.GONE
        layoutError.visibility = View.GONE
        layoutRates.visibility = View.VISIBLE
    }

    private fun showError(message: String) {
        progressRates.visibility = View.GONE
        layoutRates.visibility = View.GONE
        txtErrorMessage.text = message
        layoutError.visibility = View.VISIBLE
    }

    private fun fetchRates() {
        showLoading()
        ExchangeService.instance.getExchangeRate().enqueue(object : Callback<ExchangeRates> {
            override fun onResponse(call: Call<ExchangeRates>, response: Response<ExchangeRates>) {
                if (!isAdded) return
                when {
                    response.isSuccessful -> {
                        val rates = response.body()
                        if (rates != null) {
                            buyRate = rates.usdToLbp
                            sellRate = rates.lbpToUsd
                            txtBuyUsdRate.text = formatRate(rates.usdToLbp, "LBP")
                            txtSellUsdRate.text = formatRate(rates.lbpToUsd, "USD")
                            showRates()
                        } else {
                            showError("No rate data received.")
                        }
                    }
                    response.code() == 429 -> {
                        showError("Too many requests. Wait and try again.")
                        disableRefreshTemporarily()
                    }
                    else -> showError("Failed to load rates (${response.code()}).")
                }
            }

            override fun onFailure(call: Call<ExchangeRates>, t: Throwable) {
                if (!isAdded) return
                showError("Network error: ${t.message}")
            }
        })
    }

    private fun disableRefreshTemporarily() {
        btnRefreshRates.isEnabled = false
        btnRetry.isEnabled = false
        handler.postDelayed({
            if (isAdded) {
                btnRefreshRates.isEnabled = true
                btnRetry.isEnabled = true
            }
        }, 30_000L)
    }

    private fun calculateExchange() {
        tilAmount.error = null
        txtExchangeResult.text = ""

        // Guard: rates not loaded yet
        val currentBuyRate = buyRate
        val currentSellRate = sellRate
        if (currentBuyRate == null || currentSellRate == null) {
            txtExchangeResult.text = "Rates not available yet. Please wait."
            return
        }

        // Validate: not empty
        val raw = txtAmount.text?.toString()?.trim()
        if (raw.isNullOrEmpty()) {
            tilAmount.error = "Please enter an amount"
            return
        }

        // Validate: is a number
        val amount = raw.toDoubleOrNull()
        if (amount == null) {
            tilAmount.error = "Enter a valid number"
            return
        }

        // Validate: positive
        if (amount <= 0) {
            tilAmount.error = "Amount must be greater than zero"
            return
        }

        // RadioGroup always has one option checked (default: LBP→USD), so no unselected case needed
        when (rdGrpConversionDirection.checkedRadioButtonId) {
            R.id.rdBtnUsdToLbp -> {
                val result = amount * currentBuyRate
                txtExchangeResult.text = "${formatAmount(result, 2)} LBP"
            }
            else -> {
                val result = amount * currentSellRate
                txtExchangeResult.text = "${formatAmount(result, 6)} USD"
            }
        }
    }

    private fun formatRate(value: Float, currency: String): String =
        "${formatAmount(value.toDouble(), if (currency == "LBP") 2 else 6)} $currency"

    private fun formatAmount(value: Double, decimals: Int): String {
        val fmt = NumberFormat.getNumberInstance(Locale.US)
        fmt.minimumFractionDigits = decimals
        fmt.maximumFractionDigits = decimals
        return fmt.format(value)
    }
}
