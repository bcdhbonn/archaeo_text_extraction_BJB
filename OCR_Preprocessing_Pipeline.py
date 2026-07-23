import os
import re
import unicodedata
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import pdfplumber
except ImportError:
    print("⚠️ pdfplumber ist nicht installiert. Bitte: pip install pdfplumber")

# ==========================================
# 1. OCR ERROR CORRECTION ENGINE
# ==========================================

def clean_ocr_text(text):
    if not text:
        return ""

    # 1. Unicode Normalization (NFC)
    text = unicodedata.normalize('NFC', text)

    # 2. Ligature and Typo Swaps
    char_map = {
        '': '1', '': '2', '': '3', '': '4', '': '5', '': '6', '': '7', '': '8', '': '9', '': '0',
        'rbmisch': 'römisch', 'rbmische': 'römische', 'rbmischer': 'römischer', 'rbmisches': 'römisches',
        'Lbbabdeckung': 'Lehmabdeckung', 'gebffnet': 'geöffnet', 'liefi': 'ließ', 'Halfte': 'Hälfte',
        'grbBeren': 'größeren', 'grbBere': 'größere', 'grbBerer': 'größerer', 'Jiilich': 'Jülich',
        'Briihl': 'Brühl', 'AnschluB': 'Anschluss'
    }
    for bad, good in char_map.items():
        text = text.replace(bad, good)

    # 3. Abbreviation Expansion
    abbrev_map = [
        (r'\bBodenbrst\.\b', 'Bodenbruchstück'),
        (r'\bbrst\.\b', 'bruchstück'),
        (r'\bBruchst\.\b', 'Bruchstück'),
        (r'\bBrst\.\b', 'Bruchstück'),
        (r'\bWandbrst\.\b', 'Wandbruchstück'),
        (r'\bRandbrst\.\b', 'Randbruchstück'),
    ]
    for pat, repl in abbrev_map:
        text = re.sub(pat, repl, text)

    # 4. Line-Break De-Hyphenation (Rejoin split words across linebreaks)
    text = re.sub(r'([a-zäöüß])-\s*\n\s*([a-zäöüß])', r'\1\2', text, flags=re.IGNORECASE)

    # 5. Glued Preposition & Word Splitting
    glued_fixes = [
        # Explicit glued OCR phrases & Archaeological expansions
        (r'Siedlungbei', r'Siedlung bei'),
        (r'Siersdorf,im', r'Siersdorf, im'),
        (r'Arealeiner', r'Areal einer'),
        (r'\bneolith\.u\.', r'neolithisch u.'),
        (r'\bneolith\.', r'neolithisch'),
        (r'\bspätbronze-', r'spätbronzezeitlich'),
        (r'\bfrüheisenzeitl\.', r'früheisenzeitlich'),
        (r'\beisenzeitl\.', r'eisenzeitlich'),
        (r'\bfrühröm\.', r'frührömisch'),
        (r'\bspätröm\.', r'spätrömisch'),
        (r'\bmittelalterl\.', r'mittelalterlich'),
        (r'\bfrüheneuzeitl\.', r'früheneuzeitlich'),
        (r'\bjüngereisenzeitl\.', r'jüngereisenzeitlich'),
        (r'\bbandkeram\.', r'bandkeramisch'),
        (r'Teildes', r'Teil des'),
        (r'Grabungsarealseine', r'Grabungsareals eine '),
        (r'Trassederröm\.', r'Trasse der röm.'),
        (r'Speicheroder', r'Speicher oder'),
        (r'Materialentnahmebereichenachgewiesen', r'Materialentnahmebereiche nachgewiesen'),
        (r'Ausder', r'Aus der'),
        (r'Neuzeitstammtein', r'Neuzeit stammt ein'),
        (r'Schützengrabenmiteinzelnen', r'Schützengraben mit einzelnen'),
        (r'8mauseinanderliegenden', r'8 m auseinander liegenden'),

        # Pattern-based safe fixes
        (r'([a-zäöüß]+)\.oder([a-zäöüß]+)', r'\1. oder \2'),
        (r'\b([A-Za-zäöüÄÖÜß]{3,})u\.\s+([A-ZÄÖÜa-zäöüß])', r'\1 u. \2'),
        (r'([A-Z][a-zäöüß]+)f\.\s*([A-Z][a-zäöüß]+)', r'\1 f. \2'),
        (r'([IVXLCDM]+)\.f\.\s*([A-Z][a-zäöüß]+)', r'\1. f. \2'),
        (r'(\d+)\./(\d+)\.\s*Jh', r'\1. / \2. Jh'),
        (r'Jh\.n\.\s*Chr', r'Jh. n. Chr'),
        (r'(\b[A-Za-zäöüÄÖÜß]+),dervorallemaus\b', r'\1, der vor allem aus'),
        (r'(\b[A-Za-zäöüÄÖÜß]+)dervorallemaus\b', r'\1 der vor allem aus'),
        (r'(\b[A-Za-zäöüÄÖÜß]+)dermittleren\b', r'\1 der mittleren'),
        (r'(\b[A-Za-zäöüÄÖÜß]+)au\.([A-ZÄÖÜa-zäöüß])', r'\1 a u. \2'),
        (r'([a-zäöüß]+)u\.([A-ZÄÖÜa-zäöüß])', r'\1 u. \2'),
        (r'(\b[A-Za-zäöüÄÖÜß]+)segmentatau\b', r'\1segmentata u.'),
        (r'\b(RS|BS|WS|St|Nr)\.?([A-ZÄÖÜ][a-zäöüß]+)', r'\1 \2'),
        (r'([a-zäöüß\.\)])([A-ZÄÖÜ])', r'\1 \2'),
        (r'(\))([A-ZÄÖÜa-zäöüß])', r'\1 \2'),
        (r'([a-zäöüß])(Abb\.|Bild)', r'\1 \2'),
    ]
    for pat, repl in glued_fixes:
        text = re.sub(pat, repl, text)

    # 6. Remove OCR Noise Running Headers/Footers
    text = re.sub(r'(Römische\s+Zeit\s+\d+)|(\d+\s+Römische\s+Zeit)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Abb\.\s*\d+[^\n]*?(?:\n[^\n]*?){0,2}?Ma[ßfhmalit-]{1,5}\s*stab\s*\d+\s*:\s*\d+\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Abb\.\s*\d+\s+[A-ZÄÖÜ][^\n]+', '', text)

    return text

