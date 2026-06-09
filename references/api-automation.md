# Phase 4b: Generate the API-automation client (per-target, per-language)

This is invoked when the user wants a runnable automation of an app flow (e.g. send-OTP → verify-OTP → apply-refer). The output is a **pure API client**: only HTTP calls, **print every response to the terminal**, carry tokens forward between calls, and **save the final response to a `.txt` file**. No browser/UI driving — just the APIs you recovered in Phase 2–4.

## Rule 0 — ask the language first
Before writing anything, ask the user which language: **Python / Node.js / PHP / Web (HTML+vanilla JS) / other**. Don't assume. Use their app/endpoint knowledge already in `RE_FINDINGS.md`; only the language and the target flow inputs are unknown.

## Rule 1 — never ship a universal/canned script
Generate the client **from observed behaviour**, not a template you paste blind. If a step needs a hash/sign/token, you must already know its exact recipe from RE (Phase 2–4). **CRITICAL: If the app uses a device identifier (e.g. `android_id`, `device_id`, UUID), you MUST analyze how it is generated and implement an equivalent `generate_device_id()` function in the script to create a fresh, valid identifier on every run.** If you don't yet know the hash/device-id algorithm, go reverse it first — do not guess or stub it with a fake. The bundled `scripts/` are *your* references; the user gets a script tailored to *their* target's real endpoints, fields, and crypto.

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

## Python skeleton (User Preferred Standalone Format)
When generating a Python automation script, STRICTLY follow this structural format and set of rules:

### Rules:
1. **Generators**: 
   - If the app needs an IP, include a `generate_random_ip()` function.
   - If the app needs a name, include a `generate_firstname()` function (specifically generating Indian names if possible) and a `last_name` generator if needed.
   - If the app needs an email but **no email verification**, use a `generate_gmail_id()` function (using Faker or similar random logic).
   - If the app **needs email verification**, take the email and OTP from the user via `input()`.
2. **Proxies**: DO NOT include any proxy logic in the script UNLESS the user explicitly asks for it. If they do ask, use proxy variables (`proxy_host`, `proxy_port`, `proxy_username`, `proxy_password`) and configure the HTTP client to use them.
3. **Request Format**: Sequence requests clearly using numbered variables (`url1`, `headers1`, `data1`, `response1`). Extract the JSON, print the response clearly after each request, and store necessary tokens for the next request (`url2`, `headers2`, etc.).
4. **Execution**: Wrap the registration logic in a function (e.g., `def run_automation():`), return success/failure status, and call it at the end of the script to print the final result.

### Template (adapt endpoints/fields/hash from RE_FINDINGS.md):
```python
import json
import random
import socket
import struct
import time
import requests
from faker import Faker

def generate_random_ip():
    return socket.inet_ntoa(struct.pack('>I', random.randint(1, 0xffffffff)))

def generate_gmail_id():
    fake = Faker()
    first_name = fake.first_name().lower()
    last_name = fake.last_name().lower()
    rand_int = random.randint(11, 99999)
    email_provider = 'gmail.com'
    return f"{first_name}{last_name}{rand_int}@{email_provider}"

def generate_firstname():
    first_names = [
        "Aarav", "Aditi", "Amit", "Aaradhya", "Arjun", "Anaya", "Ayush", "Divya", "Gaurav",
        "Isha", "Kunal", "Mira", "Neha", "Rahul", "Riya", "Ved", "Zara", "Varun", "Shreya"
    ]
    random_number = random.randint(1, 100000)
    firstname = random.choice(first_names)
    return f"{firstname}{random_number}"

def run_automation():
    try:
        # 1. Generate or Input Data
        # IF VERIFICATION REQUIRED: email_address = input("Enter email: ")
        # IF NO VERIFICATION:
        email_address = generate_gmail_id()
        ip_address = generate_random_ip()
        random_firstname = generate_firstname()
        
        # --- Request 1 ---
        url1 = "https://api.TARGET.com/endpoint1"
        data1 = json.dumps({"email": email_address}) # Adapt from RE
        headers1 = {
            'Content-Type': 'application/json',
            'X-Forwarded-For': ip_address,
            'User-Agent': 'okhttp/4.9.2'
            # Add other necessary headers (e.g., Device ID) based on RE
        }
        
        response1 = requests.post(url1, headers=headers1, data=data1)
        response_content1 = response1.content
        response10 = json.loads(response_content1)
        print(response10) # Print each response
        
        idToken = response10.get('idToken', '')

        # --- Request 2 ---
        url2 = "http://api.TARGET.com/endpoint2"
        data2 = json.dumps({"name": random_firstname})
        headers2 = {
            'Content-Type': 'application/json',
            'X-Forwarded-For': ip_address,
            'authorization': f'Bearer {idToken}',
            'User-Agent': 'okhttp/4.9.2'
        }
        
        response2 = requests.post(url2, headers=headers2, data=data2)
        response_content2 = response2.content
        response20 = json.loads(response_content2)
        print(response20)
        
        # Save output
        with open('wallet_info.txt', 'a') as f:
            f.write(f'\n{email_address}||{idToken}')
            
        return True, f"Successfully processed {email_address}"

    except json.decoder.JSONDecodeError as e:
        return False, f"Error decoding JSON: {e}"
    except Exception as e:
        return False, f"An error occurred: {e}"

if __name__ == "__main__":
    success, message = run_automation()
    if success:
        print(f"SUCCESS: {message}")
    else:
        print(f"FAILED: {message}")
```

