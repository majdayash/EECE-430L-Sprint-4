package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class Wallet(
    @SerializedName("usd_balance") val usdBalance: Float,
    @SerializedName("lbp_balance") val lbpBalance: Float
)
