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
import html
from tqdm import tqdm
from rdflib import Graph, Namespace, RDF, SKOS

# ==========================================
# 1. KONFIGURATION
# ==========================================

# Lokale Pfade auf Ihrem Windows-System
pdf_base_dir = r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\BJB_PDF_1970_2014"
if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = "1984.pdf"

# Vokabular-Verzeichnis (Suchpfad: Sciebo oder lokal im Workspace)
vocab_base_dir = r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\Vokabulare"
if not os.path.exists(vocab_base_dir):
    vocab_base_dir = os.path.dirname(os.path.abspath(__file__))

# Automatische Suche im PDF-Verzeichnis (auch in Dekaden-Unterordnern)
pdf_path = None
if os.path.exists(pdf_base_dir):
    for root, dirs, files in os.walk(pdf_base_dir):
        if filename in files:
            pdf_path = os.path.join(root, filename)
            break
if not pdf_path and os.path.exists(pdf_base_dir):
    pdf_path = os.path.join(pdf_base_dir, filename)

# API Key & Client Initialisierung
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
key_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_API.txt")
if not GOOGLE_API_KEY and os.path.exists(key_file_path):
    try:
        with open(key_file_path, "r", encoding="utf-8") as kf:
            GOOGLE_API_KEY = kf.read().strip()
            print("🔑 API Key aus google_API.txt erfolgreich geladen.")
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen von google_API.txt: {e}")

try:
    if GOOGLE_API_KEY:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    else:
        client = genai.Client() # Versucht Umgebungsvariablen automatisch auszulesen
except Exception as e:
    print(f"⚠️ Hinweis bei GenAI Client Init: {e}")
    client = None

MODEL_NAME = "gemini-2.5-flash"

# Seitenbereich (25 Seiten in der Mitte des Bandes)
START_PAGE = 1
END_PAGE = 400
# Bestimme das Publikationsjahr aus dem PDF-Namen für die Layout-Auswahl
try:
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
    PUBLICATION_YEAR = int(year_match.group(1)) if year_match else 2006
except Exception:
    PUBLICATION_YEAR = 2006

# ==========================================
# 2. SKOS PARSER FÜR DAS EINHEITLICHE VOKABULAR
# ==========================================

EPOCH_LOOKUP = {}
BEFUND_LOOKUP = {}
FUND_LOOKUP = {}
ALL_SKOS_LOOKUP = {}

