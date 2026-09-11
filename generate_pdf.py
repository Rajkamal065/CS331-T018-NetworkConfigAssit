import os
import markdown
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(ROOT, "CS331_T018_Project_Report.md")
PDF_PATH = os.path.join(ROOT, "report.pdf")
HTML_TEMP = os.path.join(ROOT, "report_temp.html")

with open(MD_PATH, "r", encoding="utf-8") as f:
    md_content = f.read()

# Convert markdown to html with table extension
html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code"])

# Ensure image paths resolve correctly
img1_path = os.path.abspath(os.path.join(ROOT, "results_figures", "gaming_benchmark.png")).replace("\\", "/")
img2_path = os.path.abspath(os.path.join(ROOT, "results_figures", "throughput_benchmarks.png")).replace("\\", "/")

# Add styled HTML with print styles
full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CS331 - NetOps MCP Assistant Report</title>
<style>
  @page {{
    size: A4;
    margin: 20mm 20mm 25mm 20mm;
    @bottom-right {{
      content: counter(page);
    }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
    line-height: 1.6;
    font-size: 11pt;
  }}
  h1 {{
    color: #0f172a;
    font-size: 20pt;
    margin-bottom: 4px;
    border-bottom: 2px solid #2563eb;
    padding-bottom: 6px;
  }}
  h2 {{
    color: #1e3a8a;
    font-size: 15pt;
    margin-top: 24px;
    margin-bottom: 8px;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    page-break-after: avoid;
  }}
  h3 {{
    color: #1e293b;
    font-size: 12pt;
    margin-top: 18px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }}
  h4 {{
    color: #334155;
    font-size: 11pt;
    margin-top: 12px;
    margin-bottom: 4px;
    page-break-after: avoid;
  }}
  p, li {{
    text-align: justify;
  }}
  blockquote {{
    background: #f8fafc;
    border-left: 4px solid #3b82f6;
    margin: 12px 0;
    padding: 8px 16px;
    font-style: italic;
    color: #334155;
  }}
  pre, code {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: 9.5pt;
  }}
  pre {{
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 12px;
    overflow-x: auto;
    page-break-inside: avoid;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
  }}
  th, td {{
    border: 1px solid #cbd5e1;
    padding: 8px 10px;
    text-align: left;
  }}
  th {{
    background: #f8fafc;
    color: #0f172a;
    font-weight: 600;
  }}
  tr:nth-child(even) {{
    background: #f8fafc;
  }}
  img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 16px auto;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
  }}
  .figure-caption {{
    text-align: center;
    font-size: 9.5pt;
    color: #64748b;
    margin-top: -8px;
    margin-bottom: 16px;
  }}
  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 20px 0;
  }}
</style>
</head>
<body>
{html_body}

<div style="margin-top: 24px; page-break-inside: avoid;">
  <h3>Empirical Benchmark Visualizations</h3>
  <img src="file:///{img1_path}" alt="Gaming Benchmark">
  <div class="figure-caption">Figure 1: Gaming Profile Benchmark (Ping Latency, Handshake, and Jitter Reduction)</div>
  <img src="file:///{img2_path}" alt="Throughput Benchmark">
  <div class="figure-caption">Figure 2: Streaming (+46.6%) and Broadcasting (+17.5%) Throughput Improvements</div>
</div>

</body>
</html>
"""

with open(HTML_TEMP, "w", encoding="utf-8") as f:
    f.write(full_html)

print("HTML generated, compiling to PDF with Playwright...")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(f"file:///{HTML_TEMP.replace('\\', '/')}")
    page.wait_for_load_state("networkidle")
    page.pdf(
        path=PDF_PATH,
        format="A4",
        print_background=True,
        margin={"top": "20mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
        display_header_footer=True,
        header_template='<div style="font-size:8pt; color:#64748b; width:100%; text-align:right; padding-right:20mm;">CS331: Computer Networks — Team T018</div>',
        footer_template='<div style="font-size:8pt; color:#64748b; width:100%; text-align:center;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>'
    )
    browser.close()

if os.path.exists(HTML_TEMP):
    os.remove(HTML_TEMP)

print(f"PDF successfully generated at: {PDF_PATH}")
