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

# Build SKOS lookup dictionary from vocab_data
SKOS_CONCEPT_MAP = {}
for cat, items in vocab_data.items():
    for item in items:
        term = item.get('term', '').strip()
        if term:
            SKOS_CONCEPT_MAP[term.lower()] = term
        for alt in item.get('alt', []):
            if alt:
                SKOS_CONCEPT_MAP[alt.lower()] = term

def resolve_skos_concept(term):
    if not term or not isinstance(term, str):
        return None, 'none'
    clean = re.sub(r'\s*\(skos\)', '', term, flags=re.IGNORECASE).strip().strip("'\"[]")
    if not clean or clean in ['-', 'nan', 'None'] or len(clean) < 2:
        return None, 'none'

    clean_l = clean.lower()
    if clean_l in SKOS_CONCEPT_MAP:
        return SKOS_CONCEPT_MAP[clean_l], 'direct'

    # Century & Half Dating Expression Normalization (e.g. "zweite Hälfte 4. Jh.", "1. Hälfte 2. Jh.")
    m_half = re.search(r'(erste|1\.|zweite|2\.)\s*hälfte\s*(?:des\s+)?(\d+)\.\s*(?:jh\.|jahrhundert|jhs\.)', clean_l)
    if m_half:
        num_str = '1.' if '1' in m_half.group(1) or 'erste' in m_half.group(1) else '2.'
        cent_num = m_half.group(2)
        skos_term = f"{num_str} Hälfte {cent_num}. Jh. n. Chr."
        if skos_term.lower() in SKOS_CONCEPT_MAP:
            return SKOS_CONCEPT_MAP[skos_term.lower()], 'direct'
        else:
            return f"{cent_num}. Jahrhundert n. Chr.", 'broader'

    m_cent = re.search(r'(\d+)\.\s*(?:jh\.|jahrhundert|jhs\.)', clean_l)
    if m_cent:
        cent_num = m_cent.group(1)
        skos_term = f"{cent_num}. Jahrhundert n. Chr."
        if skos_term.lower() in SKOS_CONCEPT_MAP:
            return SKOS_CONCEPT_MAP[skos_term.lower()], 'direct'
        else:
            return 'Römische Kaiserzeit', 'broader'

    # 90s Activity / Measure Numbers (e.g. (1161/187), (NW97/1025), (0587/013))
    if re.search(r'\b[a-z]{1,3}\s*\d{2,4}/\d{3,4}\b|\b\d{3,4}/\d{3,4}\b', clean_l):
        return 'Maßnahme', 'broader'

    # Specific Typology & Parent Concept Mappings (Broader Match)
    if 'amphore' in clean_l:
        return SKOS_CONCEPT_MAP.get('amphore', 'Amphore'), 'broader'
    if 'niederbieber' in clean_l:
        return SKOS_CONCEPT_MAP.get('niederbieber', 'Niederbieber'), 'broader'
    if re.search(r'\bdrag\.\s*\d+', clean_l):
        return SKOS_CONCEPT_MAP.get('terra sigillata', 'Terra Sigillata'), 'broader'
    if 'mortarium' in clean_l:
        return SKOS_CONCEPT_MAP.get('mortarium', 'Mortarium'), 'broader'
    if 'reibschale' in clean_l:
        return SKOS_CONCEPT_MAP.get('reibschale', 'Reibschale'), 'broader'
    if 'tegula' in clean_l or 'tegulae' in clean_l:
        return SKOS_CONCEPT_MAP.get('tegula (dachziegel)', 'Tegula (Dachziegel)'), 'broader'
    if 'imbrex' in clean_l:
        return SKOS_CONCEPT_MAP.get('imbrex', 'Imbrex'), 'direct'
    if 'krug' in clean_l or 'krüge' in clean_l:
        return SKOS_CONCEPT_MAP.get('krug', 'Krug'), 'broader'
    if 'topf' in clean_l or 'töpfe' in clean_l:
        return SKOS_CONCEPT_MAP.get('topf (behälter)', 'Topf (Behälter)'), 'broader'
    if 'schüssel' in clean_l:
        return SKOS_CONCEPT_MAP.get('schüssel', 'Schüssel'), 'broader'
    if 'schale' in clean_l:
        return SKOS_CONCEPT_MAP.get('schale', 'Schale'), 'broader'
    if 'villa rustica' in clean_l:
        return SKOS_CONCEPT_MAP.get('villa rustica', 'Villa rustica'), 'direct'

    words = clean_l.split()
    for w in words:
        if len(w) >= 4 and w in SKOS_CONCEPT_MAP:
            return SKOS_CONCEPT_MAP[w], 'broader'

    return None, 'none'

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

