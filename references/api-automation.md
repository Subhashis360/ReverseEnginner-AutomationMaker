# Phase 4b: Generate the API-automation client (per-target, per-language)

This is invoked when the user wants a runnable automation of an app flow (e.g. send-OTP → verify-OTP → apply-refer). The output is a **pure API client**: only HTTP calls, **print every response to the terminal**, carry tokens forward between calls, and **save the final response to a `.txt` file**. No browser/UI driving — just the APIs you recovered in Phase 2–4.

## Rule 0 — ask the language first
Before writing anything, ask the user which language: **Python / Node.js / PHP / Web (HTML+vanilla JS) / other**. Don't assume. Use their app/endpoint knowledge already in `RE_FINDINGS.md`; only the language and the target flow inputs are unknown.

## Rule 1 — never ship a universal/canned script
Generate the client **from observed behaviour**, not a template you paste blind. If a step needs a hash/sign/token, you must already know its exact recipe from RE (Phase 2–4). If you don't yet, go reverse it first — do not guess or stub it with a fake. The bundled `scripts/` are *your* references; the user gets a script tailored to *their* target's real endpoints, fields, and crypto.

## The flow contract (the shape every generated client follows)
For a typical OTP→verify→refer flow:
```
1. input: email / phone (and later, the OTP) from the user via stdin (or form fields for web)
2. send-OTP:
     - if the endpoint needs a hash/sign/nonce/timestamp -> compute it with a dedicated function
       (recipe comes from RE; if native, call it via the Frida-RPC signer, frida-cookbook §6)
     - POST the send-OTP API
     - PRINT the full response (status + headers if relevant + body)
     - extract & keep session/token/ticket from the response
3. input: OTP code from the user
4. verify-OTP:
     - reuse the session/token from step 2 (header or body, exactly as the app does)
     - POST verify API ; PRINT full response
     - extract the next token (jwt / loginToken / registerToken / refer ticket)
5. apply-refer (if present):
     - put the jwt/token from step 4 into the header/body as the app does
     - POST refer API ; PRINT full response
6. write the final response (and ideally a transcript of all steps) to <flow>_<timestamp>.txt
```
Every step prints its response in the terminal. Tokens always flow from the previous response into the next request exactly where the app puts them (match header name / body key from RE).

## Python skeleton (requests) — adapt endpoints/fields/hash from RE_FINDINGS.md
```python
#!/usr/bin/env python3
import requests, json, sys, time, hashlib

BASE = "https://api.TARGET.com"          # from RE
S = requests.Session()
S.headers.update({"User-Agent": "okhttp/4.x", "Content-Type": "application/json; charset=utf-8"})  # match app

def show(label, r):
    print(f"\n=== {label} === HTTP {r.status_code}")
    try: body = r.json(); print(json.dumps(body, indent=2, ensure_ascii=False))
    except Exception: body = r.text; print(body)
    return body

def make_hash(params: dict) -> str:
    # ONLY if RE shows a hash/sign is required. Implement the EXACT recipe (canonical order, secret, algo).
    raw = "&".join(f"{k}={params[k]}" for k in sorted(params)) + "&secret=SECRET_FROM_RE"
    return hashlib.md5(raw.encode()).hexdigest()      # or hmac-sha256 / sm3 — whatever RE says

transcript = []
def cap(label, body): transcript.append({label: body})

# --- 1. inputs ---
account = input("email or phone: ").strip()

# --- 2. send OTP ---
ts = str(int(time.time()*1000))
payload = {"account": account, "timestamp": ts}          # field names from RE
# payload["sign"] = make_hash(payload)                   # uncomment if RE requires
r = S.post(f"{BASE}/pub/user/sendCode", json=payload)
body = show("send-otp", r); cap("send_otp", body)
session_token = (body or {}).get("data", {}).get("token", "")   # path from RE

# --- 3. input OTP ---
otp = input("OTP code: ").strip()

# --- 4. verify OTP ---
vp = {"account": account, "code": otp, "token": session_token}   # carry token exactly as app does
r = S.post(f"{BASE}/pub/user/checkCode", json=vp)
body = show("verify-otp", r); cap("verify_otp", body)
jwt = (body or {}).get("data", {}).get("loginToken", "")         # next token

# --- 5. apply refer (optional) ---
refer = input("refer code (blank to skip): ").strip()
if refer:
    S.headers["Authorization"] = jwt                              # header name from RE
    r = S.post(f"{BASE}/user/applyRefer", json={"code": refer})
    body = show("apply-refer", r); cap("apply_refer", body)

# --- 6. persist ---
out = f"flow_{int(time.time())}.txt"
open(out, "w", encoding="utf-8").write(json.dumps(transcript, indent=2, ensure_ascii=False))
print(f"\nsaved -> {out}")
```

