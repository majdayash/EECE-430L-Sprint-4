package com.example.currencyexchange.api

import com.example.currencyexchange.api.model.ExchangeRates
import com.example.currencyexchange.api.model.Token
import com.example.currencyexchange.api.model.Transaction
import com.example.currencyexchange.api.model.TransactionResponse
import com.example.currencyexchange.api.model.User
import com.example.currencyexchange.api.model.Wallet
import retrofit2.Call
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT

private const val BASE_URL = "http://10.0.2.2:5000/"

interface Exchange {
    @GET("exchangeRate")
    fun getExchangeRate(): Call<ExchangeRates>

    @POST("user")
    fun addUser(@Body user: User): Call<User>

    @POST("authentication")
    fun authenticate(@Body user: User): Call<Token>

    @POST("transaction")
    fun addTransaction(
        @Header("Authorization") authorization: String?,
        @Body transaction: Transaction
    ): Call<TransactionResponse>

    @GET("transaction")
    fun getTransactions(
        @Header("Authorization") authorization: String?
    ): Call<List<Transaction>>

    @PUT("wallet")
    fun updateWallet(
        @Header("Authorization") token: String,
        @Body wallet: Wallet
    ): Call<Wallet>
}

object ExchangeService {
    val instance: Exchange by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(Exchange::class.java)
    }
}
