package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class ExchangeRates(
    @SerializedName("usd_to_lbp") val usdToLbp: Float,
    @SerializedName("lbp_to_usd") val lbpToUsd: Float
)