## Node.js skeleton (axios) — same contract
```js
const axios = require('axios');
const readline = require('readline');
const fs = require('fs');
const crypto = require('crypto');
const BASE = 'https://api.TARGET.com';
const http = axios.create({ baseURL: BASE, headers: { 'User-Agent':'okhttp/4.x', 'Content-Type':'application/json; charset=utf-8' }, validateStatus: () => true });
const ask = q => new Promise(res => { const rl = readline.createInterface({input:process.stdin,output:process.stdout}); rl.question(q, a => { rl.close(); res(a.trim()); }); });
const show = (label, r) => { console.log(`\n=== ${label} === HTTP ${r.status}`); console.log(typeof r.data==='object'?JSON.stringify(r.data,null,2):r.data); return r.data; };
const makeHash = p => crypto.createHash('md5').update(Object.keys(p).sort().map(k=>`${k}=${p[k]}`).join('&')+'&secret=SECRET_FROM_RE').digest('hex'); // only if RE requires
(async () => {
  const transcript = [];
  const account = await ask('email or phone: ');
  let p = { account, timestamp: Date.now().toString() };
  // p.sign = makeHash(p);
  let r = await http.post('/pub/user/sendCode', p); let b = show('send-otp', r); transcript.push({send_otp:b});
  const token = b?.data?.token || '';
  const otp = await ask('OTP code: ');
  r = await http.post('/pub/user/checkCode', { account, code: otp, token }); b = show('verify-otp', r); transcript.push({verify_otp:b});
  const jwt = b?.data?.loginToken || '';
  const refer = await ask('refer code (blank to skip): ');
  if (refer) { r = await http.post('/user/applyRefer', { code: refer }, { headers: { Authorization: jwt } }); b = show('apply-refer', r); transcript.push({apply_refer:b}); }
  const out = `flow_${Date.now()}.txt`; fs.writeFileSync(out, JSON.stringify(transcript, null, 2)); console.log(`\nsaved -> ${out}`);
})();
```

## PHP CLI skeleton (curl) — same contract
```php
<?php
$BASE = "https://api.TARGET.com";
function req($url, $payload, $headers = []) {
  $ch = curl_init($url);
  curl_setopt_array($ch, [CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>json_encode($payload),
    CURLOPT_RETURNTRANSFER=>true, CURLOPT_HTTPHEADER=>array_merge(["Content-Type: application/json"], $headers)]);
  $res = curl_exec($ch); $code = curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
  return [$code, $res];
}
function show($label, $code, $res){ echo "\n=== $label === HTTP $code\n$res\n"; return json_decode($res, true); }
function makeHash($p){ ksort($p); $raw=""; foreach($p as $k=>$v){$raw.="$k=$v&";} return md5($raw."secret=SECRET_FROM_RE"); } // only if RE requires
$t = [];
fwrite(STDOUT,"email or phone: "); $account = trim(fgets(STDIN));
$p = ["account"=>$account, "timestamp"=>strval(round(microtime(true)*1000))];
// $p["sign"] = makeHash($p);
[$c,$r] = req("$BASE/pub/user/sendCode", $p); $b = show("send-otp",$c,$r); $t["send_otp"]=$b;
$token = $b["data"]["token"] ?? "";
fwrite(STDOUT,"OTP code: "); $otp = trim(fgets(STDIN));
[$c,$r] = req("$BASE/pub/user/checkCode", ["account"=>$account,"code"=>$otp,"token"=>$token]); $b = show("verify-otp",$c,$r); $t["verify_otp"]=$b;
$jwt = $b["data"]["loginToken"] ?? "";
fwrite(STDOUT,"refer code (blank to skip): "); $refer = trim(fgets(STDIN));
if ($refer !== "") { [$c,$r] = req("$BASE/user/applyRefer", ["code"=>$refer], ["Authorization: $jwt"]); $b = show("apply-refer",$c,$r); $t["apply_refer"]=$b; }
$out = "flow_".time().".txt"; file_put_contents($out, json_encode($t, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE)); echo "\nsaved -> $out\n";
```

