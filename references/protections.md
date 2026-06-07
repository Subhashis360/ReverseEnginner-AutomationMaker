# Phase 0–1: Protection identification & unpacking

Goal: in <2 minutes know **what is protecting the app** and **whether you even need to unpack**. Do not start decompiling blind.

## 0.1 Triage commands (cheap, run first)
```bash
unzip -l app.apk | grep -E 'classes.*dex|lib/|assets/'      # dex count, native libs, asset blobs
unzip -p app.apk AndroidManifest.xml | grep -aoE 'package="[^"]+"|android:name="[^"]*Application[^"]*"'
# Per-dex string scan for packer/SDK signatures and real namespaces (python, no `strings` needed on Windows):
```
Then run a python ascii-scan over each `.dex` counting `Lcom/...` namespace prefixes. **If you see the app's own real package (`Lcom/vendor/app/...`) with hundreds of classes, it is NOT DEX-packed — skip Phase 1 entirely.** If `classes.dex` is tiny and the only classes are a loader stub, it's packed.

## 0.2 Packer / protector fingerprint table
| Signature in APK | Protector | Unpack approach |
|---|---|---|
| `libjiagu.so`, `libjiagu_art.so`, `assets/qihoo` | **360加固 (Qihoo)** | Dump DEX from memory after class load (frida-dexdump / Dobby) |
| `libshella*.so`, `libBugly`?no, `libDexHelper.so`, `assets/classes0.jar` | **Bangcle / Tencent Legu (乐固)** | frida-dexdump; Legu decrypts on first access |
| `libbaiduprotect.so`, `baiduprotect1.jar` | **Baidu Protect** | frida-dexdump; some methods JIT-restored — dump late |
| `libDexHelper.so` + `libSecShell` | **SecNeo / LIAPP** | Multi-stage; dump after `Application.onCreate` |
| `libexec.so`, `libexecmain`, `ijiami` | **爱加密 Ijiami** | Memory dump + fix-up |
| DexGuard names (`o.AbC`, string-encrypted, reflection-heavy) | **DexGuard/Arxan** | Not a memory packer — deobfuscate statically + Frida string-decrypt hooks |
| `lib*.so` huge + only `JNI_OnLoad` export + obfuscated strings | **OLLVM-protected native** (often NetEase/whitebox) | Don't read statically — RPC or Unicorn the function |

## 0.3 Chinese protection / anti-fraud SDKs (often present even when DEX isn't packed)
These are the things that actually break naive API replay. Detect by lib name + Java package.
| Lib / package | SDK | What it produces | How you handle it |
|---|---|---|---|
| `libNetHTProtect.so`, `com.netease.htprotect` | **NetEase HTProtect (易盾)** anti-cheat | `AntiCheatResult.token` per request scene; `ioctl()` device token | Hook `HTProtect.getToken(int,String)` / `getTokenAsync` / `ioctl`; RPC it for live tokens. Constants (appId `YD...`, businessId hashes) are in the Java wrapper in cleartext. |
| `libsmsdk.so`, `com.ishumei.smantifraud` | **ShuMei 数美** device risk | `SmAntiFraud.getDeviceId()` → `smid` | Hook `getDeviceId`; it's stored as `DEVICE_ID`. Bound to session server-side. |
| `libtersafe*.so`, `com.tencent.*` | **Tencent 防水墙/MSDK** | captcha/sig token | Hook the token getter; usually a callback. |
| `libalive_detected.so`, `libnenn.so` | Liveness / face anti-spoof | only gates KYC flows | Skip unless target flow needs face. |
| `libmmkv.so` `com.tencent.mmkv` | MMKV storage (not protection) | local KV (tokens cached here!) | Pull `/data/data/<pkg>/files/mmkv/*` — session tokens/fingerprints often cached in plaintext. |
| `libwcdb.so` | Tencent WCDB (encrypted SQLite) | local DB | Hook the WCDB key or dump via app context. |

## 0.4 Network-config trap (the #1 silent failure)
Always read `res/xml/network_security_config.xml`:
- `base-config ... <certificates src="system"/>` with **no `user`** → a Burp/mitmproxy CA in the **user** store is *not trusted*. Interception silently fails before any code pinning. Fixes: (a) install CA into **system** store (Magisk `cert-fixer` / `move-certs`), (b) patch NSC to add `<certificates src="user"/>` and repackage, or (c) bypass entirely at the Frida layer (`scripts/ssl_unpin_universal.js`).
- `cleartextTrafficPermitted="true"` only for `127.0.0.1`/`localhost` is normal (RTC/IM loopback).

## 0.5 Unpack (Phase 1) — only if packed
1. Push matching `frida-server` (same arch: check `lib/arm64-v8a` vs `armeabi-v7a`).
2. `frida -U -f <pkg> -l dump.js --no-pause` where dump.js is frida-dexdump (`pip install frida-dexdump; frida-dexdump -U -f <pkg>`).
3. Some packers restore methods lazily — trigger app flows, then dump again; merge dexes.
4. If memory dump yields broken headers, fix with `dexfixer`/`baksmali` or re-dump after the protector finishes init (hook `Application.attachBaseContext` return).
5. Rebuild a jadx-readable set from dumped `.dex`. Record packer + method in `RE_FINDINGS.md`.

Output of Phase 0–1 to persist: `{packer, packed:bool, native_protectors[], anti_fraud_sdks[], nsc_posture, arch, unpack_method}`.