def clean_and_reflow_text(text):
    if not text:
        return ''
    # 1. Punctuation spacing
    text = re.sub(r'([a-zäöüß0-9]{2,})([.!?])([A-ZÄÖÜ])', r'\1\2 \3', text)
    text = re.sub(r'([a-zäöüß0-9])([,;:])([A-ZÄÖÜa-zäöüß0-9])', r'\1\2 \3', text)
    text = re.sub(r'([a-zäöüß0-9])([–—])([A-ZÄÖÜa-zäöüß])', r'\1 \2 \3', text)
    
    # 2. Run-together prepositions and abbreviations
    prep_pat = r'([a-zäöüß]{3,})(bei|auf|in|im|aus|nach|vor|unter|über|vom|von|mit|durch|zu|zur|zum|und|oder)\s+([A-ZÄÖÜ])'
    text = re.sub(prep_pat, r'\1 \2 \3', text)
    text = re.sub(r'([a-zäöüß]{3,})(s\.o\.|s\.u\.|vgl\.)', r'\1 \2', text)
    text = re.sub(r'\bs\.o\.', 's. o.', text)
    text = re.sub(r'\bs\.u\.', 's. u.', text)
    text = re.sub(r'\bd\.h\.', 'd. h.', text)
    text = re.sub(r'(\b[A-Za-zäöüÄÖÜß]+)\.(\d+)', r'\1. \2', text)
    text = re.sub(r'([a-zäöüß]{3,})([A-ZÄÖÜ][a-zäöüß]{2,})', r'\1 \2', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    # 3. De-hyphenate line endings
    text = re.sub(r'(\b[\wöäüß]+)-[­]?\s*\n\s*([\wöäüß]+)', r'\1\2', text)
    
    # 4. Reflow lines into flowing paragraphs
    lines = text.split('\n')
    out_paras = []
    cur_para = ''
    
    for l in lines:
        l = l.strip()
        if not l:
            if cur_para:
                out_paras.append(cur_para)
                cur_para = ''
            continue
        if re.match(r'^---\s*SEITE\s*\d+\s*---$', l, re.IGNORECASE) or re.match(r'^---\s*(?:LEFT|RIGHT)\s*COLUMN\s*---$', l, re.IGNORECASE):
            if cur_para:
                out_paras.append(cur_para)
                cur_para = ''
            out_paras.append(l)
            continue
        if not cur_para:
            cur_para = l
        else:
            prev_ends_punct = bool(re.search(r'[.!?]$', cur_para))
            next_is_measure = bool(re.match(r'^\d+\.\s+[A-ZÄÖÜ]', l))
            next_is_loc = bool(re.match(r'^[A-ZÄÖÜ][a-zäöüß]+,\s+[A-ZÄÖÜ]', l))
            next_is_verbleib = bool(re.match(r'^Verbleib:', l, re.IGNORECASE))
            
            if prev_ends_punct and (next_is_measure or next_is_loc or next_is_verbleib):
                out_paras.append(cur_para)
                cur_para = l
            elif next_is_measure or next_is_loc:
                out_paras.append(cur_para)
                cur_para = l
            else:
                cur_para += ' ' + l
    if cur_para:
        out_paras.append(cur_para)
        
    return '\n\n'.join(out_paras)

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
        raw_text = clean_and_reflow_text(f.read())

    # Filter out standalone figure caption rows that lack massnahme_id and distort text sections
    df = df[~((df['massnahme_id'].isna() | (df['massnahme_id'] == 'None') | (df['massnahme_id'] == 'nan')) & df['ort'].astype(str).str.contains('Auxiliarlager|Matronenaltar|Terra sigillata', case=False, na=False))].copy()
    df.reset_index(drop=True, inplace=True)

    STOPWORDS = {
        'in', 'im', 'an', 'am', 'er', 'es', 'en', 'oder', 'und', 'mit', 'von', 'aus', 'der', 'die', 'das', 'dem', 'den', 'zu', 'zur', 'zum', '2', '3', '1', '4', '5', 't',
        'au', 'ar', 's', 'dp', 'fol', 'an', 'd', 'av', 'rv', 'ric', 'ric²', 'ric3', 'ric4', 'ric5', 'av.', 'rv.', 'g', 'mm', 'ca', 'v.', 'chr.', 'rom', 'typ', 'var', 'nr.', 'nr'
    }

    # 1. Locate text section positions for each row in df using multi-criteria matching
    row_sections = []
    search_cursor = 0
    for idx, row in df.iterrows():
        row_id = f"row_{idx}"
        ort_val = str(row.get('ort', '')).strip()
        mid_val = str(row.get('massnahme_id', '')).strip()

        match_pos = -1
        if mid_val and mid_val not in ["-", "nan", "None"]:
            pat = r'(?:' + re.escape(ort_val) + r'[\s\S]{0,100}?' + re.escape(mid_val) + r'|' + re.escape(mid_val) + r'\s+(?:Bei|Im|In|Am)\b)'
            m = re.search(pat, raw_text[search_cursor:], re.IGNORECASE)
            if m:
                match_pos = search_cursor + m.start()

        if match_pos == -1 and ort_val and ort_val not in ["-", "nan", "None"]:
            m = re.search(r'\b' + re.escape(ort_val) + r'\b', raw_text[search_cursor:], re.IGNORECASE)
            if m:
                match_pos = search_cursor + m.start()

        if match_pos != -1:
            row_sections.append((match_pos, row_id, idx, row))
            search_cursor = match_pos
        else:
            row_sections.append((search_cursor, row_id, idx, row))

    spans = []
    for i in range(len(row_sections)):
        sec_start = row_sections[i][0]
        sec_end = row_sections[i+1][0] if i + 1 < len(row_sections) else len(raw_text)
        row_id = row_sections[i][1]
        row = row_sections[i][3]
        sec_text = raw_text[sec_start:sec_end]

        # Measure Header Badge
        ort_str = str(row.get('ort', '')).strip()
        mid_str = str(row.get('massnahme_id', '')).strip()
        mid_badge_text = f"📍 Maßnahme: {ort_str}" + (f" ({mid_str})" if mid_str and mid_str not in ["-", "nan", "None"] else "")

        m_head = re.search(r'^(?:[0-9]+\.\s*)?(?:[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)*|\b' + re.escape(ort_str) + r'\b)', sec_text, re.IGNORECASE)
        h_len = m_head.end() if m_head else len(ort_str)

        spans.append({
            "start": sec_start,
            "end": sec_start + max(h_len, 4),
            "category": "aktivitaet",
            "text": raw_text[sec_start:sec_start + max(h_len, 4)],
            "row_id": row_id,
            "skos": mid_badge_text
        })

        # Collect all table terms for this row
        candidates = []

        # Datierung terms
        d_raw = str(row.get('datierung_norm', '')) + " " + str(row.get('datierung_roh', ''))
        for t in re.split(r'[,|;]', d_raw):
            c = re.sub(r'\s*\(skos\)', '', t, flags=re.IGNORECASE).strip().strip("'\"[]")
            if c and c not in ['-', 'nan', 'None'] and len(c) >= 3:
                candidates.append((c, 'datierung', resolve_skos_concept(c)))

        # Befunde terms
        b_raw = str(row.get('befunde_norm', '')) + " " + str(row.get('befunde_roh', ''))
        for t in re.split(r'[,|;]', b_raw):
            c = re.sub(r'\s*\(skos\)', '', t, flags=re.IGNORECASE).strip().strip("'\"[]")
            if c and c not in ['-', 'nan', 'None'] and len(c) >= 3:
                if not re.match(r'^(Bei|Im|In|Am|Eine|Auf)\b', c):
                    candidates.append((c, 'befund', resolve_skos_concept(c)))

        # Funde & Typologien
        f_raw = str(row.get('funde_norm', '')) + " " + str(row.get('funde_roh', ''))
        drag_matches = re.findall(r'\b(?:Drag\.|Form|Typ)\s*\d+[a-z]?\b', f_raw, re.IGNORECASE)
        for dm in drag_matches:
            candidates.append((dm, 'fund', resolve_skos_concept(dm)))

        for t in re.split(r'[,|;]', f_raw):
            c = re.sub(r'\s*\(skos\)', '', t, flags=re.IGNORECASE).strip().strip("'\"[]")
            if c and c not in ['-', 'nan', 'None'] and len(c) >= 3:
                if not re.match(r'^(Taf\.|Fig\.|Abb\.|Taf|Fig|Abb|Oswald|Knorr|Forrer|Mary|Ricken|Fölzer)\s*\d*', c, re.IGNORECASE):
                    if len(c) < 40:
                        candidates.append((c, 'fund', resolve_skos_concept(c)))

        # Match candidate terms in section text
        for term_text, cat, skos_res in candidates:
            skos_label, skos_type = skos_res if isinstance(skos_res, tuple) else (skos_res, 'none')
            term_clean = term_text.strip()
            if term_clean.lower() in STOPWORDS or len(term_clean) < 3:
                continue

            word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + re.escape(term_clean) + r')(?![a-zA-ZäöüÄÖÜß0-9])', re.IGNORECASE)
            for match in word_pattern.finditer(sec_text):
                st = sec_start + match.start()
                en = sec_start + match.end()
                spans.append({
                    "start": st,
                    "end": en,
                    "category": cat,
                    "text": raw_text[st:en],
                    "row_id": row_id,
                    "skos": skos_label,
                    "skos_type": skos_type
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
        (r'Niederbieber\s*\d+[a-z]?', 'fund', 'Niederbieber (SKOS)'),
        (r'Gellep\s*\d+[a-z]?', 'fund', 'Gellep (SKOS)'),
        (r'RSNB\s*\d+[a-z]?', 'fund', 'Römische Keramik (SKOS)'),
        (r'Scherben?|Wandscherbe|Randscherbe|Randstück|Bodenstück', 'fund', 'Scherbe (SKOS)'),

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
        (r'(?:erste|zweite|zweiten|Anfang|Mitte|Ende)?\s*(?:Hälfte|Drittel|Viertel)?\s*(?:des\s+)?\d+\.\s*(?:Jahrh\.|Jahrhundert[sa]?|Jhs?\.|Jh\.)(?:\s*n\.\s*Chr\.)?', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*/\s*\d+\.\s*(?:Jahrh\.|Jahrhundert[sa]?|Jhs?\.|Jh\.)(?:\s*n\.\s*Chr\.)?', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*–\s*\d+\.\s*(?:Jahrh\.|Jahrhundert[sa]?|Jhs?\.|Jh\.)', 'datierung', 'Römische Kaiserzeit (SKOS)'),
        (r'\d+\.\s*(?:Jahrh\.|Jahrhundert[sa]?|Jhs?\.|Jh\.)', 'datierung', 'Römische Kaiserzeit (SKOS)'),
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
        (r'Schützengraben', 'befund', 'Schützengraben (SKOS)'),

        # 90er-Jahre Aktivitätsnummern & Maßnahmen-Marker (z. B. (1161/187), (NW97/1025), (0587/013, 012))
        (r'\(\s*(?:[A-Z]{1,3}\s*\d{2,4}/\d{3,4}|\d{3,4}/\d{3,4}(?:,\s*\d{3,4})*)\s*\)|\b[A-Z]{1,3}\s*\d{2,4}/\d{3,4}\b|\b\d{3,4}/\d{3,4}(?:,\s*\d{3,4})*\b', 'aktivitaet', 'Maßnahme (SKOS)')
    ]

    for pat_str, cat, skos_raw in GLOBAL_CONCEPT_PATTERNS:
        word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + pat_str + r')', re.IGNORECASE)
        for match in word_pattern.finditer(raw_text):
            start, end = match.span()
            if re.search(r'\b(keine|kein|ohne|keinerlei)\s+$', raw_text[:start], re.IGNORECASE):
                continue
            match_text = raw_text[start:end]
            if cat == 'datierung' and ('hälfte' in match_text.lower() or 'jahrh' in match_text.lower() or 'jh.' in match_text.lower()):
                skos_label, skos_type = resolve_skos_concept(match_text)
            else:
                skos_label, skos_type = resolve_skos_concept(skos_raw)
            spans.append({
                "start": start,
                "end": end,
                "category": cat,
                "text": match_text,
                "row_id": "",
                "skos": skos_label,
                "skos_type": skos_type
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


# Default API keys are kept empty in generated HTML to prevent secret leakage to Git.
# Users configure their API keys securely in the browser UI, stored in browser localStorage.
default_gemini_key = ""
default_claude_key = ""

template_path = os.path.join(root_dir, 'editor_template.html')
with open(template_path, 'r', encoding='utf-8') as f:
    template_content = f.read()

html_content = (
    template_content
    .replace('__VOCAB_JSON__', vocab_json_str)
    .replace('__DOCS_JSON__', docs_json_str)
    .replace('__GAZETTEER_JSON__', gazetteer_json_str)
    .replace('__DEFAULT_GEMINI_KEY__', json.dumps(default_gemini_key))
    .replace('__DEFAULT_CLAUDE_KEY__', json.dumps(default_claude_key))
)

editor_path = os.path.join(root_dir, 'annotation_editor.html')
with open(editor_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f'✅ Standalone Annotation Editor created at: {editor_path}')