def load_arch_vocab_rhineland(base_dir):
    ttl_path = os.path.join(base_dir, "arch_vocab_rhineland.ttl")
    ws_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(ttl_path):
        ttl_path = os.path.join(ws_dir, "arch_vocab_rhineland.ttl")

    if not os.path.exists(ttl_path):
        print(f"⚠️ Vokabular-Datei nicht gefunden: {ttl_path}")
        return ""

    print(f"📚 Lade einheitliches Archäologie-Vokabular: {os.path.basename(ttl_path)}...")
    g = Graph()
    try:
        g.parse(ttl_path, format="turtle")
    except Exception as e:
        print(f"⚠️ Fehler beim Parsen von {os.path.basename(ttl_path)}: {e}")
        return ""

    cat_map = {
        'http://vocabs.bcdh.uni-bonn.de/LVR_Fundansprachen/concept_4de8f3b0': 'Datierung',
        'http://vocabs.bcdh.uni-bonn.de/LVR_Fundansprachen/concept_4c5049c7': 'Befund',
        'http://vocabs.bcdh.uni-bonn.de/LVR_Fundansprachen/concept_e9dddde8': 'Fund'
    }

    memo = {}
    def get_category(concept, visited=None):
        c_str = str(concept)
        if c_str in memo: return memo[c_str]
        if visited is None: visited = set()
        if concept in visited: return None
        visited.add(concept)
        
        if c_str in cat_map:
            return cat_map[c_str]
        for b in g.objects(concept, SKOS.broader):
            cat = get_category(b, visited)
            if cat:
                memo[c_str] = cat
                return cat
        memo[c_str] = None
        return None

    NUMISMATIC_STOPWORDS = {
        'au', 'ar', 's', 'dp', 'fol', 'an', 'd', 'av', 'rv', 'ric', 'ric²', 'ric3', 'ric4', 'ric5',
        'av.', 'rv.', 'g', 'mm', 'ca', 'v.', 'chr.', 'rom', 'typ', 'var', 'nr.', 'nr'
    }

    prompt_sections = {'Datierung': [], 'Befund': [], 'Fund': []}

    for concept in g.subjects(RDF.type, SKOS.Concept):
        cat_name = get_category(concept)
        if not cat_name:
            continue

        if cat_name == 'Datierung':
            target_dict = EPOCH_LOOKUP
        elif cat_name == 'Befund':
            target_dict = BEFUND_LOOKUP
        else:
            target_dict = FUND_LOOKUP

        pref_labels = []
        for label in g.objects(concept, SKOS.prefLabel):
            lang = getattr(label, 'language', None)
        all_labels = []
        for label in list(g.objects(concept, SKOS.prefLabel)) + list(g.objects(concept, SKOS.altLabel)):
            term = str(label).strip()
            if term and term not in all_labels:
                all_labels.append(term)

        if all_labels:
            main_term = all_labels[0]
            clean_main = re.sub(r'\s*\([^)]*\)', '', main_term).strip()

            variants = []
            for l in all_labels:
                l_clean = re.sub(r'\s*\([^)]*\)', '', l).strip()
                variants.extend([l, l_clean])
                l_low = l.lower()
                if 'konstantin der große' in l_low or 'constantine the great' in l_low:
                    variants.extend(['Konstantin I.', 'Constantin I.', 'Konstantin I', 'Constantin I', 'Constantin'])
                if 'philippus arabs' in l_low or 'philip the arab' in l_low:
                    variants.extend(['Philippus I.', 'Philippus I'])
                if 'mark aurel' in l_low or 'marcus aurelius' in l_low:
                    variants.extend(['Marc Aurel', 'Marc Aurel f. Lucilla', 'Marc Aurel f. Lucius Verus'])

            alt_labels = []
            for var in variants:
                if not var: continue
                var_str = str(var).strip()
                v_low = var_str.lower()
                if v_low not in NUMISMATIC_STOPWORDS and (len(v_low) >= 3 or var_str == "As"):
                    target_dict[v_low] = main_term
                    if v_low not in ALL_SKOS_LOOKUP:
                        ALL_SKOS_LOOKUP[v_low] = (main_term, cat_name)

                    if 'konstantin' in v_low:
                        target_dict[v_low.replace('konstantin', 'constantin')] = main_term
                        ALL_SKOS_LOOKUP[v_low.replace('konstantin', 'constantin')] = (main_term, cat_name)
                    if 'mark aurel' in v_low:
                        target_dict[v_low.replace('mark aurel', 'marc aurel')] = main_term
                        ALL_SKOS_LOOKUP[v_low.replace('mark aurel', 'marc aurel')] = (main_term, cat_name)
                    if v_low.endswith('.'):
                        target_dict[v_low[:-1]] = main_term
                        ALL_SKOS_LOOKUP[v_low[:-1]] = (main_term, cat_name)

                    if var_str != main_term and var_str not in alt_labels:
                        alt_labels.append(var_str)

            entry = f"- {main_term}"
            if alt_labels:
                entry += f" (Syn: {', '.join(alt_labels[:2])})"
            prompt_sections[cat_name].append(entry)

    instruction = "OFFIZIELLES SKOS-VOKABULAR (VERWENDE DIESE BEGRIFFE BEVORZUGT BEI DER EXTRAKTION UND NORMALISIERUNG):\n\n"
    instruction += "=== 1. DATIERUNG / EPOCHEN / KAISER UND HERRSCHER ===\n"
    instruction += "\n".join(sorted(prompt_sections['Datierung'])) + "\n\n"
    instruction += "=== 2. BEFUNDE (Immobile / Ortsfeste Strukturen) ===\n"
    instruction += "\n".join(sorted(prompt_sections['Befund'])) + "\n\n"
    instruction += "=== 3. FUNDE (Mobile Objekte / Artefakte) ===\n"
    instruction += "\n".join(sorted(prompt_sections['Fund'])) + "\n"

    return instruction

vocab_instruction = load_arch_vocab_rhineland(vocab_base_dir)

# ==========================================
# 3. VALIDIERUNG & DEDUPLIZIERUNG (POST-PROCESSING)
# ==========================================

INVALID_ORTS = {"ich", "im", "in", "am", "an", "der", "die", "das", "dem", "den", "und", "oder", "es", "wir", "sie", "er", "aus", "von", "bei", "jahresbericht", "aufgrabungen", "funde", "befunde", "römische zeit", "none", "null", "nan", "-", ""}

EPOCH_ADJECTIVE_MAP = {
    'hallstattzeitlich': 'Hallstattzeit',
    'latènezeitlich': 'Latènezeit',
    'merowingerzeitlich': 'Merowingerzeit',
    'karolingerzeitlich': 'Karolingerzeit',
    'völkerwanderungszeitlich': 'Völkerwanderungszeit',
    'bronzezeitlich': 'Bronzezeit',
    'eisenzeitlich': 'Eisenzeit',
    'neolithisch': 'Neolithikum',
    'mesolithisch': 'Mesolithikum',
    'paläolithisch': 'Paläolithikum',
    'bandkeramisch': 'Bandkeramik',
    'schnurkeramisch': 'Schnurkeramik',
    'römisch': 'Römische Zeit',
    'spätrömisch': 'Spätrömische Zeit',
    'frührömisch': 'Frührömische Zeit',
    'kaiserzeitlich': 'Römische Kaiserzeit',
    'mittelalterlich': 'Mittelalter',
    'frühmittelalterlich': 'Frühmittelalter',
    'hochmittelalterlich': 'Hochmittelalter',
    'spätmittelalterlich': 'Spätmittelalter',
    'ottonisch': 'Ottonenzeit',
    'karolingisch': 'Karolingerzeit',
    'merowingisch': 'Merowingerzeit'
}

