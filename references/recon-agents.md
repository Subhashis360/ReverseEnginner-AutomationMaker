# Link-driven recon swarm (multi-agent attack-surface mapping)

Invoked when the user gives a **link** — an app-store URL, an APK/IPA, or a website/API base — and wants the rest of the surface discovered fast. The win here is **parallelism**: independent search spaces run as concurrent background agents, each returning a small distilled block that the parent merges into `RECON.md`. Authorized-scope recon only (bug bounty program scope / pentest engagement / your own asset).

## When to swarm vs. do it inline
Swarm only when there are ≥2 genuinely independent search spaces (there usually are for recon). For a single lookup, do it inline — agents have spawn cost. Run agents **in the background, in one batch**, then collect; never poll them in a loop.

## Hard rules for every spawned agent (put these in each agent prompt)
- "Return **≤30 lines**: findings as bullets only — host/endpoint/secret/version + `source`. No raw dumps, no tool transcripts."
- "Dedupe and rank by usefulness; mark anything sensitive (key, token, internal host, exposed panel) with `!`."
- "If you hit a dead end, say so in one line and stop — don't burn tokens."
- Give each agent its **own slice** (a host, a lib, a path set) so they don't overlap.

## Swarm A — target is an APP (store link or APK/IPA)
Resolve the link to a binary first (`ipatool`/store metadata → bundle/package id → the file), then fan out:
| Agent | Slice | Returns |
|---|---|---|
| **identity/OSINT** | store page + developer | package/bundle id, all versions, dev name, sibling apps by same dev, privacy labels, declared SDKs |
| **surface extract** | the binary | every host/URL/API base, deeplink schemes, exported components / Info.plist URL types (use `scripts/extract_surface.py`) |
| **secrets scan** | the binary + assets | hardcoded API keys, Firebase/GCP/AWS config, JWTs, OAuth client ids/secrets, tokens, private endpoints (`!`) |
| **3rd-party SDK map** | libs/frameworks | analytics/anti-fraud/payment/IM SDKs + their known endpoints (feeds the protections table) |
| **backend recon** | each host found | hand off to Swarm B per host |

## Swarm B — target is a SITE / API (URL)
| Agent | Slice | Returns / tools |
|---|---|---|
| **subdomain enum** | apex domain | `subfinder -d x`, `amass enum -passive`, `gau`/`waybackurls` → unique subs |
| **host probe** | discovered subs | `httpx -title -tech-detect -status-code -sc` → live hosts + tech + interesting titles |
| **endpoint/JS mining** | live web hosts | fetch + parse JS for API paths, `swagger`/`openapi.json`, `.env`, `/api/*`, GraphQL introspection |
| **vuln/tech nuclei** | live hosts | `nuclei -t exposures,cves,misconfiguration` → flagged issues (`!`) |
| **auth surface** | API base | login/register/oauth/reset endpoints, CORS posture, rate-limit headers, token format |

(If those CLI tools aren't installed, the agent uses HTTP fetches + parsing and says which tools would deepen it — don't fail silently.)

## Merge → `RECON.md` (parent writes this)
```markdown
# RECON — <target>  (scope: <program/asset>)  updated: <date>
## Identity
package/bundle, versions, developer, sibling apps
## Hosts / APIs
- api.x.com  (live, nginx, /pub/* auth)   [from binary + httpx]
- internal.x.test  ! leftover dev host    [from binary]
## Subdomains (live)
...
## Endpoints of interest
- POST /pub/user/register ...  ! GraphQL introspection open
## Secrets / exposures
- ! Firebase web key AIza... (binary)
- ! S3 bucket x-uploads (public listing)
## SDKs / tech
analytics=..., anti-fraud=ShuMei, payment=..., cdn=...
## Next
- [ ] probe IDOR on /user/{id}
- [ ] enumerate /pub/* surface
```
Rank by impact; every `!` is a candidate finding for the bounty/pentest report. Cross-link the app and its backend so RE (this skill's other phases) and web recon feed each other — the app reveals the API; the API recon reveals more endpoints to look for in the app.

## Speed knobs
- Spawn all independent agents in **one batch, background mode**; collect when done.
- Cap depth per agent; breadth-first beats deep rabbit holes for first-pass recon.
- Persist incrementally so a context reset resumes from `RECON.md`, not from zero.
