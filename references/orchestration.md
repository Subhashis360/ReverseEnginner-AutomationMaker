# One-shot orchestration + self-verifying delivery (the "no-error" loop)

Invoked when the user says, in one prompt, "reverse this app and build me the automation." This is the autopilot: drive all phases, fan out where parallel, and **do not declare done until the generated script's request is byte-identical to the app's real request and the server accepts it.** "Zero error" is achieved by *verification + auto-correction*, not by hoping the first draft is right.

## The ground-truth principle (this is what eliminates errors)
You cannot guess a hardened request correctly from static reading alone — there's always a header, a field type, an encoding, or a token you miss. So you **capture the app's own request as the oracle**, then make your script reproduce it exactly:
1. Run the app on a controlled device with the body/okhttp logger + SSL bypass (Phase 3) → capture the **real** send-OTP/verify/refer requests: full URL, method, **every header in order**, and the exact body bytes.
2. Capture the **real responses** too (they define the token JSON paths).
3. Your generated client must emit a request that **diffs clean** against the captured real one. Any delta = a bug to fix *before* delivery.

## Autopilot pipeline (single prompt → working script)
```
[0] Triage (protections.md)         packed? protectors? anti-fraud? NSC posture? arch?
        └─ if packed → unpack, else skip
[1] Parallel fan-out (memory-protocol.md §5.3) — spawn ONLY if breadth justifies:
        A native triage   B endpoint/builder triage   C auth-flow + dynamic-field trace
        each returns ≤25 distilled lines → merge into RE_FINDINGS.md
[2] Capture ground truth (frida-cookbook.md)  real request+response for each step of the flow
[3] Resolve every dynamic field (methodology.md §2.3)
        static (ts/nonce) → compute ; native/anti-cheat → Frida-RPC signer ; challenge → call pre-step
[4] Ask language (api-automation.md Rule 0)   Python/Node/PHP/Web
[5] Generate client → run it → DIFF generated request vs captured real request (scripts/verify_request.py)
        └─ mismatch? auto-fix (see delta table) → re-run → re-diff   (loop, max ~5 iters)
[6] Server accepts + response matches app's → write RE_FINDINGS.md + deliver script + short report
```
Steps [0]-[3] may be skipped to the extent `RE_FINDINGS.md` already has them (resume protocol). Don't re-derive recorded facts.

## Pre-flight checklist before writing the client (all must be known, else go reverse it)
- [ ] base URL + exact path for each step
- [ ] method + content-type (incl. charset) for each step
- [ ] full header set **and order** the app sends (from capture)
- [ ] body schema with **field types** (string vs int vs bool) and key names/order
- [ ] every dynamic field's source + how to produce a live value
- [ ] the inter-step token flow (what each response yields, where the next request consumes it)
- [ ] any pre-step that mints a one-time challenge/nonce

If any box is unchecked, that's a reverse-engineering gap — close it; do not stub or guess.

## Auto-fix delta table (generated request ≠ real request → cause → fix)
| Symptom in diff / server reply | Root cause | Fix in the client |
|---|---|---|
| sign/HMAC mismatch, 4xx "sign" | canonical string wrong | match param sort, separators, secret position, header inclusion exactly from RE |
| extra/missing header, different order | client added defaults | strip auto-headers; set headers explicitly in the app's order; pin UA/Accept |
| body differs by quotes/spacing | serializer mismatch | match compact vs spaced JSON; same key order; no trailing newline |
| `"123"` vs `123` | field type wrong | cast to the type the app sends |
| 401 with valid-looking token | token dead/replayed | regenerate live via RPC; ensure correct scene/businessId |
| works once then fails | one-time nonce/challenge | call the minting pre-step each run; never reuse |
| empty/again-OTP | session not carried | thread the cookie jar / token from step N into N+1 |
| TLS/connection reset | missing SNI/ALPN/HTTP2, or pinning on *your* side | match protocol (h2), don't pin client side |
| charset/encoding garble | wrong content-type charset or gzip | set `; charset=utf-8`; handle gzip; match base64 variant |

## Definition of done (do not deliver until all true)
1. Generated request diffs clean vs the captured real request (or differences are provably irrelevant, e.g. fresh nonce).
2. The live server returns the same success shape the app gets.
3. Every response is printed to the terminal; final transcript saved to `.txt`.
4. No stubbed/guessed secrets remain; native crypto goes through the RPC signer or a proven reimplementation.
5. `RE_FINDINGS.md` updated; a 5-line report states endpoints, dynamic fields, and how tokens are produced.

## When you can't run the app (no device/oracle)
Degrade gracefully: build the client from static RE, but **flag every unverified assumption** in comments and the report, and add a `--debug` mode that prints the exact outgoing request so the user can diff it themselves. Never present an unverified script as guaranteed.
