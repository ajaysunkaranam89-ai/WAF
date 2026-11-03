"""Build BunkerWeb_Tutorial.pdf from BunkerWeb_Tutorial.md (python-markdown + headless Chrome)."""
import pathlib, subprocess, sys, markdown

here = pathlib.Path(__file__).resolve().parent
md = (here / "BunkerWeb_Tutorial.md").read_text(encoding="utf-8")
body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
css = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1d2733; }
h1 { font-size: 24pt; color: #fff; background: linear-gradient(90deg,#7f00ff,#ee0979,#ff6a00); padding: 14px 18px; border-radius: 10px; }
h2 { font-size: 16pt; color: #5b21b6; border-bottom: 3px solid #ee0979; padding-bottom: 3px; margin-top: 26px; page-break-after: avoid; }
h3 { font-size: 12.5pt; color: #0e7490; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
th { background: #5b21b6; color: #fff; text-align: left; padding: 6px 8px; }
td { border: 1px solid #d5d9e0; padding: 5px 8px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f3ff; }
pre { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 8px; font-size: 8.6pt; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
code { font-family: Consolas, 'Courier New', monospace; background: #eef2ff; padding: 1px 4px; border-radius: 4px; font-size: 9pt; }
pre code { background: none; padding: 0; color: inherit; }
blockquote { border-left: 5px solid #ff6a00; background: #fff7ed; margin: 12px 0; padding: 8px 14px; }
img { max-width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; margin: 8px 0; box-shadow: 0 2px 8px #0003; page-break-inside: avoid; }
hr { border: 0; border-top: 1px dashed #94a3b8; margin: 22px 0; }
"""
html = f"<!doctype html><html><head><meta charset='utf-8'><title>BunkerWeb tutorial</title><style>{css}</style></head><body>{body}</body></html>"
(here / "BunkerWeb_Tutorial.html").write_text(html, encoding="utf-8")

chrome = next(p for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"] if pathlib.Path(p).exists())
pdf = here / "BunkerWeb_Tutorial.pdf"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", (here / "BunkerWeb_Tutorial.html").as_uri()], check=True, timeout=120)
print("wrote", pdf, pdf.stat().st_size, "bytes")