def extract_dating_prefix(term):
    """Prüft, ob ein Begriff ein Datierungsadjektiv (z.B. 'hallstattzeitlichen', 'römische') enthält und spaltet es ab."""
    clean = re.sub(r'\s*\(skos\)', '', term, flags=re.IGNORECASE).strip()
    words = clean.split()
    if not words:
        return None, clean

    first_word = words[0].lower()
    stemmed_adj = first_word
    for end in ['en', 'er', 'es', 'em', 'e', 'n', 's']:
        if stemmed_adj.endswith(end) and len(stemmed_adj) - len(end) >= 5:
            stemmed_adj = stemmed_adj[:-len(end)]
            break

    epoch_name = None
    if stemmed_adj in EPOCH_ADJECTIVE_MAP:
        epoch_name = EPOCH_ADJECTIVE_MAP[stemmed_adj]
    elif stemmed_adj.endswith('zeitlich'):
        base = stemmed_adj[:-8]
        epoch_name = base.capitalize() + "zeit"

    if epoch_name:
        remainder_noun = " ".join(words[1:]).strip() if len(words) > 1 else ""
        return epoch_name, remainder_noun

    return None, clean

def expand_compound_phrases(text_value):
    """Zerlegt koordinierte Ausdrücke wie 'Ziegel- und Keramikbruchstücke' in Einzelbegriffe."""
    if not isinstance(text_value, str):
        return []
    items = [x.strip() for x in re.split(r'[,|;]', text_value) if x.strip()]
    expanded = []
    for item in items:
        m = re.match(r'^([A-ZÄÖÜa-zäöüß]+)-\s+und\s+([A-ZÄÖÜa-zäöüß\s]+)$', item)
        if m:
            first_part = m.group(1)
            second_part = m.group(2)
            words2 = second_part.split()
            suffix = words2[-1] if words2 else ""
            m_sub = re.search(r'(bruchstücke|bruchstück|scherben|scherbe|ziegel|gefäße|gefäß|steine|stein)$', suffix, re.IGNORECASE)
            if m_sub:
                sub_suffix = m_sub.group(1)
                first_part_full = first_part + sub_suffix
            elif suffix and len(suffix) >= 4 and not first_part.lower().endswith(suffix.lower()):
                first_part_full = first_part
            else:
                first_part_full = first_part
            expanded.append(first_part_full)
            expanded.append(second_part)
        else:
            expanded.append(item)
    return expanded

def stem_german_word(w):
    """Entfernt typische deutsche Beugungs- und Pluralendungen für das SKOS-Matching."""
    w = w.lower().strip()
    for end in ['stücken', 'stücke', 'stück', 'ansprachen', 'ansprache', 'fundamente', 'fundament', 'stellen', 'stelle', 'gräber', 'grab', 'bauten', 'bau', 'es', 'en', 'er', 'e', 'n', 's']:
        if len(w) - len(end) >= 3 and w.endswith(end):
            return w[:-len(end)]
    return w

def clean_ort(ort_val):
    if not ort_val or not isinstance(ort_val, str):
        return "-"
    cleaned = ort_val.strip()
    if cleaned.lower() in INVALID_ORTS or len(cleaned) <= 1:
        return "-"
    if re.match(r'^(ich|im|in|an|am|der|die|das)\b', cleaned, re.IGNORECASE):
        return "-"
    return cleaned

def normalize_items_list(text_value, primary_lookup=None):
    if not text_value or not isinstance(text_value, str) or text_value.strip() in ["-", "nan", "None"]:
        return []
    
    raw_items = expand_compound_phrases(text_value)
    normalized_items = []
    
    for item in raw_items:
        clean = item.strip()
        clean_no_skos = re.sub(r'\s*\(skos\)', '', clean, flags=re.IGNORECASE).strip()
        if not clean_no_skos:
            continue
        
        clean_lower = clean_no_skos.lower()
        std_term = None

        if primary_lookup and clean_lower in primary_lookup:
            std_term = primary_lookup[clean_lower]
        elif clean_lower in ALL_SKOS_LOOKUP:
            std_term = ALL_SKOS_LOOKUP[clean_lower][0]
        else:
            stemmed = stem_german_word(clean_lower)
            if primary_lookup:
                for key, val in primary_lookup.items():
                    if stem_german_word(key) == stemmed or (len(stemmed) >= 4 and stemmed in key):
                        std_term = val
                        break
        if not std_term:
            COMPOUND_SUFFIX_MAP = {
                'krug': 'Krug (Gefäß)',
                'krüge': 'Krug (Gefäß)',
                'einhenkelkrug': 'Krug (Gefäß)',
                'zweihenkelkrug': 'Krug (Gefäß)',
                'zweihenkelkrüge': 'Krug (Gefäß)',
                'gefäß': 'Gefäß (Behälter)',
                'gefäße': 'Gefäß (Behälter)',
                'becher': 'Becher',
                'teller': 'Teller (Essgeschirr)',
                'topf': 'Topf (Behälter)',
                'töpfe': 'Topf (Behälter)',
                'schüssel': 'Schüssel (Gefäß)',
                'schüsseln': 'Schüssel (Gefäß)',
                'schale': 'Schale (Gefäß)',
                'schalen': 'Schale (Gefäß)',
                'urne': 'Aschenurne',
                'urnen': 'Aschenurne',
                'amphore': 'Amphore',
                'amphoren': 'Amphore',
                'dolium': 'Dolium'
            }
            for suf, target in COMPOUND_SUFFIX_MAP.items():
                if clean_lower.endswith(suf):
                    std_term = target
                    break
        
        if std_term:
            final_str = f"{std_term} (SKOS)"
        else:
            final_str = item if item.endswith(" (SKOS)") else item
            
        if final_str and final_str != "-":
            normalized_items.append(final_str)
            
    seen = set()
    dedup = []
    for it in normalized_items:
        if it not in seen:
            seen.add(it)
            dedup.append(it)
    return dedup

