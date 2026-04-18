package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class User(
    @SerializedName("user_name") val userName: String,
    @SerializedName("password") val password: String
)
