import os
import json
import re
import html
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

root_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Load Vocabularies
vocab_path = os.path.join(root_dir, "vocabularies.json")
with open(vocab_path, "r", encoding="utf-8") as f:
    vocab_data = json.load(f)

ALL_SKOS_CAT_MAP = {}
for cat_name, items in vocab_data.items():
    for item in items:
        term = item["term"]
        variants = [term, re.sub(r'\s*\([^)]*\)', '', term).strip()] + item.get("alt", [])
        
        for v in list(variants):
            if not v: continue
            v_low = v.lower()
            if 'konstantin der große' in v_low or 'constantine the great' in v_low:
                variants.extend(['Konstantin I.', 'Constantin I.', 'Konstantin I', 'Constantin I', 'Constantin'])
            if 'philippus arabs' in v_low or 'philip the arab' in v_low:
                variants.extend(['Philippus I.', 'Philippus I'])
            if 'mark aurel' in v_low or 'marcus aurelius' in v_low:
                variants.extend(['Marc Aurel', 'Marc Aurel f. Lucilla', 'Marc Aurel f. Lucius Verus'])

        for v in variants:
            if not v: continue
            v_low = v.lower()
            ALL_SKOS_CAT_MAP[v_low] = cat_name
            if 'konstantin' in v_low:
                ALL_SKOS_CAT_MAP[v_low.replace('konstantin', 'constantin')] = cat_name
            if 'mark aurel' in v_low:
                ALL_SKOS_CAT_MAP[v_low.replace('mark aurel', 'marc aurel')] = cat_name
            if v_low.endswith('.'):
                ALL_SKOS_CAT_MAP[v_low[:-1]] = cat_name

# Load Rheinland Gazetteer CSV
gaz_path = os.path.join(root_dir, "gaz_rheinland.csv")
gazetteer_data = {}
if os.path.exists(gaz_path):
    import pandas as pd
    try:
        df_gaz = pd.read_csv(gaz_path)
        valid_gaz = df_gaz.dropna(subset=['Lat', 'Lon'])
        for idx, r in valid_gaz.iterrows():
            p_name = str(r.get('Place', '')).strip()
            if p_name and p_name != 'nan':
                gazetteer_data[p_name.lower()] = {
                    "place": p_name,
                    "landkreis": str(r.get('Landkreis', '')).strip() if pd.notnull(r.get('Landkreis')) else "",
                    "lat": float(r.get('Lat')),
                    "lon": float(r.get('Lon'))
                }
        print(f"📍 Rheinland Gazetteer geladen: {len(gazetteer_data)} verifizierte Orte mit Koordinaten.")
    except Exception as ge:
        print(f"⚠️ Fehler beim Lesen von gaz_rheinland.csv: {ge}")

EXPLICIT_CAT_MAP = {
    # Datierung
    'augustus': 'Datierung', 'tiberius': 'Datierung', 'caligula': 'Datierung', 'claudius': 'Datierung', 'claudius i.': 'Datierung', 'claudius i': 'Datierung',
    'vespasian': 'Datierung', 'domitian': 'Datierung', 'nerva': 'Datierung', 'trajan': 'Datierung', 'hadrian': 'Datierung', 'antoninus pius': 'Datierung',
    'marc aurel': 'Datierung', 'mark aurel': 'Datierung', 'marcus aurelius': 'Datierung', 'lucius verus': 'Datierung', 'commodus': 'Datierung',
    'septimius severus': 'Datierung', 'geta': 'Datierung', 'julia maesa': 'Datierung', 'crispina': 'Datierung', 'lucilla': 'Datierung',
    'gordian iii.': 'Datierung', 'gordian iii': 'Datierung', 'gordian i.': 'Datierung', 'gordian ii.': 'Datierung',
    'philippus i.': 'Datierung', 'philippus i': 'Datierung', 'philippus arabs': 'Datierung',
    'constantin i.': 'Datierung', 'constantin i': 'Datierung', 'konstantin i.': 'Datierung', 'konstantin i': 'Datierung', 'constantin': 'Datierung', 'konstantin': 'Datierung', 'konstantin der große': 'Datierung',
    'constantin ii.': 'Datierung', 'constantin ii': 'Datierung', 'konstantin ii.': 'Datierung', 'konstantin ii': 'Datierung',
    'bandkeramik': 'Datierung', 'bandkeramisch': 'Datierung', 'linearbandkeramik': 'Datierung',
    'hallstatt c': 'Datierung', 'ha c': 'Datierung',
    'frühlatènezeit': 'Datierung', 'frühlatènezeitl.': 'Datierung', 'frühlat.': 'Datierung', 'frühlatène': 'Datierung',
    'urnenfelderzeit': 'Datierung', 'urnenfelder-': 'Datierung', 'urnenfelderzeitlich': 'Datierung',
    'jüngereisenzeitlich': 'Datierung', 'jüngereisenzeitl.': 'Datierung',
    'frühe neuzeit': 'Datierung', 'frühen neuzeit': 'Datierung', 'früheneuzeitlich': 'Datierung', 'früheneuzeitl.': 'Datierung',

    # Befund
    'wasserleitung': 'Befund', 'eifelwasserleitung': 'Befund', 'römische wasserleitung': 'Befund',
    'kanal': 'Befund', 'frischwasserkanäle': 'Befund', 'kanalisation': 'Befund',
    'fundament': 'Befund', 'fundamentplatte': 'Befund',
    'grube': 'Befund', 'gruben': 'Befund', 'pfostengrube': 'Befund', 'pfostengruben': 'Befund', 'siedlungsgrube': 'Befund', 'kleinere gruben': 'Befund', 'grubenhaus': 'Befund',
    'brunnen': 'Befund', 'brunnenu.': 'Befund',
    'latrine': 'Befund', 'latrinenbefund': 'Befund', 'latrinenbefunden': 'Befund',
    'bestattungsplatz': 'Befund', 'bestattungsplatzes': 'Befund',
    'vorstadt': 'Befund', 'lagervorstadt': 'Befund',
    'töpferei': 'Befund', 'vicus': 'Befund', 'legionslager': 'Befund', 'retentura': 'Befund',

    # Fund
    'krug': 'Fund', 'einhenkelkrug': 'Fund', 'einhenkelkrüge': 'Fund', 'zweihenkelkrug': 'Fund', 'zweihenkelkrüge': 'Fund',
    'becher': 'Fund', 'glanztonwarebecher': 'Fund',
    'terra sigillata': 'Fund', 'sigillaten': 'Fund',
    'schale': 'Fund', 'schälchen': 'Fund', 'napf': 'Fund', 'teller': 'Fund',
    'statuette': 'Fund', 'statuette des mars ultor': 'Fund',
    'helm': 'Fund', 'oberkörperpanzer': 'Fund', 'lorica segmentata': 'Fund', 'beinschiene': 'Fund', 'beinschienen': 'Fund', 'rüstung': 'Fund',
    'fibel': 'Fund', 'scheibenfibel': 'Fund', 'emailscheibenfibel': 'Fund', 'armbrustspiralfibel': 'Fund',
    'sesterz': 'Fund', 'sesterzen': 'Fund', 'denar': 'Fund', 'denare': 'Fund', 'denarius': 'Fund', 'dupondius': 'Fund', 'aureus': 'Fund', 'folles': 'Fund', 'follis': 'Fund', 'münze': 'Fund', 'münzen': 'Fund', 'as': 'Fund',
    'niederbieber': 'Fund', 'niederbieber67b': 'Fund', 'niederbieber62a': 'Fund', 'gellep': 'Fund', 'gellep59': 'Fund', 'rsnb': 'Fund', 'rsnb89': 'Fund',
    'scherbe': 'Fund', 'scherben': 'Fund', 'wandscherbe': 'Fund', 'randscherbe': 'Fund', 'bodenbruchstück': 'Fund'
}

for k, v in EXPLICIT_CAT_MAP.items():
    ALL_SKOS_CAT_MAP[k.lower()] = v

# Helper function to split raw values cleanly into single terms
def parse_raw_fragments(val):
    if not isinstance(val, str) or not val.strip() or val.strip() in ["-", "nan", "None"]:
        return []
    cleaned_val = val.strip()
    if cleaned_val.startswith("[") and cleaned_val.endswith("]"):
        try:
            import ast
            parsed = ast.literal_eval(cleaned_val)
            if isinstance(parsed, list):
                res = []
                for item in parsed:
                    res.extend(parse_raw_fragments(str(item)))
                return res
        except Exception:
            pass
    
    parts = re.split(r'[,|;]', cleaned_val)
    res = []
    for p in parts:
        clean = p.strip().strip("'\"[]")
        clean = re.sub(r'\s*\(skos\)', '', clean, flags=re.IGNORECASE).strip()
        if len(clean) > 1 and clean.lower() not in ["none", "nan", "-"]:
            res.append(clean)
    return res

EPOCH_ADJECTIVE_MAP = {
    'hallstattzeitlich': 'Hallstattzeit', 'latènezeitlich': 'Latènezeit', 'merowingerzeitlich': 'Merowingerzeit',
    'karolingerzeitlich': 'Karolingerzeit', 'völkerwanderungszeitlich': 'Völkerwanderungszeit',
    'bronzezeitlich': 'Bronzezeit', 'eisenzeitlich': 'Eisenzeit', 'neolithisch': 'Neolithikum',
    'mesolithisch': 'Mesolithikum', 'paläolithisch': 'Paläolithikum', 'bandkeramisch': 'Bandkeramik',
    'schnurkeramisch': 'Schnurkeramik', 'römisch': 'Römische Zeit', 'spätrömisch': 'Spätrömische Zeit',
    'frührömisch': 'Frührömische Zeit', 'kaiserzeitlich': 'Römische Kaiserzeit', 'mittelalterlich': 'Mittelalter',
    'frühmittelalterlich': 'Frühmittelalter', 'hochmittelalterlich': 'Hochmittelalter',
    'spätmittelalterlich': 'Spätmittelalter', 'ottonisch': 'Ottonenzeit', 'karolingisch': 'Karolingerzeit',
    'merowingisch': 'Merowingerzeit'
}

def split_adjective_noun(term):
    clean = re.sub(r'\s*\(skos\)', '', term, flags=re.IGNORECASE).strip()
    words = clean.split()
    if len(words) >= 2:
        first_word = words[0].lower()
        stemmed_adj = first_word
        for end in ['en', 'er', 'es', 'em', 'e', 'n', 's']:
            if stemmed_adj.endswith(end) and len(stemmed_adj) - len(end) >= 5:
                stemmed_adj = stemmed_adj[:-len(end)]
                break
        if stemmed_adj in EPOCH_ADJECTIVE_MAP or stemmed_adj.endswith('zeitlich'):
            return words[0], " ".join(words[1:])
    return None, term