def postprocess_record(item):
    """Reinigt Ortsangaben, spaltet kombiniere Begriffe (z.B. 'römische Siedlung'), klassifiziert Begriffe neu und dedupliziert."""
    if not isinstance(item, dict):
        return item
    
    # 1. Ort & Kreis Säuberung
    item['ort'] = clean_ort(item.get('ort'))
    if item.get('kreis') and str(item.get('kreis')).strip().lower() in INVALID_ORTS:
        item['kreis'] = "-"

    # 2. Normalisierung
    d_list = normalize_items_list(str(item.get('datierung_norm', '')), EPOCH_LOOKUP)
    b_list = normalize_items_list(str(item.get('befunde_norm', '')), BEFUND_LOOKUP)
    f_list = normalize_items_list(str(item.get('funde_norm', '')), FUND_LOOKUP)

    # 3. Datierungsadjektive aus Befunden & Funden abspalten (z.B. 'römische Siedlungsstelle' -> Datierung: 'Römische Zeit', Befund: 'Siedlungsstelle')
    new_b_list = []
    for b in b_list:
        epoch_prefix, noun_rem = extract_dating_prefix(b)
        if epoch_prefix:
            match_epoch = EPOCH_LOOKUP.get(epoch_prefix.lower(), epoch_prefix)
            d_list.append(f"{match_epoch} (SKOS)")
            if noun_rem:
                norm_noun = normalize_items_list(noun_rem, BEFUND_LOOKUP)
                new_b_list.extend(norm_noun)
        else:
            new_b_list.append(b)
    b_list = new_b_list

    new_f_list = []
    for f in f_list:
        epoch_prefix, noun_rem = extract_dating_prefix(f)
        if epoch_prefix:
            match_epoch = EPOCH_LOOKUP.get(epoch_prefix.lower(), epoch_prefix)
            d_list.append(f"{match_epoch} (SKOS)")
            if noun_rem:
                norm_noun = normalize_items_list(noun_rem, FUND_LOOKUP)
                new_f_list.extend(norm_noun)
        else:
            new_f_list.append(f)
    f_list = new_f_list

    # 4. Klassentrennung & Umgruppierung
    NUMISMATIC_STOPWORDS = {
        'au', 'ar', 's', 'dp', 'fol', 'an', 'd', 'av', 'rv', 'ric', 'ric²', 'ric3', 'ric4', 'ric5',
        'av.', 'rv.', 'g', 'mm', 'ca', 'v.', 'chr.', 'rom', 'typ', 'var', 'nr.', 'nr'
    }
    
    ROMAN_EMPERORS_DICT = {
        "augustus": "Augustus",
        "tiberius": "Tiberius",
        "caligula": "Caligula",
        "claudius": "Claudius",
        "claudius i": "Claudius I.",
        "vespasian": "Vespasian",
        "titus": "Titus",
        "domitian": "Domitian",
        "nerva": "Nerva",
        "trajan": "Trajan",
        "hadrian": "Hadrian",
        "antoninus pius": "Antoninus Pius",
        "marc aurel": "Marc Aurel",
        "lucius verus": "Lucius Verus",
        "commodus": "Commodus",
        "septimius severus": "Septimius Severus",
        "caracalla": "Caracalla",
        "geta": "Geta",
        "elagabal": "Elagabal",
        "severus alexander": "Severus Alexander",
        "julia maesa": "Julia Maesa",
        "gordian iii": "Gordian III.",
        "gordian iii.": "Gordian III.",
        "philippus i": "Philippus I.",
        "philippus i.": "Philippus I.",
        "decius": "Decius",
        "valerian": "Valerian",
        "gallienus": "Gallienus",
        "probus": "Probus",
        "diokletian": "Diokletian",
        "maxentius": "Maxentius",
        "constantin i": "Constantin I.",
        "constantin i.": "Constantin I.",
        "constantin ii": "Constantin II.",
        "constantin ii.": "Constantin II.",
        "constantius": "Constantius",
        "crispina": "Crispina",
        "lucilla": "Lucilla"
    }

    full_item_text = f"{item.get('datierung_roh', '')} {item.get('befunde_roh', '')} {item.get('funde_roh', '')} {item.get('massnahme_id', '')}"
    for emp_key, emp_label in ROMAN_EMPERORS_DICT.items():
        if re.search(r'\b' + re.escape(emp_key) + r'\b', full_item_text, re.IGNORECASE):
            d_list.append(f"{emp_label} (SKOS)")

    final_f_list = []
    for f in f_list:
        clean_key = re.sub(r'\s*\(skos\)', '', f, flags=re.IGNORECASE).strip().lower()
        if clean_key in NUMISMATIC_STOPWORDS or (len(clean_key) < 3 and clean_key != "as"):
            continue
        if clean_key in EPOCH_LOOKUP or clean_key in ROMAN_EMPERORS_DICT or (clean_key in ALL_SKOS_LOOKUP and ALL_SKOS_LOOKUP[clean_key][1] == "Datierung"):
            d_list.append(f)
        elif clean_key in BEFUND_LOOKUP and clean_key not in FUND_LOOKUP:
            b_list.append(f)
        else:
            final_f_list.append(f)
    f_list = final_f_list

    final_b_list = []
    for b in b_list:
        clean_key = re.sub(r'\s*\(skos\)', '', b, flags=re.IGNORECASE).strip().lower()
        if clean_key in NUMISMATIC_STOPWORDS or (len(clean_key) < 3 and clean_key != "as"):
            continue
        if clean_key in EPOCH_LOOKUP or clean_key in ROMAN_EMPERORS_DICT or (clean_key in ALL_SKOS_LOOKUP and ALL_SKOS_LOOKUP[clean_key][1] == "Datierung"):
            d_list.append(b)
        elif clean_key in FUND_LOOKUP and clean_key not in BEFUND_LOOKUP:
            f_list.append(b)
        else:
            final_b_list.append(b)
    b_list = final_b_list

    def dedup(l):
        seen = set()
        res = []
        for x in l:
            clean_key = re.sub(r'\s*\(skos\)', '', str(x), flags=re.IGNORECASE).strip()
            clean_lower = clean_key.lower()
            if clean_lower in NUMISMATIC_STOPWORDS or (len(clean_key) < 3 and clean_key != "As"):
                continue
            if x not in seen and x != "-":
                seen.add(x)
                res.append(x)
        return res

    d_list = dedup(d_list)
    b_list = dedup(b_list)
    f_list = dedup(f_list)

    item['datierung_norm'] = ", ".join(d_list) if d_list else "-"
    item['befunde_norm'] = ", ".join(b_list) if b_list else "-"
    item['funde_norm'] = ", ".join(f_list) if f_list else "-"

    return item

