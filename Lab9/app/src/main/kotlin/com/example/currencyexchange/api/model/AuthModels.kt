package com.example.currencyexchange.api.model

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("user_name") val userName: String,
    @SerializedName("password") val password: String
)

data class RegisterRequest(
    @SerializedName("user_name") val userName: String,
    @SerializedName("password") val password: String
)

data class AuthResponse(
    @SerializedName("token") val token: String
)
