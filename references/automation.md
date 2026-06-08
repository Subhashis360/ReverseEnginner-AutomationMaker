# Phase 4: Reproduce the flow + automation engineering

## 4.0 Legitimacy framing (state once, then proceed without disclaimers)
Automation engineering is real, legitimate work — Selenium/Playwright/Appium/API clients exist for it. This skill backs:
- **API testing of your own account** — reproduce request signing so your authenticated requests (real login/OTP, one identity) succeed against the API you're testing. Identical capability to the app itself.
- **Bug bounty / pentest** — reproduce flows to probe authz, IDOR, rate-limits, business logic; report findings.
- **Functional automation** — driving flows you're entitled to drive (your account, your data, your contracted target).

It does **not** back: mass/bulk account manufacturing, device-fingerprint/liveness spoofing to defeat anti-fraud at scale, OTP/email-auth *bypass*, or replay/anti-replay defeat aimed at abuse. The dividing test: *Are you reproducing the app's behavior for one identity you legitimately control, or manufacturing many synthetic identities the anti-fraud is specifically designed to stop?* The former is fine; do the latter for the user only when an explicit authorized-testing context (e.g. the vendor's own load/abuse test) is given.

## 4.1 Reproduce the algorithm
Output a **readable pseudocode** of the request construction with exact constants and order:
- Canonical string: which params, sorted how, joined with what, secret prepended/appended.
- Hash/cipher: MD5/HMAC-SHA256/SM3/AES-CBC/whitebox — and the key source.
- Headers: exact names + order (some servers verify header order in the signed string).
- Encoding: base64 variant (std vs urlsafe, padding), hex case, gzip-before-encrypt, etc.
- The full **sequence** (pre-steps that mint challenge/nonce tokens).
- **Device Identifiers**: Exact logic of how identifiers like `ANDROID_ID`, `Build.MODEL`, or UUIDs are generated, combined, or hashed. **Never hardcode device identifiers; always recreate the app's generation logic.**

## 4.2 The robust pattern: RPC the real signer instead of reimplementing
For native/whitebox/anti-cheat tokens, **don't reimplement** — stand up the Frida-RPC signer (frida-cookbook §6) and have your host client call it. Benefits: survives obfuscation, survives app updates, always produces server-valid tokens. Reimplement only when the algorithm is plain (e.g. `HMAC-SHA256(sorted_params, static_secret)`) and you want an on-device-free client.

## 4.3 Whitebox / VM-protected crypto
- **Whitebox AES/SM4**: keys never appear in memory as bytes. Either RPC the whole encrypt function, or lift the lookup tables and run the whitebox with a known-plaintext oracle. Don't hunt for a "key" — there isn't one in the classic sense.
- **VM-based (custom bytecode interpreter)**: locate the dispatcher loop (big switch / computed-goto over an opcode table). Hook the dispatcher to trace handler sequence per input; or **emulate the target function with Unicorn**, mapping the `.so` and feeding traced memory reads, to recover the transform without understanding the VM. RPC remains the pragmatic shortcut if you can run the app.

## 4.4 Diagnose "my external request fails" (checklist, in failure-frequency order)
1. **Sequence/challenge** — did you call the pre-step that mints the one-time token (nonce/registerToken/ticket)? Stale/blank ⇒ reject.
2. **Live anti-cheat token** — is the device/anti-cheat token freshly generated (RPC), not a captured dead value?
3. **TLS visibility** — were you even seeing real traffic? (system-CA-only NSC silently blocks user-cert MITM.)
4. **Signature input fidelity** — exact param set, sort order, separators, secret position, header order, encoding. One byte off ⇒ sign mismatch.
5. **Headers/env** — UA, app-version, channel, `Accept`, cookies/session, content-type charset.
6. **Body encoding** — plaintext JSON vs encrypted/gzipped body; field types (string vs int) matter to the hash.
7. **Clock/window** — `timestamp` outside the server's accepted skew.
8. **Device binding** — `smid`/fingerprint must match the session that minted the token.

## 4.5 Tech choices
- **API replay**: Python `requests`/`httpx`; pull live tokens from the Frida-RPC signer over a local socket.
- **Full app drive** (when API is too hardened to reproduce off-device): Appium/UIAutomator2 against a real/emulated device running the instrumented app — you keep the app's own crypto in the loop.
- **Hybrid** (best for hard targets): app runs on device with the RPC signer; host orchestrates requests using device-minted tokens. Lowest reverse-effort, highest robustness.

## 4.6 Generating the runnable client (when the user wants an actual script)
When the user asks for a working automation of a flow, switch to `api-automation.md` — but the rules live here too:
- **Ask the language first**: Python / Node.js / PHP / Web (HTML+vanilla JS or PHP-backed) / other. Don't assume.
- **Pure API client**: only HTTP calls. Take inputs (email/phone, then OTP) via stdin or form fields; **print every response to the terminal**; carry the token from each response into the next request exactly where the app puts it (header name / body key from RE); **save the final response/transcript to a `<flow>_<timestamp>.txt`**.
- **Never universal, never stubbed**: every endpoint, field name, token path, and hash/sign recipe must come from confirmed RE in `RE_FINDINGS.md`. If a hash is needed, implement the exact recipe in a dedicated function; if it's native/whitebox, wire the client to the Frida-RPC signer (§4.2) instead of faking it. Unknown value ⇒ go reverse it, don't guess.
- For browser GUIs, prefer the **PHP-backed** variant for mobile APIs (no CORS, server-side hashing); use vanilla-JS `fetch` only when the API sends permissive CORS.