def validate_and_mark(text_value):
    items = normalize_items_list(text_value)
    return ", ".join(items) if items else "-"

# ==========================================
# 4. PDF TEXT BEREINIGUNG
# ==========================================

def clean_ocr_errors(text):
    if not text:
        return ""
    ocr_fixes = [
        (r'\brbmisch(e|er|es|em|en)?\b', r'römisch\1'),
        (r'\brbmische(r|s|n)?\b', r'römische\1'),
        (r'\bLbbabdeckung\b', 'Lehmabdeckung'),
        (r'\bgebffnet\b', 'geöffnet'),
        (r'\bliefi\b', 'ließ'),
        (r'\bHalfte\b', 'Hälfte'),
        (r'\bgrbBeren\b', 'größeren'),
        (r'\bgrbBere\b', 'größere'),
        (r'\bgrbBerer\b', 'größerer'),
        (r'\bJiilich\b', 'Jülich'),
        (r'\bBriihl\b', 'Brühl'),
        (r'\bBodenbrst\.\b', 'Bodenbruchstück'),
        (r'\bbrst\.\b', 'bruchstück'),
        (r'\bBruchst\.\b', 'Bruchstück'),
        (r'\bBrst\.\b', 'Bruchstück'),
        (r'\bWandbrst\.\b', 'Wandbruchstück'),
        (r'\bRandbrst\.\b', 'Randbruchstück'),
        (r'\bAnschluB\b', 'Anschluss'),
        (r'([a-zäöüß]+)\.oder([a-zäöüß]+)', r'\1. oder \2'),
        (r'\b([A-Za-zäöüÄÖÜß]{3,})u\.\s+([A-ZÄÖÜa-zäöüß])', r'\1 u. \2'),
        (r'([A-Z][a-zäöüß]+)f\.\s*([A-Z][a-zäöüß]+)', r'\1 f. \2'),
        (r'([IVXLCDM]+)\.f\.\s*([A-Z][a-zäöüß]+)', r'\1. f. \2'),
        (r'(\b[A-Za-zäöüÄÖÜß]+),dervorallemaus\b', r'\1, der vor allem aus'),
        (r'(\b[A-Za-zäöüÄÖÜß]+)dermittleren\b', r'\1 der mittleren'),
        (r'([a-zäöüß])-\s*\n\s*([a-zäöüß])', r'\1\2'),
        (r'\b(RS|BS|WS|St|Nr)\.?([A-ZÄÖÜ][a-zäöüß]+)', r'\1 \2'),
        (r'([a-zäöüß\.\)])([A-ZÄÖÜ])', r'\1 \2'),
        (r'(\))([A-ZÄÖÜa-zäöüß])', r'\1 \2'),
        (r'([a-zäöüß])(Abb\.|Bild)', r'\1 \2'),
    ]
    for pattern, replacement in ocr_fixes:
        text = re.sub(pattern, replacement, text)
    return text

def clean_text(text):
    if not text: return ""
    replacements = {'':'1', '':'2', '':'3', '':'4', '':'5', '':'6', '':'7', '':'8', '':'9', '':'0'}
    for old, new in replacements.items(): text = text.replace(old, new)
    text = clean_ocr_errors(text)
    header_pattern = r'(Römische\s+Zeit\s+\d+)|(\d+\s+Römische\s+Zeit)'
    text = re.sub(header_pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'Abb\.\s*\d+[^\n]*?(?:\n[^\n]*?){0,2}?Ma[ßfhmalit-]{1,5}\s*stab\s*\d+\s*:\s*\d+\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Abb\.\s*\d+\s+[A-ZÄÖÜ][^\n]+', '', text)
    return text

