#!/usr/bin/env python3
"""
extract_surface.py — pull the attack surface out of an APK / IPA / extracted dir / single binary.
Pure stdlib (no deps). Used by the recon swarm's "surface extract" + "secrets scan" agents.

  python extract_surface.py <app.apk | app.ipa | dir | binary>

Outputs (deduped, sorted): hosts, full URLs, deeplink schemes, IPs, and likely secrets.
Distill the output before putting it in RECON.md — don't paste the whole dump.
"""
import sys, os, re, zipfile, io

URL   = re.compile(rb'https?://[A-Za-z0-9\.\-_:/%?&=#@~+]+')
HOST  = re.compile(rb'\b([a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b', re.I)
IP    = re.compile(rb'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b')
SCHEME= re.compile(rb'\b([a-z][a-z0-9.+\-]{2,30})://', re.I)

SECRETS = [
    ("AWS access key",      re.compile(rb'AKIA[0-9A-Z]{16}')),
    ("Google API key",      re.compile(rb'AIza[0-9A-Za-z\-_]{35}')),
    ("Firebase DB",         re.compile(rb'[A-Za-z0-9\-]+\.firebaseio\.com')),
    ("GCP/Firebase appid",  re.compile(rb'\d:\d+:android:[a-f0-9]+')),
    ("Slack token",         re.compile(rb'xox[baprs]-[0-9A-Za-z\-]{10,48}')),
    ("Stripe key",          re.compile(rb'(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{16,}')),
    ("JWT",                 re.compile(rb'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}')),
    ("Private key block",   re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ("Generic secret kv",   re.compile(rb'(?i)(?:api[_-]?key|secret|access[_-]?token|client[_-]?secret)["\':= ]{1,4}[A-Za-z0-9_\-]{12,}')),
]

# noise hosts to drop from the "interesting" view (still counted, just deprioritized)
NOISE = ('schemas.android.com','w3.org','apache.org','google.com/apis','example.com',
         'googleapis.com','gstatic.com','android.com','apple.com','swift.org')

def iter_blobs(path):
    if os.path.isdir(path):
        for root,_,files in os.walk(path):
            for f in files:
                fp=os.path.join(root,f)
                try: yield fp, open(fp,'rb').read()
                except Exception: pass
    elif zipfile.is_zipfile(path):
        z=zipfile.ZipFile(path)
        for n in z.namelist():
            if n.endswith('/'): continue
            try: yield n, z.read(n)
            except Exception: pass
    else:
        yield path, open(path,'rb').read()

def main(path):
    urls=set(); hosts=set(); ips=set(); schemes=set(); secrets={}
    for name,data in iter_blobs(path):
        for m in URL.findall(data): urls.add(m.decode('latin1'))
        for m in HOST.findall(data):
            h=(m if isinstance(m,bytes) else m[0]).decode('latin1') if not isinstance(m,bytes) else m.decode('latin1')
        for m in re.findall(rb'https?://([A-Za-z0-9\.\-]+)', data): hosts.add(m.decode('latin1'))
        for m in IP.findall(data):
            s=m.decode('latin1')
            if not s.startswith(('0.','127.','255.')): ips.add(s)
        for m in SCHEME.findall(data):
            s=m.decode('latin1').lower()
            if s not in ('http','https','file','content','data','android','javascript'): schemes.add(s)
        for label,rx in SECRETS:
            for m in rx.findall(data):
                v=(m if isinstance(m,bytes) else m).decode('latin1','replace')[:80]
                secrets.setdefault(label,set()).add((v, name))

    def interesting(h): return not any(n in h for n in NOISE)
    ih=sorted(h for h in hosts if interesting(h))

    print(f"# surface: {path}\n")
    print(f"## hosts ({len(ih)} interesting / {len(hosts)} total)")
    for h in ih: print("  ", h)
    print(f"\n## api-ish URLs")
    for u in sorted(u for u in urls if '/api' in u or '/v1' in u or '/v2' in u or '/pub/' in u)[:80]: print("  ", u)
    print(f"\n## deeplink schemes"); [print("  ", s+"://") for s in sorted(schemes)]
    print(f"\n## private/internal IPs"); [print("  ", i) for i in sorted(ips)]
    print(f"\n## SECRETS (verify before trusting; ! = sensitive)")
    for label,vals in secrets.items():
        for v,src in sorted(vals)[:20]:
            print(f"  ! {label}: {v}   <- {src}")

if __name__=="__main__":
    if len(sys.argv)<2: print(__doc__); sys.exit(1)
    main(sys.argv[1])
