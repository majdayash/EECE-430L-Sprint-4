package com.example.currencyexchange

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.example.currencyexchange.api.Authentication
import com.example.currencyexchange.api.ExchangeService
import com.example.currencyexchange.api.model.Transaction
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Locale

class TransactionsFragment : Fragment() {

    private val transactions = ArrayList<Transaction>()

    private lateinit var listView: ListView
    private lateinit var progress: ProgressBar
    private lateinit var txtStatus: TextView
    private lateinit var adapter: TransactionAdapter

    private val inputDateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
    private val outputDateFormat = SimpleDateFormat("MMM dd, yyyy  HH:mm", Locale.US)
    private val usdFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }
    private val lbpFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 0
        maximumFractionDigits = 0
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Authentication.initialize(requireContext())
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.fragment_transactions, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        listView = view.findViewById(R.id.listViewTransactions)
        progress = view.findViewById(R.id.progressTransactions)
        txtStatus = view.findViewById(R.id.txtTransactionsStatus)

        adapter = TransactionAdapter()
        listView.adapter = adapter
    }

    override fun onResume() {
        super.onResume()
        fetchTransactions()
    }

    private fun showLoading() {
        progress.visibility = View.VISIBLE
        listView.visibility = View.GONE
        txtStatus.visibility = View.GONE
    }

    private fun showList() {
        progress.visibility = View.GONE
        listView.visibility = View.VISIBLE
        txtStatus.visibility = View.GONE
    }

    private fun showStatus(message: String) {
        progress.visibility = View.GONE
        listView.visibility = View.GONE
        txtStatus.text = message
        txtStatus.visibility = View.VISIBLE
    }

    private fun fetchTransactions() {
        val token = Authentication.getToken()
        if (token.isNullOrBlank()) {
            showStatus("Please log in to view transactions")
            return
        }

        showLoading()

        ExchangeService.instance.getTransactions("Bearer $token")
            .enqueue(object : Callback<List<Transaction>> {
                override fun onResponse(
                    call: Call<List<Transaction>>,
                    response: Response<List<Transaction>>
                ) {
                    if (!isAdded) return
                    when {
                        response.isSuccessful -> {
                            val body = response.body().orEmpty()
                            transactions.clear()
                            transactions.addAll(body)
                            adapter.notifyDataSetChanged()
                            if (transactions.isEmpty()) {
                                showStatus("No transactions found")
                            } else {
                                showList()
                            }
                        }
                        response.code() == 401 ->
                            handleSessionExpired(requireActivity())
                        else ->
                            showStatus("Failed to load transactions (${response.code()})")
                    }
                }

                override fun onFailure(call: Call<List<Transaction>>, t: Throwable) {
                    if (!isAdded) return
                    showStatus("Network error: ${t.message}")
                }
            })
    }

    private fun formatDate(raw: String?): String {
        if (raw == null) return "—"
        return try {
            val date = inputDateFormat.parse(raw)
            if (date != null) outputDateFormat.format(date) else raw
        } catch (e: Exception) {
            raw
        }
    }

    inner class TransactionAdapter : BaseAdapter() {

        override fun getCount(): Int = transactions.size
        override fun getItem(position: Int): Any = transactions[position]
        override fun getItemId(position: Int): Long = transactions[position].id?.toLong() ?: position.toLong()

        override fun getView(position: Int, convertView: View?, parent: ViewGroup?): View {
            val view = convertView ?: LayoutInflater.from(requireContext())
                .inflate(R.layout.item_transaction, parent, false)

            val tx = transactions[position]

            val txtDirection = view.findViewById<TextView>(R.id.txtDirection)
            val txtUsd = view.findViewById<TextView>(R.id.txtUsdAmount)
            val txtLbp = view.findViewById<TextView>(R.id.txtLbpAmount)
            val txtDate = view.findViewById<TextView>(R.id.txtDate)

            if (tx.usdToLbp) {
                txtDirection.text = "BUY USD"
                txtDirection.setBackgroundColor(Color.parseColor("#4CAF50"))
            } else {
                txtDirection.text = "SELL USD"
                txtDirection.setBackgroundColor(Color.parseColor("#F44336"))
            }

            txtUsd.text = "$ ${usdFormat.format(tx.usdAmount)}"
            txtLbp.text = "L.L. ${lbpFormat.format(tx.lbpAmount)}"
            txtDate.text = formatDate(tx.addedDate)

            return view
        }
    }
}
