import pdfplumber
import pandas as pd
from google import genai
import sys

# Ensure standard output uses UTF-8 to prevent encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import os
import time
import re
from tqdm import tqdm
from rdflib import Graph, Namespace, RDF, SKOS

# ==========================================
# 1. KONFIGURATION
# ==========================================

# Lokale Pfade auf Ihrem Windows-System
pdf_base_dir = r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\BJB_PDF_1970_2014"
filename = "1973.pdf"

# Vokabular liegt im Workspace-Ordner (e:\AIBJB)
vocab_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archaevocabNLDE.ttl")

# Automatische Suche im PDF-Verzeichnis (auch in Dekaden-Unterordnern)
pdf_path = None
for root, dirs, files in os.walk(pdf_base_dir):
    if filename in files:
        pdf_path = os.path.join(root, filename)
        break
if not pdf_path:
    pdf_path = os.path.join(pdf_base_dir, filename) # Fallback

# API Key & Client Initialisierung
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    print("❌ Bitte setzen Sie Ihren Google API Key als Umgebungsvariable 'GOOGLE_API_KEY'!")
    print("Beispiel (PowerShell): $env:GOOGLE_API_KEY='IHR_KEY'")

try:
    client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
except Exception as e:
    print(f"❌ Fehler bei der Initialisierung des GenAI Clients: {e}")
    client = None

MODEL_NAME = "gemini-2.5-flash-lite" # Standardisiert auf das aktuelle stabile Modell

# Seitenbereich
START_PAGE = 26
END_PAGE = 137

# Bestimme das Publikationsjahr aus dem PDF-Namen für die Layout-Auswahl
try:
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
    PUBLICATION_YEAR = int(year_match.group(1)) if year_match else 2006
except Exception:
    PUBLICATION_YEAR = 2006

# ==========================================
# 2. SKOS PARSER
# ==========================================

SKOS_LOOKUP = {}

def parse_skos_vocabulary(path):
    global SKOS_LOOKUP
    if not os.path.exists(path): return ""
    print(f"📚 Lade Vokabular...")
    g = Graph()
    try:
        g.parse(path, format="turtle")
    except Exception as e:
        print(f"⚠️ Fehler beim Parsen des SKOS-Vokabulars: {e}")
        return ""

    prompt_lines = []
    for concept in g.subjects(RDF.type, SKOS.Concept):
        pref_labels = []
        for label in g.objects(concept, SKOS.prefLabel):
            if label.language in ['de', 'nl']:
                term = str(label)
                pref_labels.append(term)
                SKOS_LOOKUP[term.lower()] = term

        if pref_labels:
            main_term = pref_labels[0]
            alt_labels = []
            for alt in g.objects(concept, SKOS.altLabel):
                if alt.language in ['de', 'nl']:
                    SKOS_LOOKUP[str(alt).lower()] = main_term
                    alt_labels.append(str(alt))

            entry = f"- {main_term}"
            if alt_labels: entry += f" (Syn: {', '.join(alt_labels[:2])})"
            prompt_lines.append(entry)

    vocab_text = "NUTZE DIESE BEGRIFFE ZUR NORMALISIERUNG:\n" + "\n".join(sorted(prompt_lines)[:400])
    return vocab_text

vocab_instruction = parse_skos_vocabulary(vocab_path)

# ==========================================
# 3. VALIDIERUNG
# ==========================================

def validate_and_mark(text_value):
    if not text_value or not isinstance(text_value, str): return "-"
    if text_value == "-": return "-"
    items = [x.strip() for x in text_value.split(',')]
    final_items = []
    for item in items:
        clean = item.lower()
        if clean in SKOS_LOOKUP:
            std = SKOS_LOOKUP[clean]
            final_items.append(f"{std} (SKOS)")
        else:
            found = False
            for key in SKOS_LOOKUP:
                if key in clean and len(key) > 4:
                    std = SKOS_LOOKUP[key]
                    final_items.append(f"{std} (SKOS)")
                    found = True
                    break
            if not found: final_items.append(item)
    return ", ".join(final_items)

# ==========================================
# 4. PDF TEXT BEREINIGUNG
# ==========================================