# ==========================================
# 2. PDF & TEXT EXTRACTION PIPELINE
# ==========================================

def extract_and_preprocess_pdf(pdf_path, max_pages=7):
    print(f"📖 Extrahiere und bereinige PDF Text aus: {os.path.basename(pdf_path)}...")
    if not os.path.exists(pdf_path):
        print(f"⚠️ PDF Datei nicht gefunden: {pdf_path}")
        return ""

    raw_pages = []
    cleaned_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = min(len(pdf.pages), max_pages)
        for page_idx in range(num_pages):
            page = pdf.pages[page_idx]
            width, height = page.width, page.height
            
            # Crop top 3% and bottom 3%
            top_y = height * 0.03
            bottom_y = height * 0.97
            mid_x = width / 2

            left_crop = page.crop((0, top_y, mid_x, bottom_y))
            right_crop = page.crop((mid_x, top_y, width, bottom_y))

            left_text = left_crop.extract_text() or ""
            right_text = right_crop.extract_text() or ""

            if len(left_text.strip()) > 50 and len(right_text.strip()) > 50:
                raw_page_text = f"--- SEITE {page_idx+1} ---\n--- LEFT COLUMN ---\n{left_text.strip()}\n\n--- RIGHT COLUMN ---\n{right_text.strip()}"
            else:
                full_crop = page.crop((0, top_y, width, bottom_y))
                raw_page_text = f"--- SEITE {page_idx+1} ---\n{full_crop.extract_text() or ''}"

            cleaned_page_text = clean_ocr_text(raw_page_text)
            
            raw_pages.append(raw_page_text)
            cleaned_pages.append(cleaned_page_text)

    full_raw = "\n\n".join(raw_pages)
    full_cleaned = "\n\n".join(cleaned_pages)
    return full_raw, full_cleaned

