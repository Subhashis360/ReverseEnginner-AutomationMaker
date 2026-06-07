# ReverseEngineer-AutomationMaker

> An LLM **agent skill** that turns any capable model into a disciplined mobile reverse-engineer and API-automation builder — Android + iOS, hardened/obfuscated targets, link-driven recon, and *verified* automation generation.

A single, model-agnostic [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill (works with any model that supports skills). It gives the model a phased, token-efficient playbook for reversing protected apps and reproducing their flows as runnable, self-verified API clients — instead of one giant brittle prompt.

---

## Why this exists

Reversing hardened apps (Chinese packers, NetEase HTProtect, ShuMei, VM/whitebox crypto) and rebuilding their API flows is a *process*, not a one-shot. Done naively, an LLM burns its whole context window, dumps decompiled files everywhere, reimplements native crypto wrong, and hands you a script that 401s. This skill encodes the pro workflow so the model:

- **Stays cheap on tokens** — a lean router loads only the one reference it needs per phase (progressive disclosure).
- **Survives small context windows** — every fact is persisted to `RE_FINDINGS.md`; a fresh session resumes from the file, not from memory.
- **Goes faster with multi-agent fan-out** — parallel sub-agents triage native libs ∥ network ∥ auth-flow, each returning ≤25 distilled lines.
- **Doesn't guess** — it captures the app's *real* request as ground truth, then diffs the generated request against it and auto-fixes the deltas until the server accepts it.

## Features

| Area | What it covers |
|---|---|
| **Android** | jadx/apktool, packer ID & unpack (360加固, Bangcle/Legu, Baidu, Ijiami…), `RegisterNatives` mapping, native `Interceptor`, ShuMei/HTProtect token hooks |
| **iOS** | FairPlay decrypt, `class-dump`/`otool`, Frida ObjC/Swift hooks, SSL/jailbreak/anti-debug bypass, Keychain dump, arm64e/PAC notes |
| **Protections** | packer fingerprint tables, anti-fraud SDK map, the system-CA-only network-config trap, anti-Frida/integrity loops |
| **Super-hard** | OLLVM CFF, VM-dispatcher tracing, whitebox crypto → RPC, **Unicorn offline emulation harness**, TEE handling |
| **Recon swarm** | give it an app-store link, an APK/IPA, or a website/API URL → parallel agents map hosts, endpoints, secrets, subdomains, SDKs into `RECON.md` |
| **Automation generator** | asks your language (**Python / Node.js / PHP / Web**) and emits a pure API client: prints every response, carries tokens forward, saves the transcript to `.txt` |
| **Verification loop** | `verify_request.py` diffs generated-vs-real request (method/URL/headers+order/body+types) — the "no-error" gate before delivery |

## How it works

```
SKILL.md  ── lean router: phases, decision tree, when to spawn agents, what to load
  references/
    protections.md     Phase 0–1  identify packer/SDKs/NSC; unpack only if needed
    methodology.md     Phase 2    endpoints, body builder, dynamic-field tracing
    frida-cookbook.md  Phase 3    unpin, anti-debug, RegisterNatives, body/token hooks, RPC signer
    ios.md             iOS branch of all phases
    automation.md      Phase 4    reproduce sign/token; RPC vs reimplement; failure diagnosis
    api-automation.md  Phase 4b   per-language client generator (the contract + skeletons)
    super-hard.md      VM / whitebox / anti-instrumentation / Unicorn / TEE
    recon-agents.md    link-driven parallel recon swarm
    memory-protocol.md findings schema + multi-agent coordination + resume protocol
    orchestration.md   one-shot autopilot + self-verifying delivery loop
  scripts/             LLM reference templates (adapt per target, never ship blind):
    ssl_unpin_universal.js  native_recon.js  unicorn_emulate.py
    verify_request.py       extract_surface.py
```

The model reads `SKILL.md`, then pulls exactly one reference per phase. Heavy knowledge never sits in context unless it's being used.

## Installation

This is a Claude Code / agent **skill** (a folder with `SKILL.md` + references).

**Personal (all your projects):**
```bash
git clone https://github.com/<you>/ReverseEngineer-AutomationMaker.git \
  ~/.claude/skills/ReverseEngineer-AutomationMaker
```
On Windows: clone into `%USERPROFILE%\.claude\skills\ReverseEngineer-AutomationMaker`.

**Project-scoped:** clone into `<your-project>/.claude/skills/` instead.

The skill auto-loads on next session. It triggers on intents like *decompile this APK*, *bypass SSL pinning*, *find the register flow*, *recon this app-store link*, or *build me the automation for this OTP flow*.

> Recommended host tooling for the model to drive: `jadx`, `apktool`, `frida`, `objection`, `python3` (+ `unicorn`, `capstone` for offline emulation); iOS adds `class-dump`, `otool`, a jailbroken/TrollStore device. The skill degrades gracefully when a tool is missing.

## Usage examples

```
"Reverse this APK and find how the login request is signed."
"Bypass SSL pinning on this app on my test device and log the register flow."
"Recon this app-store link — map the backend hosts and any leaked keys."
"Build me a Python client for the sendCode → verifyCode → applyRefer flow."   # asks language, verifies output
```

## Scope & responsible use

This skill is built for **authorized** work: bug-bounty within program scope, CTF/wargames, contracted penetration testing, malware analysis, RE of legally-obtained samples for vulnerability research and interoperability, and **API automation/testing using your own accounts**. Reverse engineering for security research and interoperability is a legitimate, established practice.

It deliberately **excludes** building tooling whose purpose is mass fake-identity/account manufacturing or spoofing device-fingerprint/liveness anti-fraud to create many synthetic identities. Reproducing an app's behaviour for **one identity you legitimately control** is normal API testing; manufacturing many to defeat anti-fraud is not. You are responsible for staying within the law and the authorization of the target you test.

## Contributing

PRs welcome — especially new packer/SDK fingerprints, Frida recipes for fresh protections, and additional language targets for the automation generator. Keep references lean (the router pattern only works if each file stays focused) and **never commit a real third-party app's extracted secrets, keys, or internal hosts** — use placeholders.

## License

MIT — see [LICENSE](LICENSE).
