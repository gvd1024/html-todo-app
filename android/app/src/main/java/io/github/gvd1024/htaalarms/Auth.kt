package io.github.gvd1024.htaalarms

import android.app.Activity
import android.content.Context
import com.microsoft.identity.client.AcquireTokenSilentParameters
import com.microsoft.identity.client.AuthenticationCallback
import com.microsoft.identity.client.IAccount
import com.microsoft.identity.client.IAuthenticationResult
import com.microsoft.identity.client.ISingleAccountPublicClientApplication
import com.microsoft.identity.client.PublicClientApplication
import com.microsoft.identity.client.SignInParameters
import com.microsoft.identity.client.exception.MsalException
import com.microsoft.identity.client.exception.MsalUiRequiredException

/**
 * Microsoft sign-in (MSAL for Android, single-account mode). Same Azure registration as HTA ("HTML-ToDo-App PoC");
 * the redirect URI carries the release key's hash, so only APKs signed with that key can sign in.
 * Tokens stay inside MSAL's cache and are never logged or stored by this app.
 */
object Auth {
    val SCOPES = listOf("Files.ReadWrite", "User.Read")
    @Volatile private var pca: ISingleAccountPublicClientApplication? = null

    class SignInNeeded(msg: String) : Exception(msg)

    /** Blocking: call off the main thread. */
    fun app(ctx: Context): ISingleAccountPublicClientApplication =
        pca ?: synchronized(this) { pca ?: PublicClientApplication.createSingleAccountPublicClientApplication(ctx.applicationContext, R.raw.msal_config).also { pca = it } }

    /** Blocking. */
    fun account(ctx: Context): IAccount? = try { app(ctx).currentAccount?.currentAccount } catch (e: Exception) { null }

    /** Blocking: a fresh access token without any screen, or SignInNeeded. */
    fun token(ctx: Context): String {
        val app = app(ctx)
        val acc = app.currentAccount?.currentAccount ?: throw SignInNeeded("not signed in")
        try {
            val params = AcquireTokenSilentParameters.Builder().forAccount(acc).fromAuthority(acc.authority).withScopes(SCOPES).build()
            return app.acquireTokenSilent(params).accessToken
        } catch (e: MsalUiRequiredException) {
            throw SignInNeeded("sign-in expired")
        }
    }

    fun signIn(activity: Activity, done: (String?, String?) -> Unit) {
        Thread {
            try {
                val app = app(activity)
                val params = SignInParameters.builder().withActivity(activity).withScopes(SCOPES).withCallback(object : AuthenticationCallback {
                    override fun onSuccess(result: IAuthenticationResult) { activity.runOnUiThread { done(result.account.username, null) } }
                    override fun onError(e: MsalException) { activity.runOnUiThread { done(null, e.errorCode) } }
                    override fun onCancel() { activity.runOnUiThread { done(null, "cancelled") } }
                }).build()
                activity.runOnUiThread { app.signIn(params) }
            } catch (e: Exception) {
                activity.runOnUiThread { done(null, e.javaClass.simpleName + ": " + (e.message ?: "")) }
            }
        }.start()
    }

    /** Blocking. */
    fun signOut(ctx: Context) { try { app(ctx).signOut() } catch (e: Exception) { } }
}
