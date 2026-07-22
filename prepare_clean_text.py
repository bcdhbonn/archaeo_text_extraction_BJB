import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from Extraction_pipline_BJB import clean_text

txt_files = ["LVR_1973_raw_text.txt", "LVR_1970_raw_text.txt"]

for fname in txt_files:
    fpath = os.path.join(root_dir, fname)
    if os.path.exists(fpath):
        out_name = fname.replace("_raw_text.txt", "_cleaned.txt")
        out_path = os.path.join(root_dir, out_name)
        print(f"📄 Cleaning text file: {fname} -> {out_name}...")
        with open(fpath, "r", encoding="utf-8") as f:
            raw = f.read()
        
        cleaned = clean_text(raw)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        
        print(f"✅ Saved cleaned text to: {out_path}")
