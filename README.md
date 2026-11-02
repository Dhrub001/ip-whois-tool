# ip-whois-tool

Screenshot of a domain / IP list -> OCR -> ASN, ISP and owner table.
Useful for spotting which IPs are CDN (Akamai, Fastly, Google) and which are local ISP cache nodes (Ncell, WorldLink, Subisu...).

Two versions:

| File | What it is |
|------|------------|
| `ipwho.py` | Command line tool (Python + Tesseract) |
| `ip-lookup.html` | Single-page web tool, runs fully in the browser |

## CLI

```bash
# one-time setup
pip install -r requirements.txt
# also install the tesseract binary:
#   Ubuntu/Debian: sudo apt install tesseract-ocr
#   macOS:         brew install tesseract
#   Windows:       https://github.com/UB-Mannheim/tesseract/wiki

python ipwho.py shot1.png shot2.png          # markdown table
python ipwho.py shot1.png --csv > out.csv    # CSV
python ipwho.py list.txt --json              # JSON from a text file
python ipwho.py --text "www.tiktok.com 23.57.75.160"
python ipwho.py shot1.png --no-lookup        # OCR + parse only
```

Lookups use ipwho.is (fallback ipinfo.io) and are cached in `~/.ipwho_cache.json`.

## Put it on your website (dhrubrajgiri.com.np)

1. Upload `ip-lookup.html` to your host, for example `/tools/ip-lookup.html`.
2. Link to it from your menu, or embed it:
   ```html
   <iframe src="/tools/ip-lookup.html" style="width:100%;height:900px;border:0"></iframe>
   ```
3. It needs no backend. Tesseract.js loads from jsDelivr and lookups go straight from the visitor's browser to ipwho.is over HTTPS.

## Put it on GitHub

```bash
cd ip-whois-tool
git init
git add .
git commit -m "IP whois from screenshot tool"
git branch -M main
git remote add origin https://github.com/<your-username>/ip-whois-tool.git
git push -u origin main
```

To host the web version free on GitHub Pages: repo Settings -> Pages -> Deploy from branch `main` / root. Rename `ip-lookup.html` to `index.html` if you want it at the root URL.

## Notes

- The OCR reads the domain column first, then re-reads each row's IP column on its own, which is much more accurate for table screenshots. Domain names can still have small typos (for example `mcs-sg` read as `mes-sg`); the IPs are what get looked up.
- OCR can still misread a digit. Always check the detected text before trusting a result (the web version lets you edit it).
- A screenshot with a cut-off IPv6 address (like `2404:6800:4000:1017::cf`) will look up a different address than the full one.
- ipwho.is free tier has a monthly request limit; the CLI cache avoids repeat lookups.
- Owner names come from public databases. "Hosted inside Ncell" means the IP belongs to Ncell's network, which for TikTok/Facebook domains is usually a CDN cache node.