def clean_text(text):
    if not text: return ""
    replacements = {'':'1', '':'2', '':'3', '':'4', '':'5', '':'6', '':'7', '':'8', '':'9', '':'0'}
    for old, new in replacements.items(): text = text.replace(old, new)
    header_pattern = r'(Römische\s+Zeit\s+\d+)|(\d+\s+Römische\s+Zeit)'
    text = re.sub(header_pattern, '', text, flags=re.IGNORECASE)
    # Entferne Abbildungsunterschriften (z.B. "12 Haldern. Bronzezeitliches Gefafi. - Mahstab 1 : 2.")
    caption_pattern = r'(?:^|\n)(?!\d+\s+Jahresbericht)\d{1,3}\s+[A-ZÄÖÜ][^\n]*?(?:\n[^\n]*?){0,3}?Ma[ßfhmalit-]{1,5}\s*stab\s*\d+\s*:\s*\d+\.?'
    text = re.sub(caption_pattern, '', text, flags=re.IGNORECASE)
    return text

def extract_page_text_lazy(pdf_path, page_idx):
    """Öffnet das PDF einzeln für eine Seite, extrahiert den Text und schließt es wieder.
       Das verhindert Speicherlecks bei extrem großen PDF-Dateien (>150MB)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if 0 <= page_idx < len(pdf.pages):
                return clean_text(pdf.pages[page_idx].extract_text())
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen der Seite {page_idx+1}: {e}")
    return None

# ==========================================
# 5. KI EXTRAKTION (MIGRATION AUF GOOGLE-GENAI)
# ==========================================

def get_system_prompt(year, vocab_instruction):
    if year < 1990:
        # Prompt optimiert für das 1970er/1980er Layout (inline Ortsnamen, r/h Gauß-Krüger Koordinaten)
        return f"""
Du bist ein hochspezialisierter Experte für die archäologische Datenerfassung der "Bonner Jahrbücher". Deine Aufgabe ist die präzise Extraktion von Fundstellen und den darunter erfolgten Maßnahmen in ein strukturiertes JSON-Format.

{vocab_instruction}

### KERN-AUFGABEN
1. Zerlege den Text in einzelne Fundstellen/Maßnahmen.
2. Identifiziere den Ort und Kreis.
   WICHTIG: Ort und Kreis stehen in älteren Bänden meist am Anfang eines neuen Absatzes (z. B. "Neersen, Kr. Kempen-Krefeld (TK 4704 Viersen: r 3374, h 7956)." -> Ort: Neersen, Kreis: Kempen-Krefeld).
   Der Ort gilt für alle folgenden Nummern (1., 2. usw.) unter diesem Absatz, bis ein neuer Ort im Text erscheint.
3. Identifiziere die Maßnahmen. 
   Diese sind in älteren Bänden oft NICHT durchnummeriert (d. h. es gibt keine Nummern wie 1., 2. usw., da pro Ort oft nur ein Bericht vorliegt).
   Falls Koordinaten vorhanden sind (z. B. "(TK 4704 Viersen: r 3374, h 7956)"), verwende diese als `massnahme_id` (z. B. "(r 3374, h 7956)").
   Falls durchnummeriert, verwende die Nummer (z. B. "1. (r 18341, h 38336)").
   Falls weder eine Nummerierung noch Koordinaten vorhanden sind, setze `massnahme_id` auf "None". 
   WICHTIG: Verwende niemals beschreibende Fließtexte oder Einleitungssätze als `massnahme_id`!
   WICHTIG: Abbildungen und Bildunterschriften (z.B. beginnend mit "Bild ..." oder "Abb. ..." oder einer einfachen Nummer) dürfen nicht als eigene Maßnahme oder als `massnahme_id` klassifiziert werden. Diese dienen lediglich als Objektreferenzen von Funden/Befunden innerhalb der übergeordneten Fundstelle.

### REGELN FÜR SEITENÜBERGÄNGE & DUPLIKATE (STRENGSTENS EINHALTEN)
- Der Text enthält Marker wie "--- SEITENWECHSEL ---".
- Wenn eine `massnahme_id` bereits vor dem Seitenwechsel begonnen hat und danach fortgesetzt wird:
  - Erstelle **KEINEN** neuen Eintrag.
  - Fasse alle Informationen (auch den Text der Folgeseite) in **EINEM** JSON-Objekt zusammen.
  - Ergänze Felder wie 'funde_roh' oder 'befunde_roh' um die neuen Details der Folgeseite.
- Jede eindeutige Nummer (z.B. 1., 2., 3.) innerhalb eines Ortes entspricht einer Maßnahme und soll zu einem Array zusammengefasst werden.