## Node.js skeleton (axios) — User Preferred Format
```js
const axios = require('axios');
const fs = require('fs');

const generateRandomIp = () => `${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}`;
const generateGmailId = () => `user${Math.floor(Math.random() * 90000) + 10000}@gmail.com`; // Replace with faker if needed
const generateFirstname = () => {
    const names = ["Aarav", "Aditi", "Amit", "Aaradhya", "Arjun", "Anaya", "Ayush", "Divya"];
    return `${names[Math.floor(Math.random() * names.length)]}${Math.floor(Math.random() * 100000)}`;
};

async function runAutomation() {
    try {
        const emailAddress = generateGmailId();
        const ipAddress = generateRandomIp();
        const randomFirstname = generateFirstname();

        # --- Request 1 ---
        const url1 = "https://api.TARGET.com/endpoint1";
        const data1 = { email: emailAddress };
        const headers1 = {
            'Content-Type': 'application/json',
            'X-Forwarded-For': ipAddress,
            'User-Agent': 'okhttp/4.9.2'
        };

        const response1 = await axios.post(url1, data1, { headers: headers1 });
        const response10 = response1.data;
        console.log(response10);

        const idToken = response10.idToken || '';

        // --- Request 2 ---
        const url2 = "http://api.TARGET.com/endpoint2";
        const data2 = { name: randomFirstname };
        const headers2 = {
            'Content-Type': 'application/json',
            'X-Forwarded-For': ipAddress,
            'authorization': `Bearer ${idToken}`,
            'User-Agent': 'okhttp/4.9.2'
        };

        const response2 = await axios.post(url2, data2, { headers: headers2 });
        const response20 = response2.data;
        console.log(response20);

        fs.appendFileSync('wallet_info.txt', `\n${emailAddress}||${idToken}`);

        return { success: true, message: `Successfully processed ${emailAddress}` };
    } catch (error) {
        return { success: false, message: `An error occurred: ${error.message}` };
    }
}

(async () => {
    const result = await runAutomation();
    if (result.success) {
        console.log(`SUCCESS: ${result.message}`);
    } else {
        console.log(`FAILED: ${result.message}`);
    }
})();
```

## PHP CLI skeleton (curl) — User Preferred Format
```php
<?php
// Generators
function generateRandomIp() { return mt_rand(0,255).".".mt_rand(0,255).".".mt_rand(0,255).".".mt_rand(0,255); }
function generateGmailId() { return "user".mt_rand(10000,99999)."@gmail.com"; }
function generateFirstname() {
    $names = ["Aarav", "Aditi", "Amit", "Aaradhya", "Arjun", "Anaya"];
    return $names[array_rand($names)].mt_rand(1, 100000);
}

function runAutomation() {
    try {
        $emailAddress = generateGmailId();
        $ipAddress = generateRandomIp();
        $randomFirstname = generateFirstname();

        # --- Request 1 ---
        $url1 = "https://api.TARGET.com/endpoint1";
        $data1 = json_encode(["email" => $emailAddress]);
        $headers1 = [
            'Content-Type: application/json',
            'X-Forwarded-For: ' . $ipAddress,
            'User-Agent: okhttp/4.9.2'
        ];

        $ch1 = curl_init($url1);
        curl_setopt_array($ch1, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $data1,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers1
        ]);

        $response_content1 = curl_exec($ch1);
        curl_close($ch1);
        $response10 = json_decode($response_content1, true);
        echo json_encode($response10) . "\n";

        $idToken = $response10['idToken'] ?? '';

        // --- Request 2 ---
        $url2 = "http://api.TARGET.com/endpoint2";
        $data2 = json_encode(["name" => $randomFirstname]);
        $headers2 = [
            'Content-Type: application/json',
            'X-Forwarded-For: ' . $ipAddress,
            'authorization: Bearer ' . $idToken,
            'User-Agent: okhttp/4.9.2'
        ];

        $ch2 = curl_init($url2);
        curl_setopt_array($ch2, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $data2,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers2
        ]);

        $response_content2 = curl_exec($ch2);
        curl_close($ch2);
        $response20 = json_decode($response_content2, true);
        echo json_encode($response20) . "\n";

        file_put_contents('wallet_info.txt', "\n" . $emailAddress . "||" . $idToken, FILE_APPEND);

        return ["success" => true, "message" => "Successfully processed $emailAddress"];
    } catch (Exception $e) {
        return ["success" => false, "message" => "An error occurred: " . $e->getMessage()];
    }
}

$result = runAutomation();
if ($result["success"]) {
    echo "SUCCESS: " . $result["message"] . "\n";
} else {
    echo "FAILED: " . $result["message"] . "\n";
}
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
