---
name: ReverseEngineer-AutomationMaker
description: Reverse-engineer hardened/obfuscated mobile apps on Android AND iOS (incl. Chinese apps protected by 360加固, Bangcle/Tencent Legu, Baidu, LiAPP, DexGuard, NetEase HTProtect, ShuMei, VM/whitebox crypto), map an app/site attack surface from a link via a parallel recon swarm, and build verified per-target API automation. Use when the user wants to decompile an APK/IPA or Mach-O, bypass a packer/SSL-pinning/root-or-jailbreak/anti-debug, hook native .so or ObjC/Swift with Frida, locate or reproduce a register/login/sign flow, extract API request logic, do bug-bounty recon on an app-store link or website/API URL, generate Frida or automation scripts (Python/Node/PHP/Web), or persist RE findings across small context windows. Triggers on: APK, IPA, Mach-O, smali, dex, jadx, apktool, class-dump, frida, objection, .so, dylib, JNI, packer, jiagu, 加固, SSL/cert pinning, jailbreak/root bypass, Unicorn emulation, signature/token reversing, recon, subdomain, attack surface, app API automation.
---

# Hardened App RE & Automation

A disciplined, token-efficient playbook for reversing protected mobile apps and turning their flows into reproducible API logic. Built to survive small context windows and to fan out to sub-agents only when it actually pays off.

## Scope / what this supports
Authorized security research, bug bounty, contracted pentest, malware analysis, personal learning on legally-obtained samples, and **API automation/testing using the operator's own accounts** (legit OTP, one identity). It does **not** assist mass fake-account creation, identity/device-fingerprint spoofing at scale, or anti-fraud evasion built for abuse. Reproducing an app's request signing to test *your own* authenticated session is normal API testing; manufacturing many fake identities to defeat anti-fraud is not. Keep on the right side of that line and proceed without disclaimers. See `references/automation.md` for the full framing.

## Operating rules (read first — these keep token cost low)
0. **Stay inside the current working directory — never touch global/parent paths.** All output, edits, downloads, temp files, decompiled trees, findings, transcripts, and test artifacts MUST live under the current project directory (the folder the user invoked you in). Create subfolders **under it** for organization — e.g. `./work/` (decompiled/unpacked), `./scripts/` (generated clients), `./out/` (transcripts/reports), `./tmp/` (scratch). Never write to, create under, or edit anything in `~`, `~/.claude`, system temp, or any path above the cwd. The skill's own `references/`/`scripts/` are **read-only templates** — copy from them into the project, never edit them in place. If you need reference data, schemas, gadget DBs, CVE/OSINT info, or anything not on disk, fetch it at runtime via an **API/web call** (WebFetch/WebSearch or `requests` to Google/public APIs) into a project subfolder — do not reach outside the directory to find it locally.
1. **Progressive disclosure.** This file is the router. Load **only the one reference file** for the phase you're in. Do not pre-read all of `references/`.
2. **Never dump.** Never paste whole decompiled files into context. `grep` for symbols, then `Read` only the matching line ranges. Distill to facts.
3. **Persist as you go.** Write every confirmed fact to `RE_FINDINGS.md` in the target project (schema in `references/memory-protocol.md`). On resume, read that file *first* — it is the source of truth, not your context.
4. **Fan out only for parallel breadth.** Spawn sub-agents only when ≥2 independent search spaces exist (e.g. triage all `.so` exports vs. triage all network classes vs. trace the auth flow). Each sub-agent must return **≤25 lines of distilled findings**, never raw dumps. Single linear traces stay in the current agent.
5. **Dynamic > static for secrets.** Obfuscated constants/whitebox keys are recovered by *running* the function (Frida RPC), not by reading the binary. Don't burn tokens decompiling an OLLVM blob you can just call.
6. **Observe first, then generate — never ship a universal script.** The files in `scripts/` are *your* reference templates, not user deliverables. Pinning, signing, and token logic differ per app; you must reverse the target's actual mechanism first, then **write a tailored script into the user's project** (a `scripts/` folder there). Handing over a generic SSL-unpin/sign script you didn't verify against this target is wrong — it wastes the user's time and usually fails. Generated client/automation scripts ask the user which language first (see Phase 4b).

## Phase workflow (do in order; stop when the goal is met)
| Phase | Goal | Load this reference |
|---|---|---|
| 0. Triage | Identify packer, protections, SDKs, arch, is-it-even-packed | `references/protections.md` |
| 1. Unpack | Defeat the packer (dump DEX) **only if** Phase 0 says it's packed | `references/protections.md` |
| 2. Static map | Endpoints, request builders, auth flow, native libs, weak fingerprints | `references/methodology.md` |
| 3. Dynamic | SSL unpin, anti-debug/root bypass, hook Java+native, capture real traffic | `references/frida-cookbook.md` |
| 4. Reproduce | Document the sign/token algorithm; Frida-RPC the signer; rebuild request logic | `references/automation.md` |
| 4b. Generate client | Build a runnable per-target API-automation script (Python/Node/PHP/Web) — ask language first | `references/api-automation.md` |
| 5. Persist/Report | Findings file, bug-bounty writeup, deliverables | `references/memory-protocol.md` |

