# IP Whois from Screenshot

Drop in a screenshot of a domain and IP list. The tool reads it and shows the **ASN, ISP and owner** of every address, and flags which ones sit inside a local ISP (for example Ncell, WorldLink or Subisu in Nepal) instead of a CDN such as Akamai, Fastly or Google.

**Use it online:** https://dhrub001.github.io/ip-whois-tool/ip-lookup.html

## How to use the web page

1. **Add a screenshot.** Drag it onto the box, press `Ctrl+V` to paste it, or click the box to browse. No screenshot handy? Press **Try an example**.
2. **Check the text.** The page reads your image and fills the text box. If a digit looks wrong, fix it and press **Look up owners**.
3. **Read the results.** Every IP gets an owner, an ISP and a color tag. Filter by type, search, then **Download CSV** or **Copy as Markdown**.

You can also skip the image and type or paste lines like `www.tiktok.com 23.57.75.160`. IPv4 and IPv6 both work.

### What the colors mean

| Tag | Meaning |
|-----|---------|
| CDN or cloud | The IP belongs to a CDN, a cloud company or the service itself (Akamai, Fastly, Google, ByteDance...). |
| Local ISP | The IP belongs to a Nepali internet provider. For a big site like TikTok this usually means a cache server inside that ISP. |
| Other | Any other network. |
| Lookup failed | The owner could not be found. Check the IP and press **Look up owners** again. |

### Tips for a clean read

- Crop to the table: only the domain and IP columns.
- Capture at 100% zoom or larger. Small, blurry text is the usual cause of a misread digit.
- Keep each IP whole. If the screenshot edge cuts an address off, a different address gets looked up.
- Always check the text box before trusting a result.

### Privacy

The image is read inside your browser and never uploaded. Only the IP addresses are sent to the free [ipwho.is](https://ipwho.is) service to find their owners.

## Command-line version

`ipwho.py` does the same job in a terminal.

```bash
# one-time setup
pip install -r requirements.txt
# also install the tesseract program:
#   Ubuntu/Debian: sudo apt install tesseract-ocr
#   macOS:         brew install tesseract
#   Windows:       https://github.com/UB-Mannheim/tesseract/wiki

python ipwho.py shot1.png shot2.png          # Markdown table
python ipwho.py shot1.png --csv > out.csv    # CSV
python ipwho.py list.txt --json              # JSON, from a text file
python ipwho.py --text "www.tiktok.com 23.57.75.160"
python ipwho.py shot1.png --no-lookup        # read the image only
```

Lookups use ipwho.is, with ipinfo.io as a backup, and are cached in `~/.ipwho_cache.json`.

## Host it yourself

The web page is one file with no backend.

- **GitHub Pages:** in your fork, open Settings, then Pages, choose **Deploy from a branch**, **main** and **/ (root)**, and save.
- **Your own website:** upload `ip-lookup.html` (for example to `/tools/ip-lookup.html`) and link to it, or embed it:
  ```html
  <iframe src="/tools/ip-lookup.html" style="width:100%;height:900px;border:0"></iframe>
  ```

## Notes

- The page reads the domain column first, then re-reads each row's IP column on its own, which is much more accurate for table screenshots. Domain names can still have small typos (for example `mcs-sg` read as `mes-sg`). The lookup uses the IP, so the owner is still correct.
- Owner names come from public registry data. It is good for who runs a network but can lag behind recent changes, so confirm with `whois` if it matters.
- ipwho.is has a monthly limit on its free tier. The command-line version caches results to avoid repeat lookups.
