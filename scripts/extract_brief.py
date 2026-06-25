"""Extract the FYP module handbook so we can re-check requirements."""
from pypdf import PdfReader
from pathlib import Path

pdf = Path(r"D:\assignments\fyp\1-L6_Computing_Module_Handbook (SCC).pdf")
out = Path(r"D:\assignments\Computing project fyp\docs\handbook.txt")
reader = PdfReader(str(pdf))
print(f"Pages: {len(reader.pages)}")
text_parts = []
for i, page in enumerate(reader.pages):
    t = page.extract_text() or ""
    text_parts.append(f"\n=== PAGE {i+1} ===\n{t}")
out.write_text("\n".join(text_parts), encoding="utf-8")
print(f"Wrote {out.stat().st_size:,} bytes to {out}")