def extract_page_text_lazy(pdf_path, page_idx):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if 0 <= page_idx < len(pdf.pages):
                page = pdf.pages[page_idx]
                width = page.width
                height = page.height
                
                # Exclude top 3% (running headers) and bottom 3% (footers)
                top_y = height * 0.03
                bottom_y = height * 0.97
                mid_x = width / 2
                
                left_crop = page.crop((0, top_y, mid_x, bottom_y))
                right_crop = page.crop((mid_x, top_y, width, bottom_y))
                
                left_text = left_crop.extract_text() or ""
                right_text = right_crop.extract_text() or ""
                
                if len(left_text.strip()) > 50 and len(right_text.strip()) > 50:
                    combined_text = "--- LEFT COLUMN ---\n" + left_text.strip() + "\n\n--- RIGHT COLUMN ---\n" + right_text.strip()
                else:
                    full_crop = page.crop((0, top_y, width, bottom_y))
                    combined_text = full_crop.extract_text() or ""
                    
                return clean_text(combined_text)
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen der Seite {page_idx+1}: {e}")
    return None

# ==========================================
# 5. KI EXTRAKTION (MIGRATION AUF GOOGLE-GENAI)
# ==========================================

def get_system_prompt(year, vocab_instruction):
    prompt_common = f"""{vocab_instruction}

Du bist ein hochspezialisierter Experte für die archäologische Datenerfassung der "Bonner Jahrbücher". Deine Aufgabe ist die präzise Extraktion von Fundstellen und den darunter erfolgten Maßnahmen in ein strukturiertes JSON-Format.

### KERN-AUFGABEN & STRIKTE KLASSENTRENNUNG:
1. **ort** & **kreis**: Geografische Lage (Städte, Gemeinden, Kreise, Ortsteile, z. B. 'Jülich', 'Brühl', 'Haaren', 'Gressenich', 'Mausbach').
   - **SEHR WICHTIG**: Verwende NIEMALS Personalpronomen ("ich", "es", "wir"), Präpositionen ("im", "in", "am") oder Berichts-Füllwörter als Ortsnamen! Falls kein Ort vorhanden ist, verwende "-".
2. **massnahme_id**:
   - **WICHTIGE REGEL FÜR ÄLTERE BÄNDE**: Erfasse Koordinaten (z. B. '(r 3497, h 4084)', '(r 3497, h 4084 und r 3500, h 4097)'), TK-Angaben (z. B. '(TK 5004 Jülich: r 3497, h 4084)', '(TK 5107 Brühl: r 6303, h 3760)') sowie Grabbezeichnungen ('Grab 1', 'Grab 2') IMMER als `massnahme_id`!
3. **datierung_norm** / **datierung_roh**: Zeitstellung, Epochen, Jahrhunderte (z. B. '71 n. Chr.', '2. Jh. n. Chr.', '5. Jh. n. Chr.', 'römisch') UND archäologische Kulturen (z. B. 'Michelsberger Kultur', 'Bandkeramik', 'Römerzeit', 'Neolithikum').
   - **SEHR WICHTIG**: Archäologische Kulturen gehören IMMER zur Datierung und NIEMALS zu Funden oder Befunden!
4. **befunde_norm** / **befunde_roh**: Immobile / ortsfeste Befunde & Strukturen.
   - Beispiel: Grube, Pfostenloch, Ofen, Graben, Mauer, Gräberfeld, Grundriss, Siedlung, Villa rustica, Aquädukt, Torturm, Steinkastell, Lehmabdeckung, Fundament.
5. **funde_norm** / **funde_roh**: Mobile Objekte, Artefakte & Gegenstände.
   - Beispiel: Keramik, Scherbe, Beil, Klinge, Axt, Pfeilspitze, Abschlag, Klopfer, Reiber, Münze, Fibeln, Schüssel, Krug, Gefäß, Ziegel, Nagel, Bauelemente.

### VOLLSTÄNDIGKEIT BEI KAISERN, MÜNZEN, WASSERLEITUNGEN UND GEFÄSSEN:
- **Römische Kaiser & Herrscher**: Erfasse ALLE im Text erwähnten römischen Kaiser (z. B. Augustus, Tiberius, Caligula, Claudius I., Vespasian, Domitian, Nerva, Trajan, Hadrian, Antoninus Pius, Marc Aurel, Lucius Verus, Commodus, Septimius Severus, Geta, Julia Maesa, Gordian III., Philippus I., Constantin I., Constantin II.) VOLLSTÄNDIG in `datierung_roh` und `datierung_norm`.
- **Wasserleitungen & Bauwerke**: Erfasse 'Eifelwasserleitung', 'römische Wasserleitung', 'Wasserleitung', 'Kanal', 'Frischwasserkanäle', 'Sammler', 'Fundamentplatte' VOLLSTÄNDIG in `befunde_norm` (Wasserleitung, Kanal, Fundament).
- **Gefäßformen & Funde**: Erfasse 'Einhenkelkrug', 'Einhenkelkrüge', 'Zweihenkelkrüge', 'Glanztonwarebecher', 'Terra sigillata: Schale', 'Statuette des Mars Ultor', 'Helm', 'Panzerung', 'Beinschienen' VOLLSTÄNDIG in `funde_norm`.

### STRIKTE TRENNUNG VON KOMBINIERTEN EIGENSCHAFTSWÖRTERN:
- Wenn im Text 'römische Siedlungsstelle', 'römische Mauerfundamente' oder 'spätrömisches Gräberfeld' steht, TRENNEN:
  - `datierung_norm`: Römische Zeit (oder römisch)
  - `befunde_norm`: Siedlung, Mauer, Gräberfeld (ohne das Eigenschaftswort 'römisch')

### DUPLIKAT-REGEL PRO AKTIVITÄT:
- Nenne in `funde_norm`, `befunde_norm` und `datierung_norm` jeden eindeutigen Begriff pro Maßnahme **NUR EINMAL** (keine doppelten Nennungen).
"""

    if year < 1990:
        # Prompt optimiert für das 1970er/1980er Layout (inline Ortsnamen, r/h Gauß-Krüger Koordinaten)
        return prompt_common + f"""
### SPECIFICS FÜR 1970er/1980er BÄNDE
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
- **_norm Felder**: Nutze ausschließlich Begriffe aus den bereitgestellten Vokabularen zur Normalisierung.
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
      "datierung_norm": "Normalisierter Begriff (z. B. Michelsberger Kultur)",
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
        # Prompt optimiert für das 1990er/2000er Layout
        return prompt_common + f"""
