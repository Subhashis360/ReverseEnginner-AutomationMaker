/*
 * ssl_unpin_universal.js — universal TLS pinning / trust bypass
 * frida -U -f <pkg> -l ssl_unpin_universal.js --no-pause
 *
 * Covers: X509TrustManager / SSLContext, OkHttp CertificatePinner, HttpsURLConnection,
 * Conscrypt, TrustManagerImpl (Android Platform), Flutter/native BoringSSL.
 * Note the NSC trap: a system-CA-only network_security_config rejects user-store CAs
 * regardless of code pinning — this forces verification success so your proxy cert is accepted.
 */
'use strict';
function L(m){ console.log('[unpin] ' + m); }
function safe(f){ try{ f(); }catch(e){} }

Java.perform(function () {
  // 1) Install an all-trusting TrustManager into a fresh SSLContext default
  safe(function () {
    var X509TM = Java.use('javax.net.ssl.X509TrustManager');
    var SSLContext = Java.use('javax.net.ssl.SSLContext');
    var TM = Java.registerClass({
      name: 'org.x.UTM' + Math.floor(Math.random()*1e6),
      implements: [X509TM],
      methods: {
        checkClientTrusted: function () {},
        checkServerTrusted: function () {},
        getAcceptedIssuers: function () { return []; }
      }
    });
    var tms = [TM.$new()];
    var init = SSLContext.init.overload(
      '[Ljavax.net.ssl.KeyManager;','[Ljavax.net.ssl.TrustManager;','java.security.SecureRandom');
    init.implementation = function (km, _tm, sr) { init.call(this, km, tms, sr); };
    L('SSLContext.init overridden with all-trusting TM');
  });

  // 2) Android platform TrustManagerImpl (covers most https on modern Android)
  safe(function () {
    var TMI = Java.use('com.android.org.conscrypt.TrustManagerImpl');
    if (TMI.verifyChain) {
      TMI.verifyChain.implementation = function (certs, host, clientAuth, untrusted, ocsp, tlsExt) {
        L('TrustManagerImpl.verifyChain bypassed for ' + host);
        return certs;
      };
    }
    if (TMI.checkTrustedRecursive) {
      TMI.checkTrustedRecursive.implementation = function () { return Java.use('java.util.ArrayList').$new(); };
    }
  });

  // 3) OkHttp CertificatePinner (all overloads)
  safe(function () {
    var CP = Java.use('okhttp3.CertificatePinner');
    CP.check.overload('java.lang.String', 'java.util.List').implementation = function () { L('okhttp3.CertificatePinner.check bypassed'); };
    safe(function(){ CP.check.overload('java.lang.String','[Ljava.security.cert.Certificate;').implementation=function(){}; });
    safe(function(){ CP.check.overload('java.lang.String','kotlin.jvm.functions.Function0').implementation=function(){}; });
    L('OkHttp pinning bypassed');
  });

  // 4) HttpsURLConnection hostname verifier
  safe(function () {
    var HUC = Java.use('javax.net.ssl.HttpsURLConnection');
    HUC.setDefaultHostnameVerifier.implementation = function (v) { L('HUC default verifier dropped'); };
    HUC.setSSLSocketFactory.implementation = function (f) { L('HUC SSLSocketFactory drop'); };
  });

  // 5) TrustKit / appcelerator-style PinningTrustManager (best-effort)
  ['com.datatheorem.android.trustkit.pinning.OkHostnameVerifier',
   'okhttp3.internal.tls.OkHostnameVerifier'].forEach(function (cn) {
    safe(function () {
      var V = Java.use(cn);
      V.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function () { return true; };
    });
  });
});

// 6) Native BoringSSL / Conscrypt / Flutter pinning
setImmediate(function () {
  ['SSL_CTX_set_custom_verify', 'SSL_set_custom_verify'].forEach(function (sym) {
    var f = Module.findExportByName(null, sym);
    if (!f) return;
    var cb = new NativeCallback(function () { return 0; }, 'int', ['pointer', 'pointer', 'pointer']);
    Interceptor.attach(f, { onEnter: function (a) { a[2] = cb; } });
    L('native ' + sym + ' verify forced OK');
  });
  var gvr = Module.findExportByName(null, 'SSL_get_verify_result');
  if (gvr) Interceptor.replace(gvr, new NativeCallback(function () { return 0; }, 'long', ['pointer']));
});
