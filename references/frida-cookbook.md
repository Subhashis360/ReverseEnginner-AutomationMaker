# Phase 3: Frida cookbook (dynamic instrumentation)

Adapt these to the target's **real** class/lib names from `RE_FINDINGS.md`. Standalone runnable files live in `../scripts/`. Launch pattern:
```bash
frida -U -f <pkg> -l script.js --no-pause          # spawn
frida -U -n <pkg> -l script.js                     # attach
objection -g <pkg> explore                          # quick interactive (pinning/root toggles)
```
Match `frida-server` arch to the app's loaded ABI. If the app kills Frida, see §6 (gadget) and §5 (anti-Frida).

## 1. SSL pinning / trust bypass
Use `scripts/ssl_unpin_universal.js` (covers TrustManager, OkHttp `CertificatePinner`, `HttpsURLConnection`, Conscrypt, native BoringSSL `SSL_CTX_set_custom_verify`/`SSL_get_verify_result`, Flutter). **Remember the NSC trap**: even with no code pinning, a system-CA-only config rejects user CAs — either bypass in-app (this script forces verification success) or install the CA system-wide. The script makes the app accept your proxy cert regardless.

Minimal OkHttp-only version if you need it tiny:
```js
Java.perform(function(){
  var CP = Java.use('okhttp3.CertificatePinner');
  CP.check.overload('java.lang.String','java.util.List').implementation=function(){ return; };
  var X = Java.use('javax.net.ssl.X509TrustManager');   // plus install permissive TM into SSLContext
});
```

## 2. Root / emulator / debugger / anti-Frida bypass
```js
Java.perform(function(){
  // root checks
  ['java.io.File'].forEach(()=>{});
  var File = Java.use('java.io.File');
  File.exists.implementation=function(){
    var p=this.getAbsolutePath();
    if(/su|magisk|supersu|busybox|frida|xposed/i.test(p)) return false;
    return this.exists();
  };
  var Rt = Java.use('java.lang.Runtime');
  Rt.exec.overload('java.lang.String').implementation=function(c){
    if(/which su|su$|getprop .*magisk/i.test(c)) throw Java.use('java.io.IOException').$new('x');
    return this.exec(c);
  };
  var Sys=Java.use('android.os.SystemProperties');
  try{ Sys.get.overload('java.lang.String').implementation=function(k){
    if(/ro.debuggable|ro.secure|magisk/i.test(k)) return '0';
    return this.get(k);
  };}catch(e){}
});
// native anti-debug: neutralize ptrace
var p=Module.findExportByName(null,'ptrace');
if(p) Interceptor.replace(p,new NativeCallback(()=>0,'long',['int','int','pointer','pointer']));
// anti-frida: hide via spawn gating + scrub maps strings if it scans /proc/self/maps for "frida"
```

## 3. Native recon — map RegisterNatives & dlopen
Use `scripts/native_recon.js`. It hooks `android_dlopen_ext`/`dlopen` (catch the protected lib loading late), `JNI_OnLoad`, and `RegisterNatives` to print `JavaClass.method(sig) -> fnptr (module+offset)`. This is how you find a sign function in a `.so` that only exports `JNI_OnLoad`.

## 4. Native interceptor + blind buffer capture
Once you have the sign fn pointer (from §3) or an export:
```js
var fn = Module.findExportByName('libTarget.so','target_sign'); // or ptr from RegisterNatives
Interceptor.attach(fn, {
  onEnter(a){ this.in=a[1];  console.log('arg1', hexdump(a[1].readByteArray(64))); },
  onLeave(r){ console.log('ret', r); }
});
// Blind-hook the hash plumbing to capture the canonical pre-hash string + digest:
['MD5_Update','SHA1_Update','SHA256_Update','EVP_DigestUpdate'].forEach(function(s){
  var f=Module.findExportByName(null,s); if(!f) return;
  Interceptor.attach(f,{ onEnter(a){ try{ console.log(s,'<=',a[1].readUtf8String(a[2].toInt32())); }catch(e){} }});
});
['memcpy'].forEach(function(s){ /* attach and filter by size/region to catch buffer pre-encryption */ });
```
`malloc`/`memcpy` blind hooks are noisy — filter by size range or caller module to find the plaintext just before hashing/encryption.

## 5. Java + okhttp request/body logger (ground truth of what's sent)
Cheapest reliable capture when okhttp is obfuscated: hook the **app's own body builder** (you found it in Phase 2), not okhttp internals.
```js
Java.perform(function(){
  var B = Java.use('<pkg>.<BodyBuilder>');             // e.g. the d2-style class
  B.d.overload('java.lang.String','java.lang.Object').implementation=function(k,v){
    console.log('[param]', k, '=', v && v.toString()); return this.d(k,v);
  };
});
```
For responses, hook the gson model getters (e.g. `CheckSmsCodeModel.getRegisterToken`) to read minted challenge tokens directly.

## 6. Token-hook + Frida-RPC signer (the key to working automation, legit own-account)
Expose the app's *own* live signer/token function as an RPC so your external test client gets valid values without reimplementing native crypto:
```js
rpc.exports = {
  htToken: function(scene, biz){
    return Java.perform(function(){
      var r = Java.use('com.netease.htprotect.HTProtect').getToken(3000, biz);
      return { code:r.code.value, token:r.token.value };
    });
  },
  sign: function(payload){              // adapt to the real native/Java signer
    return Java.perform(()=> Java.use('<pkg>.<Signer>').sign(payload));
  }
};
```
Driver (host): `frida.get_usb_device().attach(pkg)` → `script.exports.sign(payload)` → assemble the request with a *live* token. This keeps own-account API testing working across app versions because you call the app's real code.

## 7. Repackage with frida-gadget (when device isn't rooted / app kills frida-server)
```bash
apktool d app.apk -o app_dec
# add lib/<abi>/libgadget.so + a System.loadLibrary("gadget") in the Application/early Activity smali
# (or use objection patchapk -s app.apk)
apktool b app_dec -o app_patched.apk
# align + sign:
zipalign -p 4 app_patched.apk app_aligned.apk
apksigner sign --ks my.keystore app_aligned.apk
```
Anti-anti-debug for repackaged builds: rename the gadget lib + its config to a non-`frida`/`gadget` string (some apps scan loaded module names), strip `frida` strings, and load it before the protector's integrity loop runs (`attachBaseContext`). If the app has signature-integrity (checks its own APK signature), hook the signature getter (`PackageManager.getPackageInfo`/`GET_SIGNATURES`) to return the original cert hash.