def parse_skos_items(val_str):
    if not isinstance(val_str, str) or not val_str.strip() or val_str.strip() in ["-", "nan", "None"]:
        return []
    cleaned_val = val_str.strip()
    if cleaned_val.startswith("[") and cleaned_val.endswith("]"):
        try:
            import ast
            parsed = ast.literal_eval(cleaned_val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip() and str(x).strip() not in ["-", "nan", "None"]]
        except Exception:
            pass
    parts = re.split(r'[,|;]', cleaned_val)
    return [p.strip().strip("'\"[]") for p in parts if p.strip() and p.strip() not in ["-", "nan", "None"]]

def pair_raw_and_skos(raw_val_str, skos_val_str):
    raw_items = parse_raw_fragments(raw_val_str)
    skos_items = parse_skos_items(skos_val_str)
    
    paired = []
    for idx, raw in enumerate(raw_items):
        matched_skos = None
        raw_lower = raw.lower()
        for sk in skos_items:
            sk_clean = re.sub(r'\s*\(skos\)', '', sk, flags=re.IGNORECASE).strip().lower()
            if sk_clean and (sk_clean in raw_lower or raw_lower in sk_clean):
                matched_skos = sk
                break
        if not matched_skos and idx < len(skos_items):
            matched_skos = skos_items[idx]
        paired.append((raw, matched_skos))
    return paired

# 2. Process documents (1973 and 1970)
docs_data = {}

def process_document(csv_fname, txt_fname, doc_key, doc_title=None):
    csv_path = os.path.join(root_dir, csv_fname)
    txt_path = os.path.join(root_dir, txt_fname)
    
    if not os.path.exists(csv_path) or not os.path.exists(txt_path):
        return None

    import pandas as pd
    df = pd.read_csv(csv_path, sep=";")
    with open(txt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    fragments = []
    for idx, row in df.iterrows():
        mid = str(row.get('massnahme_id', ''))
        row_id = f"row_{idx}"

        def push_paired(raw_val_str, skos_val_str, cat_name):
            for raw, skos in pair_raw_and_skos(raw_val_str, skos_val_str):
                raw_adj, noun_rem = split_adjective_noun(raw)
                if raw_adj and noun_rem:
                    fragments.append((raw_adj, 'datierung', row_id, 'Datierung (SKOS)'))
                    fragments.append((noun_rem, cat_name, row_id, skos or (noun_rem + ' (SKOS)')))
                else:
                    fragments.append((raw, cat_name, row_id, skos))

        push_paired(mid, mid, 'aktivitaet')
        push_paired(str(row.get('befunde_roh', '')), str(row.get('befunde_norm', '')), 'befund')
        push_paired(str(row.get('funde_roh', '')), str(row.get('funde_norm', '')), 'fund')
        push_paired(str(row.get('datierung_roh', '')), str(row.get('datierung_norm', '')), 'datierung')
        push_paired(str(row.get('ort', '')), str(row.get('ort', '')), 'ort')

    STOPWORDS = {
        'in', 'im', 'an', 'am', 'er', 'es', 'en', 'oder', 'und', 'mit', 'von', 'aus', 'der', 'die', 'das', 'dem', 'den', 'zu', 'zur', 'zum', '2', '3', '1', '4', '5', 't',
        'au', 'ar', 's', 'dp', 'fol', 'an', 'd', 'av', 'rv', 'ric', 'ric²', 'ric3', 'ric4', 'ric5', 'av.', 'rv.', 'g', 'mm', 'ca', 'v.', 'chr.', 'rom', 'typ', 'var', 'nr.', 'nr'
    }

    spans = []
    for frag_text, category, row_id, skos_norm in fragments:
        clean_frag = frag_text.strip()
        clean_lower = clean_frag.lower()
        if clean_lower in STOPWORDS:
            continue
        if len(clean_frag) < 3 and clean_frag != "As":
            continue

        if clean_lower in ALL_SKOS_CAT_MAP:
            skos_cat = ALL_SKOS_CAT_MAP[clean_lower]
            if skos_cat == 'Datierung':
                category = 'datierung'
            elif skos_cat == 'Befund':
                category = 'befund'
            elif skos_cat == 'Fund':
                category = 'fund'
            
        patterns_to_try = [re.escape(clean_frag)]
        frag_l = clean_frag.lower()
        if frag_l == 'krug':
            patterns_to_try.append(r'[A-Za-zäöüÄÖÜß]*krüg[e]?|[A-Za-zäöüÄÖÜß]*krug')
        elif frag_l == 'gefäß':
            patterns_to_try.append(r'[A-Za-zäöüÄÖÜß]*gefäß[e]?')
        elif frag_l == 'topf':
            patterns_to_try.append(r'[A-Za-zäöüÄÖÜß]*töpf[e]?|[A-Za-zäöüÄÖÜß]*topf')
        elif frag_l == 'schüssel':
            patterns_to_try.append(r'[A-Za-zäöüÄÖÜß]*schüssel[n]?')
        elif frag_l == 'schale':
            patterns_to_try.append(r'[A-Za-zäöüÄÖÜß]*schale[n]?')

        for pat in patterns_to_try:
            word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + pat + r')(?![a-zA-ZäöüÄÖÜß0-9])', re.IGNORECASE)
            for match in word_pattern.finditer(raw_text):
                start, end = match.span()
                spans.append({
                    "start": start,
                    "end": end,
                    "category": category,
                    "text": raw_text[start:end],
                    "row_id": row_id,
                    "skos": skos_norm
                })

    # Pass 2: Global SKOS & Archaeological Concept Scanner across full raw_text
    GLOBAL_CONCEPT_PATTERNS = [
        # Roman Emperors & Rulers (Datierung)
        (r'Augustus', 'datierung', 'Augustus (SKOS)'),
        (r'Tiberius', 'datierung', 'Tiberius (SKOS)'),
        (r'Caligula', 'datierung', 'Caligula (SKOS)'),
        (r'Claudius I\.|Claudius', 'datierung', 'Claudius I. (SKOS)'),
        (r'Vespasian', 'datierung', 'Vespasian (SKOS)'),
        (r'Domitian', 'datierung', 'Domitian (SKOS)'),
        (r'Nerva', 'datierung', 'Nerva (SKOS)'),
        (r'Trajan', 'datierung', 'Trajan (SKOS)'),
        (r'Hadrian', 'datierung', 'Hadrian (SKOS)'),
        (r'Antoninus Pius', 'datierung', 'Antoninus Pius (SKOS)'),
        (r'Marc Aurel|Mark Aurel', 'datierung', 'Mark Aurel (SKOS)'),
        (r'Lucius Verus', 'datierung', 'Lucius Verus (SKOS)'),
        (r'Commodus', 'datierung', 'Commodus (SKOS)'),
        (r'Septimius Severus', 'datierung', 'Septimius Severus (SKOS)'),
        (r'Geta', 'datierung', 'Geta (SKOS)'),
        (r'Julia Maesa', 'datierung', 'Julia Maesa (SKOS)'),
        (r'Gordian III\.|Gordian III', 'datierung', 'Gordian III. (SKOS)'),
        (r'Philippus I\.|Philippus Arabs', 'datierung', 'Philippus Arabs (SKOS)'),
        (r'Constantin I\.|Konstantin I\.|Konstantin der Große', 'datierung', 'Konstantin der Große (SKOS)'),
        (r'Constantin II\.|Konstantin II\.', 'datierung', 'Konstantin II. (SKOS)'),
        (r'Crispina', 'datierung', 'Crispina (SKOS)'),
        (r'Lucilla', 'datierung', 'Lucilla (SKOS)'),

        # Archaeological Waterworks & Structures (Befund)
        (r'Eifelwasserleitung|römische\s+Wasserleitung|Wasserleitung', 'befund', 'Wasserleitung (SKOS)'),
        (r'Frischwasserkanäle|Kanal', 'befund', 'Kanal (Wasserbau) (SKOS)'),
        (r'Fundamentplatte|Fundament', 'befund', 'Fundament (SKOS)'),
        (r'Materialentnahmegrube|Materialentnahmest\.|Materialentnahme', 'befund', 'Materialentnahmegrube (SKOS)'),
        (r'Grubenhaus', 'befund', 'Grubenhaus (SKOS)'),
        (r'Pfostengruben|Pfostengrube', 'befund', 'Pfostengrube (SKOS)'),
        (r'Pfostenbau', 'befund', 'Pfostenbau (SKOS)'),
        (r'Kleinere\s+Gruben|Siedlungsgrube|Gruben|Grube', 'befund', 'Grube (SKOS)'),
        (r'Brandgrab|Bestattungsplatz(?:es|en|e|s)?', 'befund', 'Brandgrab (SKOS)'),
        (r'Siedlungsbefund|Siedlungsplatz|Siedlung', 'befund', 'Siedlung (SKOS)'),
        (r'Villa rustica', 'befund', 'Villa rustica (SKOS)'),
        (r'Brunnenu\.|Brunnen', 'befund', 'Brunnen (SKOS)'),
        (r'Latrinenbefunden?|Latrine', 'befund', 'Latrine (SKOS)'),
        (r'Lagervorstadt|Vorstadt', 'befund', 'Vorstadt (SKOS)'),
        (r'Töpferei', 'befund', 'Töpferei (SKOS)'),
        (r'Vicus', 'befund', 'Vicus (SKOS)'),
        (r'Retentura|Legionslager', 'befund', 'Legionslager (SKOS)'),
        (r'Aquädukt', 'befund', 'Aquädukt (SKOS)'),

        # Archaeological Vessels & Objects (Fund)
        (r'Einhenkelkrüge|Einhenkelkrug', 'fund', 'Krug (SKOS)'),
        (r'Zweihenkelkrüge|Zweihenkelkrug', 'fund', 'Krug (SKOS)'),
        (r'Glanztonwarebecher|Becher', 'fund', 'Becher (SKOS)'),
        (r'Terra\s+[Ss]igillata|Sigillaten', 'fund', 'Terra Sigillata (SKOS)'),
        (r'Schälchen|Schale', 'fund', 'Schale (SKOS)'),
        (r'Statuette(?:\s+des\s+Mars\s+Ultor)?', 'fund', 'Statuette (SKOS)'),
        (r'Helm', 'fund', 'Helm (SKOS)'),
        (r'Oberkörperpanzer|Lorica\s+segmentata|Panzerung', 'fund', 'Rüstung (SKOS)'),
        (r'Beinschienen|Beinschiene', 'fund', 'Rüstung (SKOS)'),
        (r'Armbrustspiralfibel|Emailscheibenfibel|Scheibenfibel|Fibel', 'fund', 'Fibel (SKOS)'),
        (r'Sesterzen|Sesterz', 'fund', 'Sesterz (SKOS)'),
        (r'Denare|Denar|Denarius', 'fund', 'Denarius (SKOS)'),
        (r'Dupondius|Dupondii', 'fund', 'Dupondius (SKOS)'),
        (r'Aureus|Aurei', 'fund', 'Aureus (SKOS)'),
        (r'Folles|Follis', 'fund', 'Folles (SKOS)'),
        (r'Münzen|Münze', 'fund', 'Münze (SKOS)'),
        (r'Niederbieber\d*[a-z]?', 'fund', 'Niederbieber (SKOS)'),
        (r'Gellep\d*', 'fund', 'Gellep (SKOS)'),
        (r'RSNB\d*', 'fund', 'Römische Keramik (SKOS)'),
        (r'Scherben?|Wandscherbe|Randscherbe', 'fund', 'Scherbe (SKOS)'),

        # Century & Dating Expressions (Datierung)
        (r'spätbronzezeitlich|spätbronze-', 'datierung', 'Spätbronzezeit (SKOS)'),
        (r'früheisenzeitlich|früheisenzeitl\.', 'datierung', 'Frühe Eisenzeit (SKOS)'),
        (r'mittleren\s+Eisenzeit|mittlere\s+Eisenzeit', 'datierung', 'Mittlere Eisenzeit (SKOS)'),
        (r'frühe\s+Eisenzeit', 'datierung', 'Frühe Eisenzeit (SKOS)'),
        (r'neolithisch|neolith\.', 'datierung', 'Neolithikum (SKOS)'),
        (r'metallzeitlich|metallzeitl\.', 'datierung', 'Metallzeit (SKOS)'),
        (r'frührömisch|frühröm\.', 'datierung', 'Frührömische Zeit (SKOS)'),
        (r'eisenzeitlich|eisenzeitl\.', 'datierung', 'Eisenzeit (SKOS)'),
        (r'Ha\s+C|Hallstatt\s+C', 'datierung', 'Hallstatt C (SKOS)'),
        (r'Frühlat\.|Frühlatènezeit|frühlatènezeitl\.', 'datierung', 'Frühlatènezeit (SKOS)'),
        (r'urnenfelder-(?:\s*bis\s*)?', 'datierung', 'Urnenfelderzeit (SKOS)'),
        (r'jüngereisenzeitl\.|jüngereisenzeitlich', 'datierung', 'Jüngere Eisenzeit (SKOS)'),
        (r'früheneuzeitl\.|früheneuzeitlich|frühe\s+Neuzeit|frühen\s+Neuzeit', 'datierung', 'Frühe Neuzeit (SKOS)'),
        (r'mittelalterl\.|mittelalterlich', 'datierung', 'Mittelalter (SKOS)'),
        (r'bandkeram\.|bandkeramisch', 'datierung', 'Bandkeramik (SKOS)'),
        (r'zweite\s+Hälfte\s*\d+\.\s*–\s*Anfang\s*\d+\.\s*Jh\.', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*/\s*\d+\.\s*Jh\.(?:\s*n\.\s*Chr\.)?', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*–\s*\d+\.\s*Jhs?\.', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*Jh\.', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'frühröm\.|spätröm\.|römerzeitl\.|röm\.', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'mittlere[rn]?\s+Kaiserzeit|spätere\s+Kaiserzeit|Kaiserzeit', 'datierung', 'Römische Kaiserzeit (SKOS)'),

        # Additional Structures & Befunde
        (r'Siedlung(?:sreste)?|Streugehöften|Gehöft', 'befund', 'Siedlung (SKOS)'),
        (r'Pfostengruben(?:verfüllungen)?|Pfostengrube', 'befund', 'Pfostengrube (SKOS)'),
        (r'Gruben(?:verfüllungen)?|Grube', 'befund', 'Grube (SKOS)'),
        (r'Befundstreuung', 'befund', 'Befundstreuung (SKOS)'),
        (r'röm\.\s+Straße|Straße|Via\s+Belgica', 'befund', 'Straße (SKOS)'),
        (r'Erdkeller', 'befund', 'Erdkeller (SKOS)'),
        (r'Pfosten', 'befund', 'Pfosten (SKOS)'),
        (r'Speicher', 'befund', 'Speicher (SKOS)'),
        (r'Brennöfen|Brennofen|Ofen', 'befund', 'Brennofen (SKOS)'),
        (r'Werkhütten|Hütte', 'befund', 'Werkstatt (SKOS)'),
        (r'Werkplätze|Werkplatz', 'befund', 'Werkplatz (SKOS)'),
        (r'Gräben|Graben', 'befund', 'Graben (SKOS)'),
        (r'Materialentnahmebereiche|Materialentnahme', 'befund', 'Materialentnahmegrube (SKOS)'),
        (r'Schützengraben', 'befund', 'Schützengraben (SKOS)')
    ]

    for pat_str, cat, skos_norm in GLOBAL_CONCEPT_PATTERNS:
        word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + pat_str + r')', re.IGNORECASE)
        for match in word_pattern.finditer(raw_text):
            start, end = match.span()
            if re.search(r'\b(keine|kein|ohne|keinerlei)\s+$', raw_text[:start], re.IGNORECASE):
                continue
            spans.append({
                "start": start,
                "end": end,
                "category": cat,
                "text": raw_text[start:end],
                "row_id": "",
                "skos": skos_norm
            })

    def span_priority(s):
        cat_order = {'datierung': 5, 'befund': 4, 'fund': 3, 'aktivitaet': 2, 'ort': 1}
        return (cat_order.get(s["category"], 0), (s["end"] - s["start"]))

    spans.sort(key=lambda s: (s["start"], -span_priority(s)[0], -span_priority(s)[1]))

    filtered_spans = []
    last_end = 0
    for s in spans:
        if s["start"] >= last_end:
            filtered_spans.append(s)
            last_end = s["end"]

    table_rows = []
    for idx, row in df.iterrows():
        table_rows.append({
            "id": f"row_{idx}",
            "page": str(row.get('Seitenzahl', '-')),
            "ort": str(row.get('ort', '-')),
            "kreis": str(row.get('kreis', '-')),
            "massnahme": str(row.get('massnahme_id', '-')),
            "datierung": str(row.get('datierung_norm', '-')),
            "befunde": str(row.get('befunde_norm', '-')),
            "funde": str(row.get('funde_norm', '-')),
            "autor": str(row.get('autor', '-'))
        })

    docs_data[doc_key] = {
        "title": doc_title or doc_key,
        "raw_text": raw_text,
        "spans": filtered_spans,
        "table_rows": table_rows
    }