### EXTRAKTIONS-GUIDE
- **massnahme_id**: Die Nummer und/oder Koordinaten (z. B. "1. (r 18341, h 38336)" oder "(r 3374, h 7956)"). Falls beides fehlt, verwende "None". Keine Fließtexte oder Bild-/Abbildungsnummern (wie "(Bild 22,5)")!
- **_roh Felder**: Kopiere den Text wortwörtlich aus dem PDF. Nicht zusammenfassen. Behalte eventuelle Objektreferenzen wie "(Bild 22,5)" im Originaltext bei.
- **_norm Felder**: Nutze ausschließlich Begriffe aus dem bereitgestellten Vokabular zur Normalisierung.
- **autor**: Der Name am Ende eines Abschnitts oder am Ende der Fundstelle (oft in Klammern am Ende des Textblocks, z. B. "(H. Waffenschmidt)").

### AUSGABE-FORMAT (NUR REINES JSON)
{{
  "eintraege": [
    {{
      "Seitenzahl": "531",
      "bundesland": "NRW",
      "ort": "Niedermerz",
      "kreis": "Jülich",
      "massnahme_id": "1. (r 18341, h 38336)",
      "datierung_roh": "Originaltext zur Zeitstellung (z. B. römisch)",
      "datierung_norm": "Normalisierter Begriff",
      "befunde_roh": "Originaltext zu Befunden (z. B. ovaler Ring aus rötlich verziegeltem Lehm, römischer Ofen)",
      "befunde_norm": "Normalisierte Begriffe",
      "funde_roh": "Originaltext zu Funden (z. B. Ziegelbruchstücke, verziegelte Lehmbröckchen)",
      "funde_norm": "Normalisierte Begriffe",
      "autor": "Name des Berichterstatters"
    }}
  ]
}}
"""
    else:
        # Prompt optimiert für das 1990er/2000er Layout (originaler Prompt)
        return f"""
Du bist ein hochspezialisierter Experte für die archäologische Datenerfassung der "Bonner Jahrbücher". Deine Aufgabe ist die präzise Extraktion von Fundstellen und den darunter erfolgten Maßnahmen in ein strukturiertes JSON-Format.

{vocab_instruction}

### KERN-AUFGABEN
1. Zerlege den Text in einzelne Fundstellen/Maßnahmen.
2. Identifiziere den Ort und Kreis aus den (meist fettgedruckten) Überschriften.
   WICHTIG: Ein Ort gilt für alle folgenden Nummern, bis ein neuer Ort im Text erscheint.
   MASSNAHMEN: sind immer in mehreren Klammern, meist mit einer anführenden Nummer (1.,2.) formatiert.
   Beispiele wären: (z.B. 1218/056 - (1168/014) (HA125) - (1114/017) (HA 132) - (1057/019, 027 und 1006/031; 1057/028) - (1005/036) (WW96/158) - (1214/027) (HA96/226) - (0902/018) (NW96/0125 und 0126))
   Auf einigen Seiten existieren Abbildungen mit einer Nummerierung. Diese dürfen nicht als Maßnahme klassifiziert werden.
   (Beispiel: 24 Niederzier-Elsdorf. Villa rustica und Glashütte Fiambach 132: Spätrömisches Gräberfeld und östlicher Umfassungsgraben. Unterschiedliche Plana. Brandgräber gerastert. - Maßstab 1:400.)
   Hinter den Nummern kommt keine Maßnahme in Klammern, darum sollten sie ignoriert werden

### REGELN FÜR SEITENÜBERGÄNGE & DUPLIKATE (STRENGSTENS EINHALTEN)
- Der Text enthält Marker wie "--- SEITENWECHSEL ---".
- Wenn eine `massnahme_id` bereits vor dem Seitenwechsel begonnen hat und danach fortgesetzt wird:
  - Erstelle **KEINEN** neuen Eintrag.
  - Fasse alle Informationen (auch den Text der Folgeseite) in **EINEM** JSON-Objekt zusammen.
  - Ergänze Felder wie 'funde_roh' oder 'befunde_roh' um die neuen Details der Folgeseite.
- Jede eindeutige Nummer (z.B. 1., 2., 3.) innerhalb eines Ortes entspricht einer Maßnahme und soll zu einem Array zusammengefasst werden

### EXTRAKTIONS-GUIDE
- **massnahme_id**: Die Nummer im Format "1. (1234/567)".
- **_roh Felder**: Kopiere den Text wortwörtlich aus dem PDF. Nicht zusammenfassen.
- **_norm Felder**: Nutze ausschließlich Begriffe aus dem bereitgestellten Vokabular zur Normalisierung.
- **autor**: Der Name am Ende eines Abschnitts (oft abgekürzt, z.B. "M. Gechter").

