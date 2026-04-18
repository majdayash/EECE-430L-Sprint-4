package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class Transaction(
    @SerializedName("usd_amount") val usdAmount: Float,
    @SerializedName("lbp_amount") val lbpAmount: Float,
    @SerializedName("usd_to_lbp") val usdToLbp: Boolean,
    @SerializedName("id") val id: Int? = null,
    @SerializedName("added_date") val addedDate: String? = null
)

data class TransactionResponse(
    @SerializedName("ok") val ok: Boolean,
    @SerializedName("transaction") val transaction: Transaction
)
