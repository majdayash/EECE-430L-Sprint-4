package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class Token(
    @SerializedName("token") val token: String
)