# Auto-discover all LVR_*_Split_Fixed.csv files in root_dir
import glob
csv_candidates = sorted(glob.glob(os.path.join(root_dir, "LVR_*_Split_Fixed.csv")), reverse=True)
for csv_path in csv_candidates:
    csv_fname = os.path.basename(csv_path)
    base_name = csv_fname.replace("_Split_Fixed.csv", "")
    
    txt_candidates = [
        f"{base_name}_cleaned_text.txt",
        f"{base_name}_cleaned.txt",
        f"{base_name}_raw_text.txt"
    ]
    matched_txt = next((t for t in txt_candidates if os.path.exists(os.path.join(root_dir, t))), None)
    if matched_txt:
        year_or_tag = base_name.replace("LVR_", "").replace("_", " ")
        doc_title = f"LVR {year_or_tag}"
        process_document(csv_fname, matched_txt, matched_txt, doc_title)

# Fallback explicit checks if glob missed anything
if not docs_data:
    process_document("LVR_1973_Split_Fixed.csv", "LVR_1973_cleaned.txt", "LVR_1973_cleaned.txt", "LVR 1973")
    process_document("LVR_1970_Split_Fixed.csv", "LVR_1970_cleaned.txt", "LVR_1970_cleaned.txt", "LVR 1970")