## Seitenzahlen sind folgendermaßen formtiert 404 Ausgrabungen, Funde und Befunde 1996 auf den geraden Seiten und Römische Zeit 405 auf den ungeraden Seiten
### AUSGABE-FORMAT (NUR REINES JSON)
{{
  "eintraege": [
    {{
      "Seitenzahl": "404",
      "bundesland": "NRW",
      "ort": "Exakter Ortsname",
      "kreis": "Zugehöriger Kreis",
      "massnahme_id": "Nummer inkl. Klammerzusatz",
      "datierung_roh": "Originaltext zur Zeitstellung",
      "datierung_norm": "Normalisierter Begriff",
      "befunde_roh": "Originaltext zu Befunden (Mauern, Gruben etc.)",
      "befunde_norm": "Normalisierte Begriffe",
      "funde_roh": "Originaltext zu Funden (Keramik, Münzen etc.)",
      "funde_norm": "Normalisierte Begriffe",
      "autor": "Name des Berichterstatters"
    }}
  ]
}}
"""

def extract_data_with_gemini(text_chunk, system_prompt):
    for i in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"Analysiere exakt diesen Text:\n{text_chunk}",
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) or "quota" in str(e).lower():
                time.sleep(5)
                continue
            print(f"Fehler bei Extraktion: {e}")
            return {"eintraege": []}
    return {"eintraege": []}

# ==========================================
# 6. WORKFLOW
# ==========================================

text_pages = []

# Bestimme Dateinamen für Rohdaten und Pfad zum Rohtext
pdf_name_clean = os.path.splitext(os.path.basename(pdf_path))[0] if pdf_path else "1970"
txt_filename = f"LVR_{pdf_name_clean}_raw_text.txt"
txt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), txt_filename)

if pdf_path and os.path.exists(pdf_path):
    print(f"📖 Lese PDF (S. {START_PAGE}-{END_PAGE})...")
    
    # Ermittle die Gesamtseitenzahl
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as e:
        print(f"❌ Fehler beim Öffnen der PDF-Datei: {e}")
        total_pages = 0

    real_end = min(END_PAGE, total_pages)
    for i in tqdm(range(START_PAGE - 1, real_end), desc="Einlesen"):
        pt = extract_page_text_lazy(pdf_path, i)
        if pt: text_pages.append(pt)

    if text_pages:
        try:
            with open(txt_file, "w", encoding="utf-8") as f:
                for idx, page_text in enumerate(text_pages):
                    f.write(f"--- SEITE {START_PAGE + idx} ---\n")
                    f.write(page_text)
                    f.write("\n\n")
            print(f"📄 Rohtext gespeichert unter: {txt_file}")
        except Exception as e:
            print(f"⚠️ Fehler beim Speichern des Rohtextes: {e}")
elif os.path.exists(txt_file):
    print(f"📖 PDF nicht gefunden, aber Rohtext-Datei {txt_file} existiert. Lade Seiten aus dem Rohtext...")
    try:
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Splitte an den Seitenmarkern
        pages_raw = re.split(r'--- SEITE \d+ ---\n', content)
        # Das erste Element ist vor dem ersten Split leer
        for p in pages_raw[1:]:
            pt = clean_text(p.strip())
            if pt: text_pages.append(pt)
        print(f"✅ {len(text_pages)} Seiten erfolgreich aus Rohtext geladen.")
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Rohtext-Datei: {e}")
else:
    print("❌ Weder PDF noch Rohtext-Datei gefunden.")
    
def write_live_progress(current_idx, total_pages, last_ort=""):
    pct = (current_idx + 1) / total_pages * 100
    progress_html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.html")
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="3">
    <title>Extraktions-Fortschritt ({pct:.1f}%)</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
        .card {{ background: #1e293b; padding: 35px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 480px; text-align: center; border: 1px solid #334155; }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 22px; margin-bottom: 25px; }}
        .progress-bg {{ background: #334155; height: 26px; border-radius: 13px; overflow: hidden; margin: 20px 0; border: 1px solid #475569; position: relative; }}
        .progress-fill {{ background: linear-gradient(90deg, #3b82f6, #06b6d4); height: 100%; width: {pct:.1f}%; transition: width 0.4s ease-in-out; }}
        .stats {{ display: flex; justify-content: space-between; font-weight: bold; font-size: 15px; color: #cbd5e1; margin-top: 10px; }}
        .status-text {{ margin-top: 20px; font-size: 14px; color: #94a3b8; background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #1e293b; }}
        .badge-ort {{ color: #38bdf8; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 Extraktions-Fortschritt</h2>
        <div class="progress-bg">
            <div class="progress-fill"></div>
        </div>
        <div class="stats">
            <span>Fortschritt: {pct:.1f}%</span>
            <span>{current_idx + 1} / {total_pages} Seiten</span>
        </div>
        <div class="status-text">Zuletzt verarbeitet: <span class="badge-ort">{html.escape(last_ort or 'In Bearbeitung...')}</span></div>
    </div>
</body>
</html>
"""
    try:
        with open(progress_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception:
        pass

if text_pages:
    print(f"✅ {len(text_pages)} Seiten Text. Starte KI (Layout Jahr: {PUBLICATION_YEAR})...")
    system_prompt = get_system_prompt(PUBLICATION_YEAR, vocab_instruction)
    
    all_records = []
    for i in tqdm(range(len(text_pages)), desc="Extraktion"):
        current = text_pages[i]
        if i > 0:
            context = text_pages[i-1][-2000:] + "\n--- SEITENWECHSEL ---\n" + current
        else:
            context = current

        data = extract_data_with_gemini(context, system_prompt)
        last_found_ort = ""
        if data and "eintraege" in data:
            if data["eintraege"]:
                last_found_ort = data["eintraege"][-1].get("ort", "")
            for item in data["eintraege"]:
                mid = item.get('massnahme_id')
                ort = item.get('ort')
                
                # Suche nach existierendem Eintrag zur Zusammenführung
                existing = None
                if mid:
                    for r in all_records:
                        if r.get('massnahme_id') == mid and r.get('ort') == ort:
                            existing = r
                            break
                
                if existing:
                    # Zusammenführen der Rohdaten bei Seitenübergängen
                    for field in ['befunde_roh', 'funde_roh', 'datierung_roh']:
                        old_val = str(existing.get(field, '')).strip()
                        new_val = str(item.get(field, '')).strip()
                        if new_val and new_val != "-":
                            if old_val == "-":
                                existing[field] = new_val
                            elif new_val not in old_val:
                                existing[field] = f"{old_val} | {new_val}"
                                
                    # Zusammenführen der normalisierten Daten bei Seitenübergängen
                    for field in ['befunde_norm', 'funde_norm', 'datierung_norm']:
                        old_val = str(existing.get(field, '')).strip()
                        new_val = str(item.get(field, '')).strip()
                        if new_val and new_val != "-":
                            if old_val == "-":
                                existing[field] = new_val
                            elif new_val not in old_val:
                                existing[field] = f"{old_val}, {new_val}"
                else:
                    all_records.append(item)
        write_live_progress(i, len(text_pages), last_found_ort)
        time.sleep(1.0) # Etwas mehr Puffer für die Rate Limits

    df = pd.DataFrame(all_records)
    if not df.empty:
        if 'ort' in df.columns: df = df[df['ort'].str.len() > 1]
        for col in ['datierung_norm', 'befunde_norm', 'funde_norm']:
            if col in df.columns:
                df[col] = df[col].apply(validate_and_mark)

        # Bestimme den Namen der Ausgabe-CSV dynamisch basierend auf dem Dateinamen
        pdf_name_clean = os.path.splitext(os.path.basename(pdf_path))[0] if pdf_path else "1970"
        out_filename = f"LVR_{pdf_name_clean}_Split_Fixed.csv"
        out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_filename)
            
        df.to_csv(out_file, sep=";", index=False, encoding="utf-8-sig")
        print(f"Datei gespeichert: {out_file}")
        print(df[['massnahme_id', 'ort', 'befunde_norm', 'funde_norm']].head(20).to_string())
        
        # Automatisch HTML-Vorschau mit Farbhervorhebung generieren
        try:
            from generate_preview import create_highlighted_html
            preview_filename = f"LVR_{pdf_name_clean}_Highlighted_Preview.html"
            preview_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), preview_filename)
            create_highlighted_html(out_file, txt_file, preview_file)
        except Exception as pe:
            print(f"Fehler bei der Preview-Generierung: {pe}")
    else:
        print("⚠️ Keine Daten gefunden.")
else:
    print("⚠️ PDF Text leer.")