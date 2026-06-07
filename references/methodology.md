# Phase 2: Static mapping + difficulty tiers + worked example

Goal: from decompiled source, produce the **request model** — endpoints, the body/param builder, the auth/sign flow, the dynamic fields, and which native lib computes what. Stay surgical: grep → read ranges → record facts.

## 2.1 Decompile efficiently
```bash
jadx --no-res -j 4 -d _src app.apk      # source only (skip res) — faster
jadx --no-src -d _meta app.apk          # manifest + resources only when you just need NSC/strings
```
For a big app, **don't open files randomly**. Drive everything from grep:
```bash
grep -rhoE 'loadLibrary\("[^"]+"\)' _src/sources | sort | uniq -c        # which .so are loaded
grep -rnE '@(be\.o|be\.f|POST|GET)\("/[^"]+"' _src/sources | grep -iE 'login|register|sms|code|auth|sign|user'   # retrofit endpoints (be.o=@POST, be.a=@Body after obfuscation)
grep -rlE 'addInterceptor|OkHttpClient|Retrofit\.Builder' _src/sources    # network module
grep -rlE 'getDeviceId|SmAntiFraud|HTProtect|nativeSign|MessageDigest|HmacSHA|Mac\.getInstance' _src/sources
```

## 2.2 Find the request-body builder
Modern apps build a `Map`→JSON `RequestBody`. Find the fluent builder (`.d("k",v)...a()` style or `put`). Two outcomes:
- **Builder also signs** → the sign code is right there (HMAC/MD5 over sorted params). Document the canonicalization (sort order, separators, secret position).
- **Builder is dumb JSON, signing is in an OkHttp Interceptor** → find the class implementing the (often single-letter, obfuscated) `okhttp3.Interceptor`. Its `intercept(chain)` adds headers like `sign`, `timestamp`, `nonce`, `token`. Read it; note exact header names, order, and the input string to the hash.

## 2.3 Classify each dynamic field
For every non-static field in the request, record its **source** and **lifetime**:
| Field type | Typical source | Lifetime | Reproduce by |
|---|---|---|---|
| `timestamp`/`t` | `System.currentTimeMillis()` | per-request | trivial |
| `nonce`/`requestId` | UUID/random | per-request, single-use server-side | generate fresh |
| device fingerprint | `Settings.Secure.ANDROID_ID` + `Build.*` hashed | stable per device | reproduce or RPC the getter |
| anti-cheat token | NetEase HTProtect / ShuMei / Tencent native | short-lived, server-validated | **RPC the live getter** (never fake) |
| session token | login response, stored in MMKV/SP | per-session | from your login |
| **challenge token** (e.g. `registerToken`) | returned by a *prior* endpoint | one-time | **must call the prior endpoint first** |
| sign/HMAC | hash over canonical string + secret | per-request | reproduce algo or RPC native signer |

The **challenge token** and the **anti-cheat token** are what make naive replay fail. Always check whether the target request consumes a value produced by an earlier call — that earlier call is the "missing pre-step."

## 2.4 Native side
- `.so` exporting only `JNI_OnLoad` ⇒ natives registered via `RegisterNatives` ⇒ you can't `getExportByName` the sign function. Hook `RegisterNatives` (see frida-cookbook) to map Java native method → native fn pointer, then `Interceptor.attach` that pointer.
- Obfuscated strings (only libc/zlib visible) ⇒ constants are encrypted ⇒ recover by RPC, not static reading.
- For the sign function, blind-hook `memcpy`/`malloc`/`EVP_*`/`MD5_Update`/`SHA*_Update` to capture the pre-hash plaintext and the digest — this reveals the canonical input string even when the algorithm is obfuscated.

## 2.5 Always-collect security findings (bug-bounty value, independent of automation)
- Hardcoded secrets / appIds / business keys in the Java wrapper (HTProtect appId, AppsFlyer key, 3rd-party API keys).
- Leftover internal/dev hosts (`http://192.168.x:port`, `*.test.`, staging) in prod build.
- Weak/predictable device identifiers (e.g. `UUID(androidId.hashCode(), build.hashCode())` — low entropy).
- Exported components / browsable deeplinks with sensitive intents.
- Tokens cached in plaintext MMKV/SharedPrefs/WCDB.
- `/pub/*` (pre-auth) endpoints — enumerate their surface.

---

## 2.6 Worked example — NetEase HTProtect + ShuMei live-streaming app
A real walkthrough the model should imitate.

**Phase 0**: 10 dexes with real `com/vendor/*` namespaces ⇒ **not packed**. Libs: `libNetHTProtect.so` (HTProtect), `libsmsdk.so` (ShuMei), `libalive_detected.so` (liveness). NSC: `base-config` system-CA-only ⇒ user-cert MITM fails.

**Phase 2**: `grep` retrofit paths ⇒ all under `/pub/user/*`: `sendCode`, `sendEmail`, `checkCode`, `register`, `tokenLogin`, `startV2`. Body builder = a dumb `Map→JSON` (`okhttp3.RequestBody.create(json)`), **no signing in it**. Register body fields include `identification`, `registerToken`, `yd_device_id`, plus profile data.

Tracing each dynamic field:
- `identification = UUID(ANDROID_ID.hashCode(), (MODEL/BRAND/BOARD/PRODUCT/DEVICE/ID).hashCode())` → weak deterministic fingerprint (a finding).
- `yd_device_id = HTProtect.getToken(3000, "<businessId>").token` for scene `track_register` → live anti-cheat token.
- `smid = SmAntiFraud.getDeviceId()` → ShuMei device id.
- `registerToken = m5.f.f()` ← stored by `m5.f.p(rt)` ← returned by **`POST /pub/user/checkCode`** as `CheckSmsCodeModel.registerToken`.

**Conclusion — the server enforces a 3-step anti-replay sequence:**
```
sendCode/sendEmail  →  checkCode [mints one-time registerToken]  →  register [consumes it + live HTProtect token + smid]
```
Naive replay of `/register` alone fails because `registerToken` is blank/stale and `yd_device_id` is a dead captured token. The fix for legit own-account testing: drive the real sequence, and RPC `HTProtect.getToken` for a live token (Phase 4). HTProtect constants (appId `YD00xxxxxxxxxxxx`, businessId hashes) sat in the Java wrapper in cleartext — note the *location pattern*, the specific values are per-app.

This pattern — *find the challenge-minting pre-step + RPC the native anti-cheat token* — generalizes to most Chinese social/fintech/live apps.