### SPECIFICS FÜR 1990er/2000er BÄNDE
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
- **_norm Felder**: Nutze ausschließlich Begriffe aus den bereitgestellten Vokabularen zur Normalisierung.
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
    if client is None:
        print("❌ KI-Client ist nicht initialisiert! Bitte setzen Sie $env:GOOGLE_API_KEY in der Konsole.")
        return {"eintraege": []}
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
    
def write_live_progress(current_idx, total_pages, last_ort="", phase="Extraktion", preview_file=""):
    raw_pct = (current_idx + 1) / total_pages * 100 if total_pages > 0 else 0
    pct = min(100.0, raw_pct)
    is_finished = (pct >= 100.0 or phase.startswith("Fertiggestellt"))
    
    progress_html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.html")
    
    status_icon = "✅" if is_finished else "🚀"
    title_text = "Extraktion Abgeschlossen (100%)" if is_finished else f"Extraktions-Fortschritt ({pct:.1f}%)"
    
    # Auto-refresh nur während der Extraktion, stoppen bei 100%
    refresh_tag = '<meta http-equiv="refresh" content="3">' if not is_finished else ''
    
    preview_link_html = ""
    if is_finished:
        p_filename = os.path.basename(preview_file) if preview_file else "LVR_1973_Highlighted_Preview.html"
        preview_link_html = f"""
        <div style="margin-top: 20px;">
            <a href="{html.escape(p_filename)}" target="_blank" style="display: inline-block; background: linear-gradient(90deg, #10b981, #059669); color: white; text-decoration: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 12px rgba(16,185,129,0.3);">
                🔍 HTML-Vorschau öffnen ({html.escape(p_filename)})
            </a>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    {refresh_tag}
    <title>{title_text}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
        .card {{ background: #1e293b; padding: 35px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 480px; text-align: center; border: 1px solid #334155; }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 22px; margin-bottom: 25px; }}
        .progress-bg {{ background: #334155; height: 26px; border-radius: 13px; overflow: hidden; margin: 20px 0; border: 1px solid #475569; position: relative; }}
        .progress-fill {{ background: {'linear-gradient(90deg, #10b981, #059669)' if is_finished else 'linear-gradient(90deg, #3b82f6, #06b6d4)'}; height: 100%; width: {pct:.1f}%; transition: width 0.4s ease-in-out; }}
        .stats {{ display: flex; justify-content: space-between; font-weight: bold; font-size: 15px; color: #cbd5e1; margin-top: 10px; }}
        .status-text {{ margin-top: 20px; font-size: 14px; color: #94a3b8; background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #1e293b; }}
        .badge-ort {{ color: #38bdf8; font-weight: bold; }}
        .phase-tag {{ font-size: 12px; color: #38bdf8; background: rgba(56,189,248,0.1); padding: 4px 8px; border-radius: 4px; margin-left: 6px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>{status_icon} Extraktions-Fortschritt <span class="phase-tag">{html.escape(phase)}</span></h2>
        <div class="progress-bg">
            <div class="progress-fill"></div>
        </div>
        <div class="stats">
            <span>Fortschritt: {pct:.1f}%</span>
            <span>{min(current_idx + 1, total_pages)} / {total_pages} Seiten</span>
        </div>
        <div class="status-text">Zuletzt verarbeitet: <span class="badge-ort">{html.escape(last_ort or ('Abgeschlossen' if is_finished else 'In Bearbeitung...'))}</span></div>
        {preview_link_html}
    </div>
</body>
</html>
"""
    try:
        with open(progress_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception:
        pass

# ==========================================
# 6. WORKFLOW
# ==========================================

def run_pipeline():
    text_pages = []

    pdf_name_clean = os.path.splitext(os.path.basename(pdf_path))[0] if pdf_path else "1970"
    txt_filename = f"LVR_{pdf_name_clean}_raw_text.txt"
    cleaned_txt_filename = f"LVR_{pdf_name_clean}_cleaned_text.txt"
    ws_dir = os.path.dirname(os.path.abspath(__file__))
    txt_file = os.path.join(ws_dir, txt_filename)
    cleaned_txt_file = os.path.join(ws_dir, cleaned_txt_filename)

    if os.path.exists(cleaned_txt_file):
        print(f"📖 Lade vorbereiteten & geprüften OCR-Text aus: {os.path.basename(cleaned_txt_file)}...")
        try:
            with open(cleaned_txt_file, "r", encoding="utf-8") as f:
                content = f.read()
            pages_raw = re.split(r'--- SEITE \d+ ---\n', content)
            for p in pages_raw[1:]:
                pt = clean_text(p.strip())
                if pt: text_pages.append(pt)
            if not text_pages and content.strip():
                text_pages.append(clean_text(content.strip()))
            print(f"✅ {len(text_pages)} Seiten erfolgreich aus bereinigtem OCR-Text geladen.")
        except Exception as e:
            print(f"⚠️ Fehler beim Lesen von {cleaned_txt_file}: {e}")

    if not text_pages and pdf_path and os.path.exists(pdf_path):
        print(f"📖 Lese PDF (S. {START_PAGE}-{END_PAGE})...")
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
            write_live_progress(len(text_pages) - 1, (real_end - START_PAGE + 1), phase="PDF Einlesen")

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
    elif not text_pages and os.path.exists(txt_file):
        print(f"📖 PDF nicht gefunden, aber Rohtext-Datei {txt_file} existiert. Lade Seiten aus dem Rohtext...")
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read()
            pages_raw = re.split(r'--- SEITE \d+ ---\n', content)
            for p in pages_raw[1:]:
                pt = clean_text(p.strip())
                if pt: text_pages.append(pt)
            print(f"✅ {len(text_pages)} Seiten erfolgreich aus Rohtext geladen.")
        except Exception as e:
            print(f"❌ Fehler beim Lesen der Rohtext-Datei: {e}")
    else:
        print("❌ Weder PDF noch Rohtext-Datei gefunden.")

    if text_pages:
        print(f"✅ {len(text_pages)} Seiten Text. Starte KI (Layout Jahr: {PUBLICATION_YEAR})...")
        system_prompt = get_system_prompt(PUBLICATION_YEAR, vocab_instruction)
        
        all_records = []
        last_found_ort = ""

        for i in tqdm(range(len(text_pages)), desc="Extraktion"):
            current = text_pages[i]
            if i > 0:
                context = text_pages[i-1][-2000:] + "\n--- SEITENWECHSEL ---\n" + current
            else:
                context = current

            data = extract_data_with_gemini(context, system_prompt)
            if data and "eintraege" in data and data["eintraege"]:
                for item in data["eintraege"]:
                    ort_val = item.get("ort")
                    if ort_val and clean_ort(ort_val) != "-":
                        last_found_ort = ort_val
                    
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
                        for field in ['befunde_roh', 'funde_roh', 'datierung_roh']:
                            old_val = str(existing.get(field, '')).strip()
                            new_val = str(item.get(field, '')).strip()
                            if new_val and new_val != "-":
                                if old_val == "-":
                                    existing[field] = new_val
                                elif new_val not in old_val:
                                    existing[field] = f"{old_val} | {new_val}"
                                    
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

            write_live_progress(i, len(text_pages), last_found_ort, phase="KI Extraktion")
            time.sleep(1.0)

        processed_records = [postprocess_record(r) for r in all_records]
        df = pd.DataFrame(processed_records)
        if not df.empty:
            if 'ort' in df.columns:
                df = df[~df['ort'].astype(str).str.lower().isin(INVALID_ORTS) & (df['ort'].astype(str).str.len() > 1)]
            for col in ['datierung_norm', 'befunde_norm', 'funde_norm']:
                if col in df.columns:
                    df[col] = df[col].apply(validate_and_mark)

            pdf_name_clean = os.path.splitext(os.path.basename(pdf_path))[0] if pdf_path else "1970"
            out_filename = f"LVR_{pdf_name_clean}_Split_Fixed.csv"
            out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_filename)
                
            df.to_csv(out_file, sep=";", index=False, encoding="utf-8-sig")
            print(f"Datei gespeichert: {out_file}")
            print(df[['massnahme_id', 'ort', 'befunde_norm', 'funde_norm']].head(20).to_string())
            
            preview_file = ""
            try:
                from generate_preview import create_highlighted_html
                preview_filename = f"LVR_{pdf_name_clean}_Highlighted_Preview.html"
                preview_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), preview_filename)
                create_highlighted_html(out_file, txt_file, preview_file)
            except Exception as pe:
                print(f"Fehler bei der Preview-Generierung: {pe}")
            
            write_live_progress(len(text_pages) - 1, len(text_pages), last_found_ort, phase="Fertiggestellt ✅", preview_file=preview_file)
        else:
            print("⚠️ Keine Daten gefunden.")
    else:
        print("⚠️ PDF Text leer.")

if __name__ == "__main__":
    run_pipeline()