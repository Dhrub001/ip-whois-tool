#!/usr/bin/env python3
"""
ipwho.py - screenshot (or text) -> domain/IP pairs -> ASN / ISP / owner table.

Examples:
  python ipwho.py screenshot1.png screenshot2.png
  python ipwho.py list.txt --csv > result.csv
  python ipwho.py --text "www.tiktok.com 23.57.75.160"
  python ipwho.py shot.png --no-lookup        # OCR + parse only
"""
import argparse
import csv
import io
import ipaddress
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

DOMAIN_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})\b", re.I)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b", re.I)

CACHE_FILE = Path.home() / ".ipwho_cache.json"

NEPAL_ISPS = {
    "ncell": "Ncell",
    "worldlink": "WorldLink",
    "subisu": "Subisu",
    "websurfer": "Websurfer",
    "nepal telecommunications": "Nepal Telecom (NTC)",
    "vianet": "Vianet",
    "classic tech": "Classic Tech",
    "dishhome": "DishHome",
    "cg communications": "CG Net",
    "nepalpal": "NepalPal",
}

CDN_CLOUDS = {
    "akamai": "Akamai (CDN)",
    "fastly": "Fastly (CDN)",
    "cloudflare": "Cloudflare (CDN)",
    "google": "Google",
    "amazon": "Amazon / AWS",
    "microsoft": "Microsoft",
    "bytedance": "ByteDance",
    "facebook": "Meta",
    "meta platforms": "Meta",
}


