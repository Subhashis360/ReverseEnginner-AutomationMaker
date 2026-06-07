# Super-hard targets: VM-protection, whitebox crypto, anti-instrumentation, TEE

Load only when Phase 0 flags one of these. Principle throughout: **you don't need to understand the protection — you need its output for known input.** Prefer running/emulating the real code over manually defeating the math.

## A. Anti-Frida / anti-instrumentation (gets you on the device at all)
Symptoms: app exits on launch under Frida, or hooks "work" but values are decoys.
- **Detection vectors & counters:** scans `/proc/self/maps` & `/proc/self/task/*/status` for `frida`/`gum`/`gadget` → hook `openat`/`fopen` and scrub matching reads; checks TCP 27042 → spawn with `frida -f` (no default port) or use a non-default gadget; named-thread scan (`gmain`,`gum-js-loop`) → rename via gadget config; `ptrace(PTRACE_TRACEME)` self-attach → `Interceptor.replace(ptrace, ()=>0)`; periodic CRC of `.text` / inline-hook detection → use **Stalker/DBI tracing** instead of inline `Interceptor.attach`, or hook above the integrity check.
- **Strategy:** prefer **early-instrumentation** (gadget loaded at `attachBaseContext` before the protector's watchdog), or **LD_PRELOAD/zygisk** module. If integrity loops are aggressive, do data capture with **Stalker** (no code patching) or hardware watchpoints (`MemoryAccessMonitor`).
- **TracerPid:** patch `/proc/self/status` reads to report `TracerPid: 0`.

## B. OLLVM control-flow-flattening + string encryption
- CFF makes static reading useless. Don't fight the dispatcher statically. Either (a) **trace** the real execution with Frida Stalker to recover the effective basic-block order for your input, or (b) **decrypt strings dynamically**: hook the string-decrypt routine (often one function called everywhere with an index/ptr) and dump `index → plaintext`. Find it by `Interceptor.attach`-ing candidates and watching which returns readable text.
- Recover constants by hooking the consumer, not by deobfuscating the producer.

## C. VM-based protection (custom bytecode interpreter)
The function is compiled to bytecode run by an in-binary VM (big dispatch loop over an opcode table).
- **Locate the dispatcher:** the hottest loop with an indexed jump/`switch` over a byte stream; `capstone`-disassemble around `JNI_OnLoad`→registered fn to find the handler table.
- **Trace, don't reverse:** Frida Stalker on the dispatcher logging `(opcode, operands)` per step gives you the program for a given input. Diff traces across inputs to find input-dependent branches (where your secret transform lives).
- **Or emulate** the whole native function with Unicorn (§E) — feed input, read output, ignore the VM entirely.

## D. Whitebox crypto (AES/SM4 with no key in memory)
There is no extractable key — it's fused into lookup tables.
- **Pragmatic:** RPC the whole encrypt/decrypt function (frida-cookbook §6). Done.
- **Off-device:** lift the tables and run the whitebox as a black box with a known-plaintext oracle; or apply published whitebox attacks (DCA/DFA) only if you must run fully offline. 95% of the time, RPC is the answer.

## E. Unicorn emulation harness (run a native function without the device)
Use when you need the transform offline and RPC isn't viable. Skeleton: `scripts/unicorn_emulate.py`.
Workflow:
1. From Ghidra/r2 get the target fn's file offset, and the addresses of any libc calls it makes.
2. Map the `.so` segments into Unicorn at their load addresses; set up a stack.
3. **Hook unmapped reads/imports**: stub `malloc`/`memcpy`/`strlen`/`__stack_chk`/JNI calls with Python callbacks (return sane values); log every memory read so you can supply traced values.
4. Put input in a buffer, set args per AAPCS64 (`x0..x7`), set `LR` to a sentinel, emulate until `LR`.
5. Read the output buffer. Validate against one real on-device sample, then you have an offline signer.

## F. TEE / hardware-backed keys (Keystore `StrongBox`, attestation)
Keys live in the TEE; the CPU never sees them. You cannot extract them. Options: RPC the `sign`/`mac` operation through the app (the TEE still signs for you while the app runs), or, for attestation tokens (SafetyNet/Play Integrity/device attest), understand you're being asked to forge hardware attestation — out of scope for legitimate own-account testing; treat a hard attestation wall as a stop, not a puzzle to brute.

## G. Multi-layer / nested packers
Dump, then detect the *second* protector on the dumped DEX/so and repeat. Dump **late** (after each stage's init returns). Merge dexes; fix headers. Record each layer in `RE_FINDINGS.md`.

## Decision shortcut
Can you run the app on a device you control? → **RPC the target function** (A→done for B/C/D/F-sign). Must be fully offline? → **emulate (E)** or trace+reimplement (C). Hardware attestation wall with no legit bypass? → **stop and report**, don't manufacture attestations.
