# iOS / IPA reverse engineering

The phase model is identical to Android (triage → static → dynamic → reproduce → automate); only the tooling changes. Load this when the target is an `.ipa`, a Mach-O, or an App Store link.

## 0. Acquisition + is-it-encrypted
App Store binaries are **FairPlay-encrypted** (`LC_ENCRYPTION_INFO[_64].cryptid = 1`). You must decrypt before static analysis.
- Download: `ipatool download -b <bundleid>` (needs an Apple ID) or pull from device.
- Decrypt (jailbroken): `frida-ios-dump`, `bagbak`, or `flexdecrypt` / `dumpdecrypted`. On modern devices, **TrollStore** apps and Dopamine/palera1n jailbreaks are the usual path.
- Verify: `otool -l <bin> | grep -A4 LC_ENCRYPTION_INFO` → `cryptid 0` means decrypted.
- Layout: `unzip app.ipa` → `Payload/<App>.app/<MachOBinary>` (+ `Frameworks/`, `Info.plist`, embedded `.mobileprovision`).

## 1. Static (Mach-O)
```bash
otool -L bin                 # linked dylibs/frameworks (pinning libs, crypto, anti-debug)
otool -l bin                 # load commands, segments, encryption, min-OS
otool -hv bin; lipo -info bin# arch (arm64 / arm64e)
nm -gU bin                   # exported symbols
class-dump bin > hdr.h       # ObjC class/method headers (use class-dump-swift / Swift dump for Swift)
xcrun swift-demangle <sym>   # demangle Swift symbols
strings -a bin | grep -Ei 'http|api|key|secret|token'
```
- Decompile in **Hopper / IDA / Ghidra / Binary Ninja**. Map JNI-equivalent: ObjC selectors via `objc_msgSend`; Swift is harder (mangled, no dynamic dispatch table) — lean dynamic.
- `Info.plist`: bundle id, URL schemes (deeplink surface), `ATSExceptions` (cleartext allowances), background modes, declared frameworks.
- Embedded provisioning profile → team id, entitlements, devices (for dev builds).

## 2. iOS protection stack (detect → bypass)
| Protection | Detect | Bypass |
|---|---|---|
| TLS pinning | TrustKit / AFNetworking/Alamofire `ServerTrustPolicy` / native `SecTrustEvaluate` / BoringSSL | SSL-Kill-Switch2; Frida hook `SecTrustEvaluate*` → `errSecSuccess` + native `SSL_CTX_set_custom_verify`; `objection --gadget <app> explore` → `ios sslpinning disable` |
| Jailbreak detection | checks `/Applications/Cydia.app`, `/bin/bash`, `fork()`, `canOpenURL:cydia://`, sandbox write to `/private` | Frida hook `NSFileManager fileExistsAtPath:`, `fork`, `getenv`, `stat`; objection `ios jailbreak disable` |
| Anti-debug | `ptrace(PT_DENY_ATTACH)`, `sysctl(KERN_PROC)`, `getppid` | `Interceptor.replace(ptrace,()=>0)`; patch `sysctl` to clear `P_TRACED` |
| Code obfuscation | string crypt, OLLVM in C/C++ cores | same dynamic tactics as Android: hook the decrypt routine / RPC the function (see super-hard.md) |
| Integrity / re-sign check | validates code signature / `_CodeSignature` | hook the validator; for gadget builds, the entitlement/signature is already broken — patch the check |

## 3. Dynamic (Frida on iOS)
- **Jailbroken:** install `frida` from Cydia/Sileo → `frida -U -f <bundleid> -l s.js`.
- **Non-jailbroken:** re-sign with FridaGadget: `objection patchipa --source app.ipa` (or `frida-gadget` + `ios-deploy`/Sideloadly) → run, attach.
- **ObjC hooking:**
```js
if (ObjC.available) {
  var NSURLReq = ObjC.classes.NSMutableURLRequest;       // capture outgoing requests
  Interceptor.attach(NSURLReq['- setHTTPBody:'].implementation, {
    onEnter(a){ var d = new ObjC.Object(a[2]); console.log('[body]', d.bytes().readUtf8String(d.length())); }
  });
  // generic ObjC method trace:
  var m = ObjC.classes.YourClass['- signRequest:'];
  Interceptor.attach(m.implementation, { onEnter(a){ console.log('arg', new ObjC.Object(a[2]).toString()); },
                                         onLeave(r){ console.log('ret', new ObjC.Object(r).toString()); } });
}
```
- **Networking layers to hook:** `NSURLSession`/`NSURLConnection`, `NSMutableURLRequest -setHTTPBody:` / `-setValue:forHTTPHeaderField:`, Alamofire (`SessionManager`), or native `libcurl`/BoringSSL. Same "capture the body builder" tactic as Android.
- **Keychain / data:** `objection ios keychain dump`; sandbox at `/var/mobile/Containers/Data/Application/<UUID>/` (NSUserDefaults plist, Core Data, `Documents/`).
- **Swift:** no ObjC runtime — `Interceptor.attach(Module.findExportByName(<framework>, <mangled>))`; find symbols via `nm`/`Module.enumerateExports`.

## 4. Reproduce + automate
Identical contract to Android (api-automation.md, orchestration.md): capture the real request as the oracle, build the per-language client, diff with `verify_request.py`, RPC any native signer. iOS-specific signer RPC: expose the ObjC sign selector via `rpc.exports`.

## Notes
- arm64e (newer devices) has **pointer authentication (PAC)** — strip/sign pointers when patching; Frida handles most of this, raw Interceptor on arm64e may need PAC-aware addresses.
- If the app is App-Store-only and you have no jailbreak/TrollStore device, you're limited to static on a decrypted IPA from a sharing source + traffic capture via a proxy with a profile-trusted CA (still blocked by code pinning until bypassed).