# ---------------------------------------------------------------- OCR / parse
def ocr_image(path):
    """
    OCR a table-style screenshot (domain column + IP column).
    Pass 1: find rows and domains (sparse-text mode, grouped by y position).
    Pass 2: re-read the IP column of each row on its own, digits only (much more accurate).
    """
    try:
        from PIL import Image, ImageOps
        import pytesseract
    except ImportError:
        sys.exit("Missing deps: pip install pillow pytesseract  (and install the tesseract binary)")
    orig = Image.open(path).convert("L")
    S = 2
    big = ImageOps.autocontrast(orig.resize((orig.width * S, orig.height * S), Image.LANCZOS))
    data = pytesseract.image_to_data(big, config="--psm 11", output_type=pytesseract.Output.DICT)
    words = []
    for i, t in enumerate(data["text"]):
        t = t.strip()
        if t and float(data["conf"][i]) >= 0:
            h, l, tp, w = data["height"][i], data["left"][i], data["top"][i], data["width"][i]
            words.append({"cy": tp + h / 2, "l": l, "r": l + w, "t": tp, "b": tp + h, "h": h, "txt": t})
    if not words:
        return ""
    words.sort(key=lambda w: (w["cy"], w["l"]))
    tol = sorted(w["h"] for w in words)[len(words) // 2] * 0.6
    lines, cur, cy = [], [], None
    for w in words:
        if cy is None or abs(w["cy"] - cy) <= tol:
            cur.append(w)
            cy = sum(x["cy"] for x in cur) / len(cur)
        else:
            lines.append(cur)
            cur, cy = [w], w["cy"]
    if cur:
        lines.append(cur)

    # x position where the IP column starts = median left edge of the first numeric token in the right half
    lefts = []
    for ln in lines:
        nums = [w["l"] for w in ln if re.fullmatch(r"[\d.:]{2,}", w["txt"]) and w["l"] > big.width * 0.45]
        if nums:
            lefts.append(min(nums))
    col_x = sorted(lefts)[len(lefts) // 2] - 8 if lefts else None

    out = []
    for ln in lines:
        ln.sort(key=lambda w: w["l"])
        if col_x is None:
            out.append(" ".join(w["txt"] for w in ln))
            continue
        dom = " ".join(w["txt"] for w in ln if w["l"] < col_x)
        ipw = [w for w in ln if w["l"] >= col_x - 4 and not (len(w["txt"]) == 1 and not w["txt"].isdigit())]
        ip_txt = ""
        if ipw:
            box = (max(0, (col_x - 4) // S), max(0, min(w["t"] for w in ln) // S - 3),
                   min(orig.width, max(w["r"] for w in ipw) // S + 6),
                   min(orig.height, max(w["b"] for w in ln) // S + 3))
            crop = orig.crop(box)
            crop = ImageOps.autocontrast(crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS))
            ip_txt = pytesseract.image_to_string(
                crop, config="--psm 7 -c tessedit_char_whitelist=0123456789.:abcdef").strip()
            if not ip_txt:
                ip_txt = " ".join(w["txt"] for w in ipw)
        out.append(f"{dom} {ip_txt}".strip())
    return "\n".join(re.sub(r"(?<=\d)\.\s+(?=\d)", ".", t) for t in out)


def _valid_ip(s):
    try:
        return str(ipaddress.ip_address(s))
    except ValueError:
        return None


def extract_pairs(text):
    """Return a list of (domain, ip) from OCR'd or pasted text, one pair per line."""
    pairs = []
    for line in text.splitlines():
        ip = None
        for m in IPV4_RE.finditer(line):
            ip = _valid_ip(m.group(0))
            if ip:
                break
        if not ip:
            for m in IPV6_RE.finditer(line):
                if m.group(0).count(":") >= 2:
                    ip = _valid_ip(m.group(0))
                    if ip:
                        break
        if not ip:
            continue
        dm = DOMAIN_RE.search(line)
        domain = dm.group(1).lower() if dm else "?"
        pairs.append((domain, ip))
    return pairs


# -------------------------------------------------------------------- lookup
def _http_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "ipwho-cli/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def lookup(ip):
    try:
        d = _http_json(f"https://ipwho.is/{ip}")
        if d.get("success"):
            c = d.get("connection", {})
            return {
                "asn": f"AS{c['asn']}" if c.get("asn") else "",
                "org": c.get("org", ""),
                "isp": c.get("isp", ""),
                "country": d.get("country_code", ""),
                "city": d.get("city", ""),
            }
    except Exception:
        pass
    try:  # fallback
        d = _http_json(f"https://ipinfo.io/{ip}/json")
        asn, _, name = d.get("org", "").partition(" ")
        return {"asn": asn, "org": name, "isp": name,
                "country": d.get("country", ""), "city": d.get("city", "")}
    except Exception as e:
        return {"error": str(e)}


def classify(domain, info):
    name = f"{info.get('org', '')} {info.get('isp', '')}".lower()
    for key, label in NEPAL_ISPS.items():
        if key in name:
            note = ""
            if domain not in ("?", "") and key not in domain:
                note = f"Hosted inside {label} - likely CDN cache node"
            return f"Local ISP ({label})", note
    for key, label in CDN_CLOUDS.items():
        if key in name:
            return label, ""
    if info.get("country") == "NP":
        return "Nepal network", ""
    return "Other", ""


# -------------------------------------------------------------------- output
COLS = ["domain", "ip", "asn", "org", "isp", "country", "type", "note"]


def print_markdown(rows):
    print("| # | " + " | ".join(c.upper() for c in COLS) + " |")
    print("|---|" + "---|" * len(COLS))
    for i, r in enumerate(rows, 1):
        print(f"| {i} | " + " | ".join(str(r.get(c, "")) for c in COLS) + " |")


def main():
    ap = argparse.ArgumentParser(description="Screenshot/text -> domain/IP -> ASN/ISP table")
    ap.add_argument("inputs", nargs="*", help="image files, .txt files, or - for stdin")
    ap.add_argument("--text", help="raw text instead of files")
    ap.add_argument("--csv", action="store_true", help="CSV output")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--no-lookup", action="store_true", help="only OCR + parse")
    args = ap.parse_args()

    chunks = []
    if args.text:
        chunks.append(args.text)
    for p in args.inputs:
        if p == "-":
            chunks.append(sys.stdin.read())
        elif Path(p).suffix.lower() in (".txt", ".csv", ".log"):
            chunks.append(Path(p).read_text(errors="ignore"))
        else:
            chunks.append(ocr_image(p))
    if not chunks:
        ap.error("give at least one image/text file or --text")

    pairs = []
    for c in chunks:
        pairs += extract_pairs(c)
    if not pairs:
        sys.exit("No domain/IP pairs found.")

    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
        except Exception:
            cache = {}

    rows = []
    for domain, ip in pairs:
        row = {"domain": domain, "ip": ip}
        if not args.no_lookup:
            if ip not in cache or "error" in cache[ip]:
                cache[ip] = lookup(ip)
                time.sleep(0.2)
            info = cache[ip]
            row.update({k: info.get(k, "") for k in ("asn", "org", "isp", "country")})
            if "error" in info:
                row["note"] = "lookup failed: " + info["error"]
            else:
                row["type"], row["note"] = classify(domain, info)
        rows.append(row)

    if not args.no_lookup:
        try:
            CACHE_FILE.write_text(json.dumps(cache))
        except Exception:
            pass

    if args.json:
        print(json.dumps(rows, indent=2))
    elif args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    else:
        print_markdown(rows)
        if not args.no_lookup:
            counts = {}
            for r in rows:
                counts[r.get("type", "?")] = counts.get(r.get("type", "?"), 0) + 1
            print("\nSummary: " + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