# ==========================================
# 3. HTML REVIEW GENERATOR (SIDE-BY-SIDE DIFF)
# ==========================================

def create_ocr_review_html(raw_text, cleaned_text, output_html_path):
    print(f"🖥️ Generiere OCR-Prüfbericht unter: {output_html_path}...")
    import html

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>OCR-Bereinigung: Vorschau & Review</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 0; background: #0f172a; color: #f8fafc;
        }}
        header {{
            background: #1e293b; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155;
        }}
        h1 {{ margin: 0; font-size: 1.2rem; color: #38bdf8; }}
        .badge {{ background: #0284c7; color: white; padding: 4px 10px; borderRadius: 4px; font-size: 0.85rem; font-weight: 600; }}
        .container {{ display: flex; height: calc(100vh - 65px); }}
        .pane {{ flex: 1; padding: 20px; overflow-y: auto; border-right: 1px solid #334155; }}
        .pane:last-child {{ border-right: none; }}
        h2 {{ font-size: 1rem; color: #94a3b8; margin-top: 0; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
        pre {{ white-space: pre-wrap; word-break: break-word; font-family: "Cascadia Code", "Fira Code", Consolas, monospace; font-size: 0.9rem; line-height: 1.6; color: #cbd5e1; }}
        .cleaned pre {{ color: #4ade80; }}
    </style>
</head>
<body>
    <header>
        <h1>🔍 OCR-Bereinigungs-Pipeline (Review vor Extraktion)</h1>
        <span class="badge">Bereit zur Überprüfung</span>
    </header>
    <div class="container">
        <div class="pane">
            <h2>📄 Original OCR (Rohtext aus PDF)</h2>
            <pre>{html.escape(raw_text)}</pre>
        </div>
        <div class="pane cleaned">
            <h2>✨ Bereinigter Text (Gefixte Wörter & Zeilenumbrüche)</h2>
            <pre>{html.escape(cleaned_text)}</pre>
        </div>
    </div>
</body>
</html>
"""

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ OCR Review HTML erfolgreich erstellt: {output_html_path}")

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    
    pdf_paths = [
        os.path.join(workspace_dir, "2014_10_16.pdf"),
        r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\PDFs_Test\2014_10_16.pdf"
    ]
    pdf_path = next((p for p in pdf_paths if os.path.exists(p)), None)

    output_raw_path = os.path.join(workspace_dir, "LVR_2014_10_16_raw_text.txt")
    output_cleaned_path = os.path.join(workspace_dir, "LVR_2014_10_16_cleaned_text.txt")
    output_html_path = os.path.join(workspace_dir, "OCR_Review_Preview.html")

    if pdf_path and os.path.exists(pdf_path):
        raw_text, cleaned_text = extract_and_preprocess_pdf(pdf_path, max_pages=7)
    elif os.path.exists(output_raw_path):
        print(f"📖 Lese bestehenden Rohtext aus: {os.path.basename(output_raw_path)}...")
        with open(output_raw_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        cleaned_text = clean_ocr_text(raw_text)
    else:
        print("⚠️ Weder PDF noch 'LVR_2014_10_16_raw_text.txt' gefunden.")
        sys.exit(1)

    with open(output_raw_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    with open(output_cleaned_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    create_ocr_review_html(raw_text, cleaned_text, output_html_path)

    print("\n🎉 OCR-Vorverarbeitung abgeschlossen!")
    print(f"1. Rohtext:            {output_raw_path}")
    print(f"2. Bereinigter Text:   {output_cleaned_path}")
    print(f"3. Visuelle Vorschau:  {output_html_path}")
    print("\nSie können den bereinigten Text in 'OCR_Review_Preview.html' im Browser überprüfen, bevor Sie die KI-Extraktion starten!")