## Web GUI variants
Two ways; pick based on whether the target API allows browser cross-origin calls.

**A) Vanilla HTML + JS (fetch).** Works only if the API sends permissive CORS (most mobile APIs don't). Form with inputs + a results `<pre>` that prints every response; a download link writes the transcript to a `.txt` blob.
```html
<!doctype html><meta charset=utf-8>
<input id=acct placeholder="email/phone"><button onclick=sendOtp()>Send OTP</button>
<input id=otp placeholder="otp"><button onclick=verify()>Verify</button>
<input id=refer placeholder="refer code"><button onclick=applyRefer()>Apply</button>
<button onclick=save()>Save .txt</button><pre id=out></pre>
<script>
const BASE="https://api.TARGET.com"; let token="",jwt="",log=[];
const show=(l,d)=>{const t=typeof d==='object'?JSON.stringify(d,null,2):d;out.textContent+=`\n=== ${l} ===\n${t}\n`;log.push({[l]:d});};
async function post(p,b,h={}){const r=await fetch(BASE+p,{method:'POST',headers:{'Content-Type':'application/json',...h},body:JSON.stringify(b)});let d;try{d=await r.json()}catch{d=await r.text()}return d;}
async function sendOtp(){const d=await post('/pub/user/sendCode',{account:acct.value,timestamp:Date.now().toString()});show('send-otp',d);token=d?.data?.token||"";}
async function verify(){const d=await post('/pub/user/checkCode',{account:acct.value,code:otp.value,token});show('verify-otp',d);jwt=d?.data?.loginToken||"";}
async function applyRefer(){const d=await post('/user/applyRefer',{code:refer.value},{Authorization:jwt});show('apply-refer',d);}
function save(){const b=new Blob([JSON.stringify(log,null,2)],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`flow_${Date.now()}.txt`;a.click();}
</script>
```
**B) PHP-backed web (recommended for mobile APIs).** HTML form posts to a PHP endpoint that does the curl server-side (no CORS problem, can compute hashes/sign), echoes each response back to the page, and appends to a `.txt`. Reuse the PHP CLI `req()`/`makeHash()` above inside the POST handler; render `$res` into a `<pre>` and `file_put_contents(..., FILE_APPEND)` the transcript.

## Filling the TODOs
Every `SECRET_FROM_RE`, endpoint path, body field name, token JSON path, and header name comes from `RE_FINDINGS.md`. If a value is still unknown, that's a Phase 2–4 gap — close it by reversing, not by guessing. For native hashes/tokens, wire the client to the Frida-RPC signer instead of reimplementing (frida-cookbook §6 + automation.md §4.2).

## Mandatory self-verify before you hand it over
Don't deliver a "hopefully correct" client. Capture the app's real request once (Frida body logger / mitmproxy) into `oracle.json`, then diff your client's outgoing request against it with `scripts/verify_request.py` and fix every delta (method/url/headers+order/body+types) until it's CLEAN. Full loop + delta→fix table + Definition of Done are in `orchestration.md`. This verification step is what turns a plausible script into a working one.
