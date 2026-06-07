#!/usr/bin/env python3
"""
verify_request.py — the "no-error" gate for generated API clients.

Diffs a request your generated client is about to send against the app's REAL captured
request (the ground-truth oracle from Frida/mitmproxy), and pinpoints the deltas that
cause sign-mismatch / 4xx. Run this in the orchestration self-verify loop until clean.

Capture the real request as a .json oracle like:
{
  "method": "POST",
  "url": "https://api.TARGET.com/pub/user/sendCode",
  "headers": {"Content-Type":"application/json; charset=utf-8","User-Agent":"okhttp/4.x", ...},
  "header_order": ["Content-Type","User-Agent", ...],
  "body": "<exact raw body bytes as string>"
}

Usage:
  from verify_request import diff_request
  deltas = diff_request(oracle_json_path, my_method, my_url, my_headers, my_body)
  if deltas: print('\n'.join(deltas))   # fix each, re-run
"""
import json, sys

# headers that clients/libraries add automatically and that usually DON'T matter for signing
_VOLATILE = {"content-length", "host", "connection", "accept-encoding"}

def _norm_headers(h):
    return {k.lower(): v for k, v in h.items()}

def diff_request(oracle_path, method, url, headers, body):
    o = json.load(open(oracle_path, encoding="utf-8"))
    deltas = []

    if method.upper() != o["method"].upper():
        deltas.append(f"[method] mine={method} real={o['method']}")
    if url != o["url"]:
        deltas.append(f"[url] mine={url} real={o['url']}")

    mine_h, real_h = _norm_headers(headers), _norm_headers(o["headers"])
    for k, rv in real_h.items():
        if k in _VOLATILE:
            continue
        if k not in mine_h:
            deltas.append(f"[header missing] {k}: real='{rv}'")
        elif mine_h[k] != rv:
            deltas.append(f"[header value] {k}: mine='{mine_h[k]}' real='{rv}'")
    for k in mine_h:
        if k not in real_h and k not in _VOLATILE:
            deltas.append(f"[header extra] {k}: '{mine_h[k]}' (app does not send this — strip it)")

    # header order (matters when a sign covers header order)
    if "header_order" in o:
        mine_order = [k for k in headers.keys() if k.lower() not in _VOLATILE]
        real_order = [k for k in o["header_order"] if k.lower() not in _VOLATILE]
        if [k.lower() for k in mine_order] != [k.lower() for k in real_order]:
            deltas.append(f"[header order] mine={mine_order} real={real_order}")

    # body: exact bytes first, then structural diff to localize
    mb = body if isinstance(body, str) else body.decode("utf-8", "replace")
    rb = o["body"]
    if mb != rb:
        deltas.append("[body raw] differs (see structural diff below)")
        try:
            mj, rj = json.loads(mb), json.loads(rb)
            for k, rv in rj.items():
                if k not in mj:
                    deltas.append(f"  [body missing key] {k} = {rv!r} ({type(rv).__name__})")
                elif mj[k] != rv:
                    deltas.append(f"  [body value] {k}: mine={mj[k]!r}({type(mj[k]).__name__}) real={rv!r}({type(rv).__name__})")
            for k in mj:
                if k not in rj:
                    deltas.append(f"  [body extra key] {k} = {mj[k]!r}")
            if list(mj.keys()) != list(rj.keys()):
                deltas.append(f"  [body key order] mine={list(mj.keys())} real={list(rj.keys())}")
        except Exception:
            deltas.append("  (body not JSON — compare raw bytes/encoding: gzip? form-encoded? encrypted?)")
    return deltas

if __name__ == "__main__":
    # demo: python verify_request.py oracle.json candidate.json
    cand = json.load(open(sys.argv[2], encoding="utf-8"))
    d = diff_request(sys.argv[1], cand["method"], cand["url"], cand["headers"], cand["body"])
    print("CLEAN ✓ request matches the app" if not d else "DELTAS:\n" + "\n".join(d))
    sys.exit(1 if d else 0)
