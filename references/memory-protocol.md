# Phase 5: Findings persistence + multi-agent coordination (token discipline)

The point: a fresh context (any model) must resume instantly by reading **one file**, and sub-agents must return distilled facts, not dumps.

## 5.1 The findings file — `RE_FINDINGS.md` (in the target project root)
Create/update it continuously. It is the single source of truth across context windows. Schema:

```markdown
# RE_FINDINGS — <app> <version>
_status: <phase>/<done|blocked>  updated: <date>_

## Target
pkg / version / arch / minSdk-target

## Phase0 protections
packed: <yes/no + packer> | native_protectors: [...] | anti_fraud: [HTProtect appId=..., ShuMei area=...]
nsc: <system-CA-only | user-trusted | cleartext-loopback>

## Endpoints (base: <host>)
- POST /pub/user/sendCode   — request OTP
- POST /pub/user/checkCode  — mints registerToken
- POST /pub/user/register   — consumes registerToken
... (one line each, with what it does / what it mints/consumes)

## Auth flow / sequence
sendCode -> checkCode[registerToken] -> register   (anti-replay: registerToken one-time)

## Dynamic fields
| field | source (class.method / native) | lifetime | reproduce |
|---|---|---|---|
| yd_device_id | HTProtect.getToken(3000, <biz>) | short | RPC |
| identification | f1.a() UUID(androidId,build) | stable | reproduce/RPC |
| registerToken | /checkCode response | one-time | call pre-step |

## Native map (RegisterNatives)
libX.so: Java_..._sign(...) -> 0x... (offset)

## Constants / secrets (cleartext found)
HTProtect appId=..., businessId=..., 3rd-party keys=...

## Security findings (bounty)
- leftover dev host http://...:port
- weak deterministic device id
- plaintext token cache in MMKV

## Frida assets
scripts/<app>_trace.js (body+token logger), ssl_unpin (works/notes)

## Open / next
- [ ] pin down header interceptor exact names
- [ ] RPC signer for <fn>
```

Rules: append facts the moment they're confirmed; keep each entry one line; never paste decompiled bodies here — only conclusions + `file:line` pointers.

## 5.2 Harness memory (if available)
If the running model has a persistent memory store, write a short pointer there: `{app, pkg, RE_FINDINGS path, current phase, biggest blocker}` so the next session recalls where to look. Keep the heavy detail in `RE_FINDINGS.md` (portable across models); memory holds only the pointer + 1-line status. Don't duplicate.

## 5.3 When to spawn sub-agents (and how to keep them cheap)
Spawn **only** when there are independent search spaces that parallelize. Good split for a fresh hard target:
- Agent A — **native triage**: enumerate every `.so`, exports, which only export `JNI_OnLoad`, string-obfuscation level. Return: table of lib→{exports, protector, interesting}.
- Agent B — **network/endpoint triage**: all retrofit/okhttp endpoints + the body builder + interceptor class. Return: endpoint list + builder/interceptor `file:line`.
- Agent C — **auth-flow trace**: from login/register UI down to the request, listing dynamic fields + their sources. Return: the sequence + field table.

Hard limits to put in each sub-agent prompt:
- "Return **≤25 lines**: conclusions + `file:line` only. No code bodies, no file dumps."
- "Grep first; Read only matching ranges."
- "If you find a secret/endpoint/finding, output it as one bullet."

The parent merges the three short reports into `RE_FINDINGS.md`. Do **not** spawn agents for a single linear trace — that costs more tokens than doing it inline. Never poll agents in a loop; collect when they return.

## 5.4 Resume protocol (start of every session on a known target)
1. Read `RE_FINDINGS.md` (only this).
2. Jump to the `## Open / next` list.
3. Load the single `references/*.md` for that phase.
4. Continue; append new facts. Never re-derive what's already recorded.