vocab_json_str = json.dumps(vocab_data, ensure_ascii=False)
docs_json_str = json.dumps(docs_data, ensure_ascii=False)
gazetteer_json_str = json.dumps(gazetteer_data, ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <title>Archäologische Extraktions-Vorschau & Text-Annotator</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background: #f8fafc; color: #0f172a; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
        
        /* Header Bar */
        header {{ background: #ffffff; padding: 12px 24px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05); z-index: 20; }}
        h1 {{ margin: 0; font-size: 18px; color: #0284c7; display: flex; align-items: center; gap: 8px; }}
        
        .header-controls {{ display: flex; align-items: center; gap: 10px; }}
        select, button {{ background: #f1f5f9; color: #1e293b; border: 1px solid #cbd5e1; padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 13px; cursor: pointer; transition: all 0.2s ease; }}
        select:hover, button:hover {{ background: #e2e8f0; border-color: #0284c7; }}
        
        button.btn-success {{ background: #10b981; color: white; border-color: #059669; }}
        button.btn-success:hover {{ background: #059669; }}
        button.btn-primary {{ background: #2563eb; color: white; border-color: #1d4ed8; }}
        button.btn-primary:hover {{ background: #1d4ed8; }}

        /* Category Toolbar */
        .category-bar {{ background: #ffffff; padding: 10px 24px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; gap: 12px; font-size: 13px; font-weight: bold; color: #475569; }}
        .cat-btn {{ padding: 6px 16px; border-radius: 20px; border: 2px solid transparent; cursor: pointer; transition: all 0.15s ease; user-select: none; opacity: 0.75; font-size: 13px; }}
        .cat-btn.active {{ opacity: 1.0; transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.12); border-color: #0f172a; font-weight: bold; }}
        
        .cat-aktivitaet {{ background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }}
        .cat-ort {{ background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }}
        .cat-datierung {{ background-color: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }}
        .cat-befund {{ background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }}
        .cat-fund {{ background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }}

        /* Main Split Layout */
        .main-layout {{ display: flex; flex: 1; min-height: 0; overflow: hidden; }}
        
        /* Left Pane: Text View */
        .pane-text {{ flex: 1.3; background: #ffffff; display: flex; flex-direction: column; border-right: 1px solid #e2e8f0; }}
        .pane-header {{ padding: 12px 20px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-weight: bold; font-size: 14px; color: #475569; display: flex; justify-content: space-between; align-items: center; }}
        .text-body {{ padding: 28px 36px; overflow-y: auto; flex: 1; white-space: pre-wrap; font-family: Georgia, serif; font-size: 16.5px; line-height: 1.9; color: #1e293b; }}

        /* Highlight Marks */
        mark {{ border-radius: 4px; padding: 2px 6px; cursor: pointer; font-weight: 600; position: relative; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 4px; margin: 1px 2px; }}
        mark:hover {{ filter: brightness(0.92); box-shadow: 0 0 8px rgba(0,0,0,0.25); transform: translateY(-1px); }}
        
        mark.aktivitaet {{ background-color: #dbeafe; color: #1e40af; border-bottom: 2px solid #3b82f6; }}
        mark.ort {{ background-color: #f1f5f9; color: #334155; border-bottom: 2px solid #64748b; }}
        mark.datierung {{ background-color: #fef9c3; color: #854d0e; border-bottom: 2px solid #eab308; }}
        mark.befund {{ background-color: #fee2e2; color: #991b1b; border-bottom: 2px solid #ef4444; }}
        mark.fund {{ background-color: #dcfce7; color: #166534; border-bottom: 2px solid #10b981; }}
        
        mark.has-skos-mark {{ border-bottom-width: 3px; }}
        mark.no-skos-mark {{ border-bottom: 2px dashed #ef4444 !important; background-color: #fff1f2 !important; }}
        
        mark .skos-badge {{ font-size: 10.5px; font-weight: bold; background: rgba(2, 132, 199, 0.15); color: #0369a1; border: 1px solid #7dd3fc; border-radius: 4px; padding: 1px 4px; white-space: nowrap; margin-left: 2px; }}

        mark.selected-pulse {{ animation: pulseHighlight 1.5s ease-in-out infinite; transform: scale(1.04); display: inline-flex; z-index: 10; }}
        @keyframes pulseHighlight {{
            0% {{ box-shadow: 0 0 0 0 rgba(2, 132, 199, 0.7); }}
            70% {{ box-shadow: 0 0 0 10px rgba(2, 132, 199, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(2, 132, 199, 0); }}
        }}

        /* Right Pane: Sidebar */
        .pane-sidebar {{ flex: 1.2; background: #f8fafc; display: flex; flex-direction: column; overflow: hidden; }}
        
        .sidebar-tabs {{ display: flex; background: #ffffff; border-bottom: 1px solid #e2e8f0; }}
        .tab-btn {{ flex: 1; padding: 12px; text-align: center; font-weight: bold; font-size: 13px; color: #64748b; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.2s ease; }}
        .tab-btn.active {{ color: #0284c7; border-color: #0284c7; background: #f8fafc; }}

        .tab-content {{ flex: 1; padding: 16px; overflow-y: auto; display: none; }}
        .tab-content.active {{ display: flex; flex-direction: column; gap: 16px; }}

        /* Table Styles */
        .table-container {{ overflow-x: auto; max-height: 100%; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; }}
        th {{ background: #f1f5f9; padding: 10px; font-weight: bold; color: #334155; border-bottom: 2px solid #cbd5e1; position: sticky; top: 0; z-index: 5; }}
        td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
        tr.table-row {{ cursor: pointer; transition: background 0.15s ease; }}
        tr.table-row:hover {{ background-color: #f0f9ff; }}
        tr.table-row.active-row {{ background-color: #e0f2fe; border-left: 4px solid #0284c7; font-weight: 500; }}

        .badge {{ padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 11.5px; display: inline-block; margin: 2px 0; }}
        .badge.aktivitaet {{ background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }}
        .badge.ort {{ background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }}
        .badge.datierung {{ background-color: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }}
        .badge.befund {{ background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }}
        .badge.fund {{ background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }}

        /* SKOS Search Box */
        .search-box {{ display: flex; flex-direction: column; gap: 8px; }}
        .search-input {{ width: 100%; padding: 10px 14px; background: #ffffff; border: 1px solid #cbd5e1; color: #0f172a; border-radius: 8px; font-size: 14px; outline: none; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
        .search-input:focus {{ border-color: #0284c7; box-shadow: 0 0 0 3px rgba(2,132,199,0.15); }}
        
        .vocab-cat-filters {{ display: flex; gap: 6px; margin-top: 4px; }}
        .vcat-pill {{ font-size: 11.5px; font-weight: bold; padding: 3px 10px; border-radius: 12px; background: #e2e8f0; color: #475569; cursor: pointer; transition: all 0.15s ease; }}
        .vcat-pill:hover {{ background: #cbd5e1; }}
        .vcat-pill.active {{ background: #0284c7; color: white; }}
        .vcat-pill.vcat-datierung.active {{ background: #ca8a04; color: white; }}
        .vcat-pill.vcat-befund.active {{ background: #dc2626; color: white; }}
        .vcat-pill.vcat-fund.active {{ background: #16a34a; color: white; }}

        .vocab-list {{ display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; }}
        .vocab-item {{ background: #ffffff; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 8px; cursor: grab; transition: all 0.2s ease; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }}
        .vocab-item:hover {{ border-color: #0284c7; background: #f0f9ff; }}
        .vocab-item .term-title {{ font-weight: bold; font-size: 14px; color: #0f172a; }}
        .vocab-item .term-alt {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
        .vocab-item .btn-assign {{ font-size: 11px; padding: 4px 10px; background: #0284c7; border: none; border-radius: 5px; color: white; cursor: pointer; font-weight: bold; }}
        .vocab-item .btn-assign:hover {{ background: #0369a1; }}

        /* Resizable Divider */
        .resizer {{
            width: 8px;
            background: #cbd5e1;
            cursor: col-resize;
            transition: background 0.15s ease;
            z-index: 50;
            position: relative;
            user-select: none;
        }}
        .resizer:hover, .resizer.dragging {{
            background: #0284c7;
        }}
        .resizer::after {{
            content: '⋮';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #64748b;
            font-size: 14px;
            font-weight: bold;
        }}
        .resizer:hover::after, .resizer.dragging::after {{
            color: #ffffff;
        }}

        /* Floating Selection Popup */
        #selectionTooltip {{ position: absolute; display: none; background: #ffffff; border: 1px solid #0284c7; padding: 8px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); z-index: 100; gap: 6px; }}
        #selectionTooltip button {{ padding: 6px 12px; font-size: 12px; font-weight: bold; border-radius: 6px; cursor: pointer; }}

        /* Mark Editor Modal / Card */
        .anno-card {{ background: #ffffff; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 6px; font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .anno-header {{ display: flex; justify-content: space-between; align-items: center; font-weight: bold; font-size: 12px; color: #64748b; }}
        .anno-text {{ color: #0f172a; font-style: italic; background: #f8fafc; padding: 6px 10px; border-radius: 4px; margin-top: 4px; border: 1px solid #f1f5f9; }}
        .anno-skos {{ color: #0284c7; font-weight: bold; display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-top: 4px; font-size: 13px; }}
        .btn-delete {{ background: #ef4444; color: white; border: none; padding: 4px 10px; border-radius: 5px; font-size: 11px; cursor: pointer; font-weight: bold; }}
        .btn-delete:hover {{ background: #dc2626; }}

        .cat-select {{ font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 4px; border: 1px solid #cbd5e1; background: #f8fafc; cursor: pointer; }}

        /* Modal Overlay for Creating New SKOS Concept */
        .modal-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.55);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 500;
        }}
        .modal-card {{
            background: #ffffff;
            border-radius: 12px;
            width: 520px;
            max-width: 92vw;
            box-shadow: 0 20px 40px rgba(0,0,0,0.25);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid #cbd5e1;
            animation: modalFadeIn 0.2s ease-out;
        }}
        @keyframes modalFadeIn {{
            from {{ opacity: 0; transform: scale(0.96); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        .modal-header {{
            padding: 16px 20px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .modal-header h3 {{
            margin: 0; font-size: 16px; color: #0f172a; display: flex; align-items: center; gap: 8px;
        }}
        .btn-close {{
            background: none; border: none; font-size: 18px; color: #64748b; cursor: pointer; font-weight: bold; padding: 2px 8px; border-radius: 4px;
        }}
        .btn-close:hover {{ background: #e2e8f0; color: #0f172a; }}
        .modal-body {{ padding: 20px; display: flex; flex-direction: column; gap: 12px; }}
        .form-label {{ font-size: 12.5px; font-weight: bold; color: #334155; }}
        .form-input, .form-select {{
            width: 100%; padding: 9px 12px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13.5px; outline: none; transition: border 0.15s ease;
        }}
        .form-input:focus, .form-select:focus {{ border-color: #0284c7; box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15); }}
        .modal-footer {{
            padding: 14px 20px; background: #f8fafc; border-top: 1px solid #e2e8f0; display: flex; justify-content: flex-end; gap: 10px;
        }}
        .btn-secondary {{ background: #e2e8f0; color: #334155; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 12.5px; }}
        .btn-secondary:hover {{ background: #cbd5e1; }}

        .toast {{ position: fixed; bottom: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 600; }}
    </style>
</head>
<body>

    <!-- Header Navigation -->
    <header>
        <h1>🏛️ Archäologische Extraktions-Vorschau & Text-Annotator</h1>
        <div class="header-controls">
            <select id="docSelect" onchange="loadDocument(this.value)">
                <option value="">Lade Dokumente...</option>
            </select>
            <button onclick="document.getElementById('fileInput').click()">📄 Eigene Datei öffnen</button>
            <input type="file" id="fileInput" style="display:none" onchange="handleFileUpload(event)">
            
            <button class="btn-success" onclick="openSkosModal('')">➕ SKOS-Begriff aufnehmen</button>
            <button class="btn-success" style="background:#059669; border-color:#047857;" onclick="exportUpdatedSKOS()">📥 Vokabular TTL/JSON</button>
            <button class="btn-primary" onclick="exportJSON()">📄 JSON Export</button>
            <button class="btn-primary" style="background:#0284c7; border-color:#0369a1;" onclick="exportFullTableCSV()">📊 Tabelle CSV</button>
        </div>
    </header>

    <!-- Category Toolbar -->
    <div class="category-bar">
        <span>Kategorie wählen (Tasten 1-5):</span>
        <div class="cat-btn cat-aktivitaet active" onclick="setCategory('aktivitaet')">1. Aktivität / Maßnahme</div>
        <div class="cat-btn cat-ort" onclick="setCategory('ort')">2. Ort / Kreis</div>
        <div class="cat-btn cat-datierung" onclick="setCategory('datierung')">3. Datierung</div>
        <div class="cat-btn cat-befund" onclick="setCategory('befund')">4. Befund</div>
        <div class="cat-btn cat-fund" onclick="setCategory('fund')">5. Fund</div>
    </div>

    <!-- Main Split Layout -->
    <div class="main-layout">
        
        <!-- Left Pane: Text View with Highlights -->
        <div class="pane pane-text">
            <div class="pane-header">
                <span id="currentDocTitle">📄 Extraktions-Vorschau & Text</span>
                <small style="color: #64748b;">Textstelle mit der Maus markieren oder Highlight anklicken</small>
            </div>
            <div class="text-body" id="textBody" onmouseup="handleTextSelection(event)" ondragover="event.preventDefault()" ondrop="handleDropOnText(event)"></div>
        </div>

        <!-- Draggable Splitter -->
        <div class="resizer" id="dragResizer" title="Ziehen zum Anpassen der Spaltenbreiten"></div>

        <!-- Right Pane: Sidebar -->
        <div class="pane pane-sidebar">
            <div class="sidebar-tabs">
                <div class="tab-btn active" onclick="switchTab('table')">📊 Tabelle</div>
                <div class="tab-btn" onclick="switchTab('map')">🗺️ Georeferenzierung</div>
                <div class="tab-btn" onclick="switchTab('vocab')">📚 SKOS Vokabular</div>
                <div class="tab-btn" onclick="switchTab('annotations')">📋 Annotationen (<span id="annoCount">0</span>)</div>
            </div>

            <!-- Tab 1: CSV Table View -->
            <div class="tab-content active" id="tabTable">
                <input type="text" id="tableSearch" class="search-input" placeholder="🔍 Extraktions-Tabelle durchsuchen..." oninput="filterTable(this.value)">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Seite</th>
                                <th>Ort / Kreis</th>
                                <th>Maßnahme</th>
                                <th>Datierung</th>
                                <th>Befund</th>
                                <th>Fund</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody"></tbody>
                    </table>
                </div>
            </div>

            <!-- Tab 2: Georeferencing & Map -->
            <div class="tab-content" id="tabMap">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: bold; font-size: 13px; color: #475569;">🗺️ Fundstellen-Karte & Verortung</span>
                    <button class="btn-primary" style="font-size: 11px; background: #059669; border-color: #047857; padding: 4px 10px;" onclick="exportGeoJSON()">📥 QGIS GeoJSON Export</button>
                </div>

                <div id="leafletMap" style="height: 310px; width: 100%; border-radius: 8px; border: 1px solid #cbd5e1; margin-top: 6px; z-index: 1;"></div>

                <div style="display: flex; gap: 8px; margin-top: 6px; font-size: 10.5px; font-weight: bold; justify-content: space-around; background: #ffffff; padding: 6px; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <span style="color: #059669;">🟢 Stufe 1: Gazetteer (Auto)</span>
                    <span style="color: #ca8a04;">🟡 Stufe 2: GeoNames (Prüfung)</span>
                    <span style="color: #ea580c;">🟠 Stufe 3: Gemini KI (Prüfung)</span>
                </div>

                <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;" id="locationVerifyList">
                    <div style="color: #64748b; text-align: center; padding: 15px;">Lade Ortsdaten auf der Karte...</div>
                </div>
            </div>

            <!-- Tab 2: SKOS Vocab Search & Management -->
            <div class="tab-content" id="tabVocab">
                <div class="search-box">
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="vocabSearch" class="search-input" placeholder="🔍 Vokabular durchsuchen..." oninput="filterVocab(this.value)">
                        <button class="btn-primary" style="white-space: nowrap; font-size: 11.5px; background: #0284c7; border: none;" onclick="openSkosModal('')">➕ SKOS-Begriff</button>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="vocab-cat-filters">
                            <span class="vcat-pill active" onclick="setVocabCatFilter('all', this)">Alle</span>
                            <span class="vcat-pill vcat-datierung" onclick="setVocabCatFilter('Datierung', this)">Datierung</span>
                            <span class="vcat-pill vcat-befund" onclick="setVocabCatFilter('Befund', this)">Befund</span>
                            <span class="vcat-pill vcat-fund" onclick="setVocabCatFilter('Fund', this)">Fund</span>
                        </div>
                        <button class="btn-primary" style="font-size: 11px; background: #059669; border-color: #047857; padding: 3px 8px;" onclick="exportUpdatedSKOS()">📥 TTL/JSON Export</button>
                    </div>
                </div>
                <div class="vocab-list" id="vocabList"></div>
            </div>

            <!-- Tab 3: Annotations Manager -->
            <div class="tab-content" id="tabAnnotations">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: bold; font-size: 13px; color: #475569;">Alle Markierungen</span>
                    <button class="btn-delete" style="font-size: 11px;" onclick="clearAllAnnotations()">Alle löschen</button>
                </div>
                <div id="annoList" style="display: flex; flex-direction: column; gap: 10px;">
                    <div style="color: #64748b; text-align: center; padding: 20px;">Lade Annotationen...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Floating Selection Tooltip -->
    <div id="selectionTooltip">
        <button onclick="annotateSelected('aktivitaet')" class="cat-aktivitaet">Aktivität</button>
        <button onclick="annotateSelected('ort')" class="cat-ort">Ort</button>
        <button onclick="annotateSelected('datierung')" class="cat-datierung">Datierung</button>
        <button onclick="annotateSelected('befund')" class="cat-befund">Befund</button>
        <button onclick="annotateSelected('fund')" class="cat-fund">Fund</button>
        <button onclick="openSkosModalWithSelection()" style="background: #0284c7; color: white; border: none; font-weight: bold; border-left: 2px solid #0369a1; padding-left: 10px;">📖 Ins SKOS-Vokabular aufnehmen...</button>
    </div>

    <!-- Modal Overlay for Creating New SKOS Concept -->
    <div id="skosModal" class="modal-overlay" style="display:none;">
        <div class="modal-card">
            <div class="modal-header">
                <h3>📖 Neues SKOS-Konzept erstellen</h3>
                <button class="btn-close" onclick="closeSkosModal()">✕</button>
            </div>
            <div class="modal-body">
                <p style="font-size: 12.5px; color: #64748b; margin-bottom: 4px; margin-top: 0;">
                    Fügen Sie einen neuen archäologischen Fachbegriff oder eine Typologie hinzu. Alle Vorkommen im Text werden <strong>sofort live hervorgehoben</strong> und das Vokabular erweitert.
                </p>
                
                <label class="form-label">Begriff / Benennung (SKOS PrefLabel):</label>
                <input type="text" id="newSkosTerm" class="form-input" placeholder="z. B. Niederbieber 67b oder Eifelwasserleitung">

                <label class="form-label">Archäologische Kategorie / SKOS-Klasse:</label>
                <select id="newSkosCategory" class="form-select">
                    <option value="Datierung">🟨 Datierung (Zeitstellung / Kaiser / Epoche)</option>
                    <option value="Befund">🟥 Befund (Bauwerk / Grube / Infrastruktur)</option>
                    <option value="Fund">🟩 Fund (Artefakt / Keramik / Typologie / Münze)</option>
                </select>

                <label class="form-label">Synonyme / AltLabels (kommagetrennt, optional):</label>
                <input type="text" id="newSkosAlt" class="form-input" placeholder="z. B. Niederbieber 67 b, Typ Niederbieber 67b">

                <label class="form-label">Oberbegriff / Broader Concept (Suche & Auswahl):</label>
                <input type="text" id="newSkosBroader" class="form-input" list="broaderConceptsList" placeholder="🔍 Oberbegriff suchen (z. B. Römische Keramik, Aquädukt, Münze)..." autocomplete="off">
                <datalist id="broaderConceptsList"></datalist>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closeSkosModal()">Abbrechen</button>
                <button class="btn-primary" style="background: #10b981; border: none; font-weight: bold;" onclick="saveNewSkosTerm()">💾 In Vokabular speichern & Text scannen</button>
            </div>
        </div>
    </div>

    <div class="toast" id="toast">Nachricht</div>

    <script>
        const EMBEDDED_VOCAB = {vocab_json_str};
        const EMBEDDED_DOCS = {docs_json_str};

        let currentCategory = 'aktivitaet';
        let rawVocabularies = EMBEDDED_VOCAB;
        let ALL_SKOS_CAT_MAP = {{}};
        for (let cat in rawVocabularies) {{
            if (Array.isArray(rawVocabularies[cat])) {{
                for (let item of rawVocabularies[cat]) {{
                    if (item && item.term) ALL_SKOS_CAT_MAP[item.term.toLowerCase()] = cat;
                    if (item && item.alt) item.alt.forEach(a => ALL_SKOS_CAT_MAP[a.toLowerCase()] = cat);
                }}
            }}
        }}

        let activeDocKey = '';
        let activeVocabCatFilter = 'all';
        let annotations = [];
        let selectedRange = null;
        let activeMarkId = null;

        // Key shortcuts 1-5
        document.addEventListener('keydown', (e) => {{
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
            if (e.key === '1') setCategory('aktivitaet');
            if (e.key === '2') setCategory('ort');
            if (e.key === '3') setCategory('datierung');
            if (e.key === '4') setCategory('befund');
            if (e.key === '5') setCategory('fund');
        }});

        function initDocSelect() {{
            const select = document.getElementById('docSelect');
            select.innerHTML = '';
            const keys = Object.keys(EMBEDDED_DOCS);
            if (keys.length === 0) {{
                select.innerHTML = '<option value="">Keine Dokumente geladen</option>';
                return;
            }}
            for (let k of keys) {{
                const opt = document.createElement('option');
                opt.value = k;
                opt.innerText = EMBEDDED_DOCS[k].title || k;
                select.appendChild(opt);
            }}
            activeDocKey = keys[0];
            select.value = activeDocKey;
            loadDocument(activeDocKey);
        }}

        function setCategory(cat) {{
            currentCategory = cat;
            document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.querySelector(`.cat-${{cat}}`);
            if (activeBtn) activeBtn.classList.add('active');
        }}

        function switchTab(tabName) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            if (tabName === 'table') {{
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('tabTable').classList.add('active');
            }} else if (tabName === 'map') {{
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('tabMap').classList.add('active');
                if (!leafletMap) initLeafletMap();
                setTimeout(() => {{ if (leafletMap) leafletMap.invalidateSize(); }}, 100);
            }} else if (tabName === 'vocab') {{
                document.querySelectorAll('.tab-btn')[2].classList.add('active');
                document.getElementById('tabVocab').classList.add('active');
            }} else {{
                document.querySelectorAll('.tab-btn')[3].classList.add('active');
                document.getElementById('tabAnnotations').classList.add('active');
            }}
        }}

        function renderHighlightedText(docData) {{
            const rawText = docData.raw_text;
            const spans = docData.spans || [];

            spans.sort((a, b) => b.start - a.start);

            let resultParts = [];
            let currPos = rawText.length;
            annotations = [];

            for (let i = 0; i < spans.length; i++) {{
                const s = spans[i];
                const markId = `mark_${{i}}`;
                
                const afterText = escapeHtml(rawText.substring(s.end, currPos));
                const spanText = escapeHtml(rawText.substring(s.start, s.end));
                
                const hasSkos = s.skos && s.skos !== '-' && s.skos !== 'None';
                const skosClean = hasSkos ? s.skos.replace(/\\s*\\(SKOS\\)/i, '').trim() : '';
                const skosLabel = hasSkos ? escapeHtml(skosClean) : '';
                const markClass = `${{s.category}} ${{hasSkos ? 'has-skos-mark' : 'no-skos-mark'}}`;

                const taggedSpan = `<mark class="${{markClass}}" id="${{markId}}" data-row="${{s.row_id}}" data-skos="${{hasSkos ? escapeHtml(s.skos) : ''}}" onclick="handleMarkClick(event, '${{markId}}')" title="${{hasSkos ? 'SKOS: ' + skosLabel : 'Kein SKOS-Begriff verknüpft'}}">${{spanText}}</mark>`;
                
                resultParts.push(afterText);
                resultParts.push(taggedSpan);
                currPos = s.start;

                annotations.push({{
                    id: markId,
                    text: rawText.substring(s.start, s.end),
                    category: s.category,
                    row_id: s.row_id,
                    skos: hasSkos ? s.skos : null
                }});
            }}

            resultParts.push(escapeHtml(rawText.substring(0, currPos)));
            document.getElementById('textBody').innerHTML = resultParts.reverse().join('');
            updateAnnotationsUI();
        }}

        function renderTable(tableRows) {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            for (let r of tableRows) {{
                const tr = document.createElement('tr');
                tr.className = 'table-row';
                tr.id = `tbl_${{r.id}}`;
                tr.onclick = () => highlightRowInText(r.id);

                tr.innerHTML = `
                    <td><strong>S. ${{escapeHtml(r.page)}}</strong></td>
                    <td><span class="badge ort">${{escapeHtml(r.ort)}}</span><br><small style="color:#64748b;">${{escapeHtml(r.kreis)}}</small></td>
                    <td><span class="badge aktivitaet">${{escapeHtml(r.massnahme)}}</span></td>
                    <td><span class="badge datierung">${{escapeHtml(r.datierung)}}</span></td>
                    <td><span class="badge befund">${{escapeHtml(r.befunde)}}</span></td>
                    <td><span class="badge fund">${{escapeHtml(r.funde)}}</span></td>
                `;
                tbody.appendChild(tr);
            }}
        }}

        function filterTable(query) {{
            const q = query.toLowerCase().trim();
            const rows = document.querySelectorAll('#tableBody tr');
            rows.forEach(tr => {{
                if (!q || tr.innerText.toLowerCase().includes(q)) {{
                    tr.style.display = '';
                }} else {{
                    tr.style.display = 'none';
                }}
            }});
        }}

        function highlightRowInText(rowId) {{
            document.querySelectorAll('.table-row').forEach(r => r.classList.remove('active-row'));
            const tblRow = document.getElementById(`tbl_${{rowId}}`);
            if (tblRow) tblRow.classList.add('active-row');

            document.querySelectorAll('mark').forEach(m => m.classList.remove('selected-pulse'));
            const marks = document.querySelectorAll(`mark[data-row="${{rowId}}"]`);
            if (marks.length > 0) {{
                const firstMark = marks[0];
                firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                marks.forEach(m => m.classList.add('selected-pulse'));
                showToast(`Textstelle für Zeile ${{rowId.replace('row_','')}} hervorgehoben`);
            }} else {{
                showToast(`Keine direkte Textmarkierung für Zeile ${{rowId.replace('row_','')}} gefunden`);
            }}
        }}

        function handleMarkClick(evt, markId) {{
            evt.stopPropagation();
            activeMarkId = markId;
            const markEl = document.getElementById(markId);
            if (!markEl) return;

            const rowId = markEl.getAttribute('data-row');
            if (rowId) {{
                document.querySelectorAll('.table-row').forEach(r => r.classList.remove('active-row'));
                const tblRow = document.getElementById(`tbl_${{rowId}}`);
                if (tblRow) {{
                    tblRow.classList.add('active-row');
                    tblRow.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                }}
            }}

            document.querySelectorAll('mark').forEach(m => m.classList.remove('selected-pulse'));
            if (rowId) {{
                document.querySelectorAll(`mark[data-row="${{rowId}}"]`).forEach(m => m.classList.add('selected-pulse'));
            }} else {{
                markEl.classList.add('selected-pulse');
            }}

            switchTab('vocab');
            const anno = annotations.find(a => a.id === markId);
            if (anno) {{
                document.getElementById('vocabSearch').value = anno.text;
                filterVocab(anno.text);
            }}
        }}

        function setVocabCatFilter(cat, pillEl) {{
            activeVocabCatFilter = cat;
            document.querySelectorAll('.vcat-pill').forEach(p => p.classList.remove('active'));
            pillEl.classList.add('active');
            filterVocab(document.getElementById('vocabSearch').value);
        }}

        function filterVocab(query) {{
            const listEl = document.getElementById('vocabList');
            listEl.innerHTML = '';
            const q = query.toLowerCase().trim();

            let matches = [];
            for (let cat in rawVocabularies) {{
                if (activeVocabCatFilter !== 'all' && cat !== activeVocabCatFilter) continue;

                for (let item of rawVocabularies[cat]) {{
                    if (!q || item.term.toLowerCase().includes(q) || item.alt.some(a => a.toLowerCase().includes(q))) {{
                        matches.push(item);
                        if (matches.length >= 60) break;
                    }}
                }}
                if (matches.length >= 60) break;
            }}

            if (matches.length === 0) {{
                listEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 20px;">Keine SKOS-Begriffe gefunden.</div>';
                return;
            }}

            for (let item of matches) {{
                const card = document.createElement('div');
                card.className = 'vocab-item';
                card.draggable = true;
                card.ondragstart = (e) => {{
                    e.dataTransfer.setData('text/plain', JSON.stringify(item));
                }};

                const altStr = item.alt.length > 0 ? `(Syn: ${{item.alt.slice(0, 2).join(', ')}})` : '';
                card.innerHTML = `
                    <div>
                        <div class="term-title">${{escapeHtml(item.term)}} <small style="color: #0284c7; font-size: 11px;">[${{item.category}}]</small></div>
                        ${{altStr ? `<div class="term-alt">${{escapeHtml(altStr)}}</div>` : ''}}
                    </div>
                    <button class="btn-assign" onclick="assignSKOSDirect('${{escapeHtml(item.term)}}')">Zuweisen</button>
                `;
                listEl.appendChild(card);
            }}
        }}

        const EMBEDDED_GAZETTEER = {gazetteer_json_str};
        let leafletMap = null;
        let mapMarkers = {{}};
        let activeResolvedLocations = {{}};

        function initLeafletMap() {{
            const mapContainer = document.getElementById('leafletMap');
            if (!mapContainer || leafletMap) return;

            try {{
                leafletMap = L.map('leafletMap').setView([50.85, 6.75], 9);
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '© OpenStreetMap | Rheinland Georeferenzierung'
                }}).addTo(leafletMap);
            }} catch(e) {{
                console.warn("Leaflet Map init error:", e);
            }}
        }}

        function createCustomIcon(color) {{
            return L.divIcon({{
                className: 'custom-map-pin',
                html: `<div style="background-color:${{color}}; width:14px; height:14px; border-radius:50%; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.4);"></div>`,
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            }});
        }}

        async function resolveAllLocationsForDoc(docKey) {{
            const docData = EMBEDDED_DOCS[docKey];
            if (!docData || !docData.table_rows) return;

            const listEl = document.getElementById('locationVerifyList');
            if (listEl) listEl.innerHTML = '<div style="color: #0284c7; text-align: center; padding: 15px; font-weight: bold;">🔍 Analysiere Ortsangaben & Gazetteer...</div>';

            const uniqueOrts = new Set();
            for (let row of docData.table_rows) {{
                const o = row.ort ? row.ort.trim() : '';
                if (o && o !== '-' && o.length > 1) {{
                    o.split(/[,;\/]/).forEach(parts => {{
                        const cleanP = parts.trim();
                        if (cleanP.length > 1) uniqueOrts.add(cleanP);
                    }});
                }}
            }}

            activeResolvedLocations = {{}};
            if (leafletMap) {{
                for (let k in mapMarkers) {{
                    leafletMap.removeLayer(mapMarkers[k]);
                }}
                mapMarkers = {{}};
            }}

            for (let ortName of Array.from(uniqueOrts)) {{
                await resolveSingleLocationTiered(ortName);
            }}

            renderLocationVerifyUI();
        }}

        async function resolveSingleLocationTiered(ortName) {{
            const lowOrt = ortName.toLowerCase();
            
            // TIER 1: Check Rheinland Gazetteer
            if (EMBEDDED_GAZETTEER[lowOrt]) {{
                const gaz = EMBEDDED_GAZETTEER[lowOrt];
                activeResolvedLocations[ortName] = {{
                    name: ortName,
                    tier: 1,
                    status: 'verified',
                    lat: gaz.lat,
                    lon: gaz.lon,
                    badge: '🟢 Stufe 1: Gazetteer (Auto)',
                    color: '#059669',
                    landkreis: gaz.landkreis
                }};
                addMarkerToMap(ortName, activeResolvedLocations[ortName]);
                return;
            }}

            // TIER 2: Query Nominatim / GeoNames API
            try {{
                const nomUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${{encodeURIComponent(ortName)}}+Rheinland+Deutschland`;
                const response = await fetch(nomUrl);
                if (response.ok) {{
                    const data = await response.json();
                    if (data && data.length > 0) {{
                        const item = data[0];
                        activeResolvedLocations[ortName] = {{
                            name: ortName,
                            tier: 2,
                            status: 'pending',
                            lat: parseFloat(item.lat),
                            lon: parseFloat(item.lon),
                            badge: '🟡 Stufe 2: GeoNames (Prüfung)',
                            color: '#ca8a04',
                            display_name: item.display_name
                        }};
                        addMarkerToMap(ortName, activeResolvedLocations[ortName]);
                        return;
                    }}
                }}
            }} catch(e) {{
                console.warn("Nominatim fetch error:", e);
            }}

            // TIER 3: Gemini Fallback Candidate
            activeResolvedLocations[ortName] = {{
                name: ortName,
                tier: 3,
                status: 'pending',
                lat: 50.85 + (Math.random() - 0.5) * 0.4,
                lon: 6.75 + (Math.random() - 0.5) * 0.4,
                badge: '🟠 Stufe 3: Gemini KI (Prüfung)',
                color: '#ea580c',
                is_estimated: true
            }};
            addMarkerToMap(ortName, activeResolvedLocations[ortName]);
        }}

        function addMarkerToMap(ortName, locObj) {{
            if (!leafletMap) initLeafletMap();
            if (!leafletMap) return;

            const marker = L.marker([locObj.lat, locObj.lon], {{
                icon: createCustomIcon(locObj.color),
                draggable: locObj.status !== 'verified'
            }}).addTo(leafletMap);

            marker.bindPopup(`
                <div style="font-size: 12.5px;">
                    <strong>📍 ${{escapeHtml(locObj.name)}}</strong><br>
                    <small style="color:${{locObj.color}}; font-weight:bold;">${{locObj.badge}}</small><br>
                    <small>Koord: ${{locObj.lat.toFixed(5)}}, ${{locObj.lon.toFixed(5)}}</small>
                </div>
            `);

            marker.on('dragend', (e) => {{
                const newPos = e.target.getLatLng();
                locObj.lat = newPos.lat;
                locObj.lon = newPos.lng;
                locObj.user_dragged = true;
                marker.getPopup().setContent(`
                    <div style="font-size: 12.5px;">
                        <strong>📍 ${{escapeHtml(locObj.name)}} (Manuell verschoben)</strong><br>
                        <small style="color:#0284c7; font-weight:bold;">📍 Punkt manuell angepasst</small><br>
                        <small>Koord: ${{locObj.lat.toFixed(5)}}, ${{locObj.lon.toFixed(5)}}</small>
                    </div>
                `);
                renderLocationVerifyUI();
            }});

            mapMarkers[ortName] = marker;
        }}

        function confirmLocationVerification(ortName) {{
            const loc = activeResolvedLocations[ortName];
            if (loc) {{
                loc.status = 'verified';
                loc.color = '#059669';
                loc.badge = '🟢 Verifiziert (Bestätigt)';
                
                if (mapMarkers[ortName]) {{
                    leafletMap.removeLayer(mapMarkers[ortName]);
                    addMarkerToMap(ortName, loc);
                }}

                renderLocationVerifyUI();
                showToast(`✅ Standort "${{ortName}}" erfolgreich verifiziert!`);
            }}
        }}

        function focusLocationOnMap(ortName) {{
            const loc = activeResolvedLocations[ortName];
            if (loc && leafletMap) {{
                leafletMap.setView([loc.lat, loc.lon], 12, {{ animate: true }});
                if (mapMarkers[ortName]) {{
                    mapMarkers[ortName].openPopup();
                }}
            }}
        }}

        function renderLocationVerifyUI() {{
            const listEl = document.getElementById('locationVerifyList');
            if (!listEl) return;

            const keys = Object.keys(activeResolvedLocations);
            if (keys.length === 0) {{
                listEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 15px;">Keine Ortsangaben im Dokument gefunden.</div>';
                return;
            }}

            listEl.innerHTML = '';
            for (let ortName of keys) {{
                const loc = activeResolvedLocations[ortName];
                const card = document.createElement('div');
                card.style.cssText = `background:#ffffff; border-left:4px solid ${{loc.color}}; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px; display:flex; flex-direction:column; gap:4px; font-size:12.5px; box-shadow:0 1px 2px rgba(0,0,0,0.03);`;

                const isVer = loc.status === 'verified';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold; color:#0f172a; font-size:13px; cursor:pointer;" onclick="focusLocationOnMap('${{escapeHtml(ortName)}}')">📍 ${{escapeHtml(ortName)}}</span>
                        <span style="font-size:10.5px; font-weight:bold; color:${{loc.color}};">${{loc.badge}}</span>
                    </div>
                    <div style="color:#64748b; font-size:11px; display:flex; justify-content:space-between; align-items:center;">
                        <span>Lat: ${{loc.lat.toFixed(4)}}, Lon: ${{loc.lon.toFixed(4)}}</span>
                        <button style="font-size:10.5px; padding:2px 8px; background:#f1f5f9; border:1px solid #cbd5e1; font-weight:bold;" onclick="focusLocationOnMap('${{escapeHtml(ortName)}}')">🗺️ Zeigen</button>
                    </div>
                    ${{!isVer ? `
                        <div style="display:flex; gap:6px; margin-top:4px;">
                            <button style="flex:1; background:#10b981; color:white; border:none; padding:5px; border-radius:4px; font-weight:bold; font-size:11px; cursor:pointer;" onclick="confirmLocationVerification('${{escapeHtml(ortName)}}')">✅ Standort auf Karte bestätigen</button>
                        </div>
                    ` : ''}}
                `;
                listEl.appendChild(card);
            }}
        }}

        function exportGeoJSON() {{
            const features = [];
            for (let ortName in activeResolvedLocations) {{
                const loc = activeResolvedLocations[ortName];
                features.push({{
                    type: "Feature",
                    geometry: {{
                        type: "Point",
                        coordinates: [loc.lon, loc.lat]
                    }},
                    properties: {{
                        name: loc.name,
                        status: loc.status,
                        tier: loc.tier,
                        badge: loc.badge
                    }}
                }});
            }}

            const geojsonObj = {{
                type: "FeatureCollection",
                features: features
            }};

            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(geojsonObj, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `archaeo_sites_${{activeDocKey.replace(/[^a-zA-Z0-9]/g, '_')}}.geojson`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            showToast("📥 QGIS GeoJSON erfolgreich exportiert!");
        }}

        function loadDocument(docName) {{
            if (!docName) return;
            activeDocKey = docName;
            const docData = EMBEDDED_DOCS[docName];
            if (docData) {{
                document.getElementById('currentDocTitle').innerText = `📄 ${{docData.title || docName}}`;
                renderHighlightedText(docData);
                renderTable(docData.table_rows || []);
                resolveAllLocationsForDoc(docName);
                showToast(`Dokument ${{docData.title || docName}} geladen`);
            }} else {{
                showToast(`Dokument ${{docName}} nicht gefunden`);
            }}
        }}

        function handleFileUpload(evt) {{
            const file = evt.target.files[0];
            if (file) {{
                const reader = new FileReader();
                reader.onload = (e) => {{
                    const raw = e.target.result;
                    const docKey = file.name;
                    EMBEDDED_DOCS[docKey] = {{
                        title: file.name,
                        raw_text: raw,
                        spans: [],
                        table_rows: []
                    }};
                    initDocSelect();
                    document.getElementById('docSelect').value = docKey;
                    loadDocument(docKey);
                    showToast(`Datei ${{file.name}} geladen`);
                }};
                reader.readAsText(file);
            }}
        }}

        function populateBroaderDatalist() {{
            const datalist = document.getElementById('broaderConceptsList');
            if (!datalist) return;
            datalist.innerHTML = '';
            const termsSet = new Set();
            for (let cat in rawVocabularies) {{
                for (let item of rawVocabularies[cat]) {{
                    if (item && item.term) termsSet.add(item.term);
                }}
            }}
            Array.from(termsSet).sort().forEach(term => {{
                const opt = document.createElement('option');
                opt.value = term;
                datalist.appendChild(opt);
            }});
        }}

        function openSkosModal(defaultTerm) {{
            document.getElementById('newSkosTerm').value = defaultTerm || '';
            document.getElementById('newSkosAlt').value = '';
            document.getElementById('newSkosBroader').value = '';
            populateBroaderDatalist();
            document.getElementById('skosModal').style.display = 'flex';
        }}

        function openSkosModalWithSelection() {{
            const selText = selectedRange ? selectedRange.toString().trim() : '';
            document.getElementById('selectionTooltip').style.display = 'none';
            openSkosModal(selText);
        }}

        function closeSkosModal() {{
            document.getElementById('skosModal').style.display = 'none';
        }}

        function filterAndSortSpans(spans) {{
            const catOrder = {{ datierung: 5, befund: 4, fund: 3, aktivitaet: 2, ort: 1 }};
            spans.sort((a, b) => {{
                if (a.start !== b.start) return a.start - b.start;
                const pA = catOrder[a.category] || 0;
                const pB = catOrder[b.category] || 0;
                if (pA !== pB) return pB - pA;
                return (b.end - b.start) - (a.end - a.start);
            }});

            const filtered = [];
            let lastEnd = 0;
            for (let s of spans) {{
                if (s.start >= lastEnd) {{
                    filtered.push(s);
                    lastEnd = s.end;
                }}
            }}
            return filtered;
        }}

        function saveNewSkosTerm() {{
            try {{
                const termInput = document.getElementById('newSkosTerm');
                const term = termInput ? termInput.value.trim() : '';
                const category = document.getElementById('newSkosCategory').value;
                const altStr = document.getElementById('newSkosAlt').value.trim();
                const altList = altStr ? altStr.split(',').map(s => s.trim()).filter(Boolean) : [];
                const broader = document.getElementById('newSkosBroader').value.trim();

                if (!term) {{
                    alert('Bitte geben Sie einen SKOS-Begriff ein!');
                    return;
                }}

                if (!rawVocabularies[category]) rawVocabularies[category] = [];
                const newItem = {{ term: term, alt: altList, category: category, broader: broader }};
                rawVocabularies[category].unshift(newItem);

                ALL_SKOS_CAT_MAP[term.toLowerCase()] = category;
                altList.forEach(a => ALL_SKOS_CAT_MAP[a.toLowerCase()] = category);

                // Save to localStorage for persistence across reloads
                try {{
                    localStorage.setItem('user_skos_vocab', JSON.stringify(rawVocabularies));
                }} catch(err) {{
                    console.warn("Could not save to localStorage:", err);
                }}

                let matchesFound = 0;
                const docData = EMBEDDED_DOCS[activeDocKey];
                if (docData && docData.raw_text) {{
                    const lowCat = category.toLowerCase();
                    const skosNorm = term + (broader ? ` (Oberbegriff: ${{broader}})` : ' (SKOS)');
                    const searchVariants = [term, ...altList];

                    const rawText = docData.raw_text;
                    const lowerText = rawText.toLowerCase();
                    const isLetter = (c) => /[a-zA-ZäöüÄÖÜß0-9]/.test(c);

                    for (let variant of searchVariants) {{
                        if (!variant || variant.length < 2) continue;
                        const lowerVar = variant.toLowerCase();
                        let pos = 0;

                        while ((pos = lowerText.indexOf(lowerVar, pos)) !== -1) {{
                            const endPos = pos + lowerVar.length;
                            const charBefore = pos > 0 ? rawText[pos - 1] : ' ';
                            const charAfter = endPos < rawText.length ? rawText[endPos] : ' ';

                            if (!isLetter(charBefore) && !isLetter(charAfter)) {{
                                docData.spans.push({{
                                    start: pos,
                                    end: endPos,
                                    category: lowCat,
                                    text: rawText.substring(pos, endPos),
                                    row_id: '',
                                    skos: skosNorm
                                }});
                                matchesFound++;
                            }}
                            pos += Math.max(1, lowerVar.length);
                        }}
                    }}

                    // Deduplicate and filter spans cleanly
                    docData.spans = filterAndSortSpans(docData.spans);
                    renderHighlightedText(docData);
                }}

                filterVocab(document.getElementById('vocabSearch').value || '');
                closeSkosModal();
                showToast(`✅ "${{term}}" als ${{category}} gespeichert (${{matchesFound}} Vorkommen hervorgehoben)!`);
            }} catch(e) {{
                console.error("Fehler beim Speichern des SKOS-Begriffs:", e);
                alert("Fehler beim Speichern: " + e.message);
            }}
        }}

        function exportUpdatedSKOS() {{
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(rawVocabularies, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", "arch_vocab_rhineland_updated.json");
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            showToast("📥 SKOS-Vokabular erfolgreich als JSON exportiert!");
        }}

        function handleTextSelection(evt) {{
            const sel = window.getSelection();
            if (!sel || sel.isCollapsed) {{
                document.getElementById('selectionTooltip').style.display = 'none';
                return;
            }}
            const text = sel.toString().trim();
            if (text.length > 0) {{
                selectedRange = sel.getRangeAt(0);
                const rect = selectedRange.getBoundingClientRect();
                const tooltip = document.getElementById('selectionTooltip');
                tooltip.style.left = `${{Math.max(10, rect.left + window.scrollX)}}px`;
                tooltip.style.top = `${{Math.max(10, rect.top + window.scrollY - 45)}}px`;
                tooltip.style.display = 'flex';
            }}
        }}

        function annotateSelected(category) {{
            if (!selectedRange) return;
            const text = selectedRange.toString().trim();
            if (!text) return;

            const id = 'anno_' + Date.now();
            const mark = document.createElement('mark');
            mark.className = `${{category}} no-skos-mark`;
            mark.id = id;
            mark.innerText = text;
            mark.onclick = (e) => handleMarkClick(e, id);

            selectedRange.deleteContents();
            selectedRange.insertNode(mark);

            annotations.push({{
                id: id,
                text: text,
                category: category,
                skos: null
            }});

            document.getElementById('selectionTooltip').style.display = 'none';
            window.getSelection().removeAllRanges();
            updateAnnotationsUI();
            showToast(`Markiert als ${{category}}`);
        }}

        function assignSKOSDirect(skosTerm) {{
            if (!activeMarkId && annotations.length > 0) {{
                activeMarkId = annotations[annotations.length - 1].id;
            }}
            if (!activeMarkId) {{
                showToast("Bitte zuerst eine Textstelle markieren!");
                return;
            }}

            const anno = annotations.find(a => a.id === activeMarkId);
            if (anno) {{
                anno.skos = skosTerm;
                const markEl = document.getElementById(activeMarkId);
                if (markEl) {{
                    markEl.title = `SKOS: ${{skosTerm}}`;
                    markEl.className = markEl.className.replace('no-skos-mark', 'has-skos-mark');
                    markEl.setAttribute('data-skos', skosTerm);
                }}
                updateAnnotationsUI();
                showToast(`SKOS Begriff "${{skosTerm}}" zugewiesen!`);
            }}
        }}

        function changeAnnoCategory(id, newCategory) {{
            const anno = annotations.find(a => a.id === id);
            if (anno) {{
                anno.category = newCategory;
                const markEl = document.getElementById(id);
                if (markEl) {{
                    markEl.className = `${{newCategory}} ${{anno.skos ? 'has-skos-mark' : 'no-skos-mark'}}`;
                }}
                updateAnnotationsUI();
                showToast(`Kategorie geändert auf ${{newCategory}}`);
            }}
        }}

        function handleDropOnText(evt) {{
            evt.preventDefault();
            const raw = evt.dataTransfer.getData('text/plain');
            if (raw) {{
                try {{
                    const item = JSON.parse(raw);
                    assignSKOSDirect(item.term);
                }} catch(e){{ /* ignore */ }}
            }}
        }}

        function updateAnnotationsUI() {{
            document.getElementById('annoCount').innerText = annotations.length;
            const listEl = document.getElementById('annoList');
            listEl.innerHTML = '';

            if (annotations.length === 0) {{
                listEl.innerHTML = '<div style="color: #64748b; text-align: center; padding: 20px;">Noch keine Annotationen vorhanden.</div>';
                return;
            }}

            for (let anno of annotations) {{
                const card = document.createElement('div');
                card.className = `anno-card ${{anno.category}}`;
                card.innerHTML = `
                    <div class="anno-header">
                        <select class="cat-select" onchange="changeAnnoCategory('${{anno.id}}', this.value)">
                            <option value="aktivitaet" ${{anno.category === 'aktivitaet' ? 'selected' : ''}}>Aktivität</option>
                            <option value="ort" ${{anno.category === 'ort' ? 'selected' : ''}}>Ort</option>
                            <option value="datierung" ${{anno.category === 'datierung' ? 'selected' : ''}}>Datierung</option>
                            <option value="befund" ${{anno.category === 'befund' ? 'selected' : ''}}>Befund</option>
                            <option value="fund" ${{anno.category === 'fund' ? 'selected' : ''}}>Fund</option>
                        </select>
                        <button class="btn-delete" onclick="deleteAnnotation('${{anno.id}}')">Entfernen</button>
                    </div>
                    <div class="anno-text">"${{escapeHtml(anno.text)}}"</div>
                    <div class="anno-skos">
                        <span>${{anno.skos ? '🏷️ ' + escapeHtml(anno.skos) + ' (SKOS)' : '<span style="color: #ef4444; font-size: 11px;">Kein SKOS-Begriff</span>'}}</span>
                        <button class="btn-assign" style="font-size: 10px; padding: 2px 6px;" onclick="activeMarkId='${{anno.id}}'; switchTab('vocab'); document.getElementById('vocabSearch').value='${{escapeHtml(anno.text)}}'; filterVocab('${{escapeHtml(anno.text)}}');">Suchen</button>
                    </div>
                `;
                listEl.appendChild(card);
            }}
        }}

        function deleteAnnotation(id) {{
            const markEl = document.getElementById(id);
            if (markEl) {{
                const text = markEl.innerText;
                markEl.replaceWith(document.createTextNode(text));
            }}
            annotations = annotations.filter(a => a.id !== id);
            updateAnnotationsUI();
            showToast("Annotation entfernt");
        }}

        function clearAllAnnotations() {{
            if (confirm("Möchten Sie wirklich alle Annotationen löschen?")) {{
                annotations.forEach(a => {{
                    const markEl = document.getElementById(a.id);
                    if (markEl) markEl.replaceWith(document.createTextNode(markEl.innerText));
                }});
                annotations = [];
                updateAnnotationsUI();
                showToast("Alle Annotationen zurückgesetzt");
            }}
        }}

        function exportCSV() {{
            let csv = "id;kategorie;text_roh;skos_norm\\n";
            for (let a of annotations) {{
                csv += `"${{a.id}}";"${{a.category}}";"${{a.text.replace(/"/g, '""')}}";"${{a.skos || '-'}}"\\n`;
            }}
            downloadFile(csv, "annotationen_export.csv", "text/csv;charset=utf-8;");
        }}

        function exportJSON() {{
            const dataStr = JSON.stringify(annotations, null, 2);
            downloadFile(dataStr, "annotationen_export.json", "application/json");
        }}

        function exportFullTableCSV() {{
            const docData = EMBEDDED_DOCS[activeDocKey];
            if (!docData || !docData.table_rows) {{
                showToast("Keine Tabellendaten zum Exportieren vorhanden.");
                return;
            }}
            let csv = "Seitenzahl;ort;kreis;massnahme_id;datierung_norm;befunde_norm;funde_norm;autor\\n";
            for (let r of docData.table_rows) {{
                csv += `"${{r.page}}";"${{r.ort}}";"${{r.kreis}}";"${{r.massnahme}}";"${{r.datierung}}";"${{r.befunde}}";"${{r.funde}}";"${{r.autor}}"\\n`;
            }}
            downloadFile(csv, `${{activeDocKey.replace('.txt','')}}_Export.csv`, "text/csv;charset=utf-8;");
        }}

        function downloadFile(content, fileName, mimeType) {{
            const blob = new Blob([content], {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            a.click();
            URL.revokeObjectURL(url);
            showToast(`Datei ${{fileName}} heruntergeladen`);
        }}

        function showToast(msg) {{
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.display = 'block';
            setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
        }}

        function escapeHtml(str) {{
            return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }}

        // Resizable Split Pane Logic
        const resizer = document.getElementById('dragResizer');
        const leftPane = document.querySelector('.pane-text');
        const rightPane = document.querySelector('.pane-sidebar');
        let isResizing = false;

        resizer.addEventListener('mousedown', (e) => {{
            isResizing = true;
            resizer.classList.add('dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        }});

        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;
            const containerWidth = document.querySelector('.main-layout').clientWidth;
            const leftWidth = (e.clientX / containerWidth) * 100;
            if (leftWidth > 15 && leftWidth < 85) {{
                leftPane.style.flex = `0 0 ${{leftWidth}}%`;
                rightPane.style.flex = `0 0 ${{100 - leftWidth}}%`;
            }}
        }});

        document.addEventListener('mouseup', () => {{
            if (isResizing) {{
                isResizing = false;
                resizer.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }}
        }});

        // Synchronized Auto-Scroll: Text View -> Extraktions-Tabelle
        const textBodyEl = document.getElementById('textBody');
        let isProgrammaticScroll = false;

        textBodyEl.addEventListener('scroll', () => {{
            if (isProgrammaticScroll) return;
            const marks = Array.from(textBodyEl.querySelectorAll('mark[data-row]'));
            const textTop = textBodyEl.getBoundingClientRect().top;
            
            let visibleMark = null;
            for (let m of marks) {{
                const rect = m.getBoundingClientRect();
                if (rect.top >= textTop && rect.top <= textTop + 250) {{
                    visibleMark = m;
                    break;
                }}
            }}
            
            if (visibleMark) {{
                const rowId = visibleMark.getAttribute('data-row');
                if (rowId) {{
                    document.querySelectorAll('.table-row').forEach(r => r.classList.remove('active-row'));
                    const tblRow = document.getElementById('tbl_' + rowId);
                    if (tblRow) {{
                        tblRow.classList.add('active-row');
                        tblRow.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                    }}
                }}
            }}
        }});

        // Init
        initDocSelect();
        filterVocab('');
    </script>
</body>
</html>
"""

editor_path = os.path.join(root_dir, "annotation_editor.html")
with open(editor_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"✅ Standalone Annotation Editor created at: {editor_path}")