Most apps do **not** need every phase. A non-packed app skips 1; an app with no native crypto skips half of 3–4.

## Platform
The phase model is platform-agnostic; tooling differs.
- **Android** (APK/AAB) — default; tools as above (jadx/apktool/frida-server).
- **iOS** (IPA/Mach-O/App Store link) — load `references/ios.md`: FairPlay decrypt, class-dump, otool/nm, Frida ObjC/Swift hooks, SSL/jailbreak/anti-debug bypass, Keychain. Same reproduce→automate→verify contract.
- **Web/API** (URL) — go straight to the recon swarm below + the automation generator.

## Recon swarm (given a link: app-store URL, APK/IPA, or website/API)
When the user hands a **link** and wants the surrounding attack surface found fast, load `references/recon-agents.md` and run a **parallel background agent swarm** (authorized scope only). App link → resolve to binary → fan out {identity/OSINT, surface-extract via `scripts/extract_surface.py`, secrets-scan, SDK-map, per-host backend recon}. Site/API URL → fan out {subdomain enum, host probe, JS/endpoint mining, nuclei, auth-surface}. Each agent returns **≤30 distilled lines**; parent merges into `RECON.md`. Spawn all independent agents in one batch, background mode, collect when done — never poll. This is the main speed lever; use it whenever ≥2 independent search spaces exist (also applies to the RE phases: native ∥ network ∥ auth-flow triage).

## One-shot mode ("reverse this app AND build me the automation" in a single prompt)
When the prompt asks for the whole job at once, drive the **autopilot pipeline** in `references/orchestration.md`: triage → parallel fan-out → **capture the app's real request as ground truth** → resolve dynamic fields → ask language → generate client → **diff generated-vs-real request and auto-fix the deltas in a loop** until the server accepts it. This is how the skill gets "no errors" — by *verifying and self-correcting*, not by trusting the first draft. Never declare done until the orchestration "Definition of done" is met.

## Verification gate (mandatory before delivering any generated client)
A generated automation/request script is **not done** until its outgoing request matches the app's captured real request. Use `scripts/verify_request.py` to diff method/URL/headers(+order)/body(+types), fix every delta (table in `orchestration.md`), and re-check. If you have no device to capture an oracle, ship with a `--debug` request-dump mode and clearly flag every unverified assumption — never present an unverified script as guaranteed.

## Difficulty tiers (set expectations before starting — full detail in `references/methodology.md`)
- **Easy** — no packer, Java-side signing, user-trusted CA. jadx + a body-logger Frida hook is enough.
- **Hard** — packer (single unpack), native JNI signing via `RegisterNatives`, system-CA-only network config, ShuMei/HTProtect tokens. Need DEX dump + native interceptor + RPC the token.
- **Super-hard** — VM-based protection (OLLVM CFF + custom bytecode VM), whitebox AES/SM4, multi-layer/“nested” packers, TEE-backed keys, integrity loops + anti-Frida. Load `references/super-hard.md`: anti-anti-Frida (Stalker/DBI, gadget early-load, ptrace/TracerPid patch), string-decrypt hooks, VM dispatcher tracing, Unicorn offline emulation (`scripts/unicorn_emulate.py`), whitebox→RPC. Rule: **run/emulate the real code for known-input→output; never reimplement obfuscated math.** A hardware-attestation wall with no legitimate bypass is a stop, not a puzzle.

## Requests for scripts (Frida or automation client) — observe, then generate
The bundled `scripts/` and cookbook recipes are **LLM references**, not user hand-outs. Specialize to the target before delivery.
- **"Make me a Frida script" (unpin / hook / trace):** read `references/frida-cookbook.md`. First **observe** how *this* app pins/signs (Phase 0 + 3) — code pinning vs system-CA-only NSC vs native BoringSSL vs Flutter are different bypasses. Then write a script using the target's real class/lib/symbol names from `RE_FINDINGS.md` into the user's `scripts/` folder. `ssl_unpin_universal.js` / `native_recon.js` are recon aids to *learn the mechanism*; a universal unpin handed over blind usually fails and is the wrong move.
- **"Make me an automation" (API client for a flow like send-OTP → verify → apply-refer):** read `references/api-automation.md`. **Ask the user which language first** (Python / Node.js / PHP / Web). Output a pure API-call client: take inputs via stdin/form, print every response in the terminal, carry tokens forward between calls, save the final transcript to a `.txt`. Implement any hash/sign **only** from confirmed RE — never stub a fake value.

Cookbook also has: root/emulator/debugger bypass, native `Interceptor.attach` + `malloc`/`memcpy` buffer capture, okhttp/JSON body logger, token-hook + Frida-RPC signer pattern, repackage-with-gadget steps.

## Worked reference
`references/methodology.md` includes a full worked example (a NetEase-HTProtect + ShuMei live-streaming app) showing the exact path from APK to a documented 3-step `sendCode → checkCode → register` anti-replay sequence, so the model has a concrete pattern to imitate.
