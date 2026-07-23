import pandas as pd
import re
import html
import os
import sys

def create_highlighted_html(csv_path, raw_text_path, html_out_path):
    if not os.path.exists(csv_path) or not os.path.exists(raw_text_path):
        print(f"Fehler: Datei {csv_path} oder {raw_text_path} existiert nicht.")
        return

    df = pd.read_csv(csv_path, sep=";")
    with open(raw_text_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Collect search fragments
    fragments = []

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

    def add_fragment(val, category):
        items = parse_raw_fragments(val)
        for clean in items:
            raw_adj, noun_rem = split_adjective_noun(clean)
            if raw_adj and noun_rem:
                fragments.append((raw_adj, 'datierung'))
                fragments.append((noun_rem, category))
            else:
                fragments.append((clean, category))

    for idx, row in df.iterrows():
        add_fragment(str(row.get('massnahme_id', '')), 'aktivitaet')
        add_fragment(str(row.get('befunde_roh', '')), 'befund')
        add_fragment(str(row.get('funde_roh', '')), 'fund')
        add_fragment(str(row.get('datierung_roh', '')), 'datierung')
        add_fragment(str(row.get('ort', '')), 'ort')
        add_fragment(str(row.get('autor', '')), 'autor')

    # Add Global Concept Scanner across full raw_text
    GLOBAL_CONCEPT_PATTERNS = [
        # Roman Emperors & Rulers (Datierung)
        (r'Augustus', 'datierung'), (r'Tiberius', 'datierung'), (r'Caligula', 'datierung'),
        (r'Claudius I\.|Claudius', 'datierung'), (r'Vespasian', 'datierung'), (r'Domitian', 'datierung'),
        (r'Nerva', 'datierung'), (r'Trajan', 'datierung'), (r'Hadrian', 'datierung'),
        (r'Antoninus Pius', 'datierung'), (r'Marc Aurel|Mark Aurel', 'datierung'), (r'Lucius Verus', 'datierung'),
        (r'Commodus', 'datierung'), (r'Septimius Severus', 'datierung'), (r'Geta', 'datierung'),
        (r'Julia Maesa', 'datierung'), (r'Gordian III\.|Gordian III', 'datierung'),
        (r'Philippus I\.|Philippus Arabs', 'datierung'), (r'Constantin I\.|Konstantin I\.|Konstantin der Große', 'datierung'),
        (r'Constantin II\.|Konstantin II\.', 'datierung'), (r'Crispina', 'datierung'), (r'Lucilla', 'datierung'),

        # Archaeological Waterworks & Structures (Befund)
        (r'Eifelwasserleitung|römische\s+Wasserleitung|Wasserleitung', 'befund'),
        (r'Frischwasserkanäle|Kanal', 'befund'), (r'Fundamentplatte|Fundament', 'befund'),
        (r'Materialentnahmegrube|Materialentnahmest\.|Materialentnahme', 'befund'),
        (r'Grubenhaus', 'befund'), (r'Pfostengruben|Pfostengrube', 'befund'), (r'Pfostenbau', 'befund'),
        (r'Kleinere\s+Gruben|Siedlungsgrube|Gruben|Grube', 'befund'),
        (r'Brandgrab|Bestattungsplatz(?:es|en|e|s)?', 'befund'),
        (r'Siedlungsbefund|Siedlungsplatz|Siedlung', 'befund'), (r'Villa rustica', 'befund'),
        (r'Brunnenu\.|Brunnen', 'befund'), (r'Latrinenbefunden?|Latrine', 'befund'),
        (r'Lagervorstadt|Vorstadt', 'befund'), (r'Töpferei', 'befund'), (r'Vicus', 'befund'),
        (r'Retentura|Legionslager', 'befund'), (r'Aquädukt', 'befund'),

        # Archaeological Vessels & Objects (Fund)
        (r'Einhenkelkrüge|Einhenkelkrug', 'fund'), (r'Zweihenkelkrüge|Zweihenkelkrug', 'fund'),
        (r'Glanztonwarebecher|Becher', 'fund'), (r'Terra\s+[Ss]igillata|Sigillaten', 'fund'),
        (r'Schälchen|Schale', 'fund'), (r'Statuette(?:\s+des\s+Mars\s+Ultor)?', 'fund'), (r'Helm', 'fund'),
        (r'Oberkörperpanzer|Lorica\s+segmentata|Panzerung', 'fund'), (r'Beinschienen|Beinschiene', 'fund'),
        (r'Armbrustspiralfibel|Emailscheibenfibel|Scheibenfibel|Fibel', 'fund'),
        (r'Sesterzen|Sesterz', 'fund'), (r'Denare|Denar|Denarius', 'fund'), (r'Dupondius|Dupondii', 'fund'),
        (r'Aureus|Aurei', 'fund'), (r'Folles|Follis', 'fund'), (r'Münzen|Münze', 'fund'),
        (r'Niederbieber\d*[a-z]?', 'fund'), (r'Gellep\d*', 'fund'), (r'RSNB\d*', 'fund'),
        (r'Scherben?|Wandscherbe|Randscherbe', 'fund'),

        # Century & Dating Expressions (Datierung)
        (r'Ha\s+C|Hallstatt\s+C', 'datierung'), (r'Frühlat\.|Frühlatènezeit|frühlatènezeitl\.', 'datierung'),
        # Century & Dating Expressions (Datierung)
        (r'spätbronzezeitlich|spätbronze-', 'datierung'), (r'früheisenzeitlich|früheisenzeitl\.', 'datierung'),
        (r'mittleren\s+Eisenzeit|mittlere\s+Eisenzeit', 'datierung'), (r'frühe\s+Eisenzeit', 'datierung'),
        (r'neolithisch|neolith\.', 'datierung'), (r'metallzeitlich|metallzeitl\.', 'datierung'),
        (r'frührömisch|frühröm\.', 'datierung'), (r'eisenzeitlich|eisenzeitl\.', 'datierung'),
        (r'Ha\s+C|Hallstatt\s+C', 'datierung'), (r'Frühlat\.|Frühlatènezeit|frühlatènezeitl\.', 'datierung'),
        (r'urnenfelder-(?:\s*bis\s*)?', 'datierung'), (r'jüngereisenzeitl\.|jüngereisenzeitlich', 'datierung'),
        (r'früheneuzeitl\.|früheneuzeitlich|frühe\s+Neuzeit|frühen\s+Neuzeit', 'datierung'),
        (r'mittelalterl\.|mittelalterlich', 'datierung'), (r'bandkeram\.|bandkeramisch', 'datierung'),
        (r'zweite\s+Hälfte\s*\d+\.\s*–\s*Anfang\s*\d+\.\s*Jh\.', 'datierung'),
        (r'\d+\.\s*/\s*\d+\.\s*Jh\.(?:\s*n\.\s*Chr\.)?', 'datierung'), (r'\d+\.\s*–\s*\d+\.\s*Jhs?\.', 'datierung'),
        (r'\d+\.\s*Jh\.', 'datierung'), (r'frühröm\.|spätröm\.|römerzeitl\.|röm\.', 'datierung'),
        (r'mittlere[rn]?\s+Kaiserzeit|spätere\s+Kaiserzeit|Kaiserzeit', 'datierung'),

        # Additional Structures & Befunde
        (r'Siedlung(?:sreste)?|Streugehöften|Gehöft', 'befund'), (r'Pfostengruben(?:verfüllungen)?|Pfostengrube', 'befund'),
        (r'Gruben(?:verfüllungen)?|Grube', 'befund'), (r'Befundstreuung', 'befund'),
        (r'röm\.\s+Straße|Straße|Via\s+Belgica', 'befund'), (r'Erdkeller', 'befund'), (r'Pfosten', 'befund'),
        (r'Speicher', 'befund'), (r'Brennöfen|Brennofen|Ofen', 'befund'), (r'Werkhütten|Hütte', 'befund'),
        (r'Werkplätze|Werkplatz', 'befund'), (r'Gräben|Graben', 'befund'),
        (r'Materialentnahmebereiche|Materialentnahme', 'befund'), (r'Schützengraben', 'befund')
    ]

    spans = []
    for frag_text, category in fragments:
        clean_frag = frag_text.strip()
        if len(clean_frag) < 3 and clean_frag != "As": continue
        pattern = re.escape(clean_frag)
        word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + pattern + r')', re.IGNORECASE)
        for match in word_pattern.finditer(raw_text):
            start, end = match.span()
            if re.search(r'\b(keine|kein|ohne|keinerlei)\s+$', raw_text[:start], re.IGNORECASE):
                continue
            spans.append((start, end, category, clean_frag))

    for pat_str, category in GLOBAL_CONCEPT_PATTERNS:
        word_pattern = re.compile(r'(?<![a-zA-ZäöüÄÖÜß0-9])(?:' + pat_str + r')', re.IGNORECASE)
        for match in word_pattern.finditer(raw_text):
            start, end = match.span()
            if re.search(r'\b(keine|kein|ohne|keinerlei)\s+$', raw_text[:start], re.IGNORECASE):
                continue
            spans.append((start, end, category, raw_text[start:end]))

    def span_priority(s):
        cat_order = {'datierung': 5, 'befund': 4, 'fund': 3, 'aktivitaet': 2, 'ort': 1}
        return (cat_order.get(s[2], 0), (s[1] - s[0]))

    spans.sort(key=lambda s: (s[0], -span_priority(s)[0], -span_priority(s)[1]))

    filtered_spans = []
    last_end = 0
    for start, end, category, frag_text in spans:
        if start >= last_end:
            filtered_spans.append((start, end, category, frag_text))
            last_end = end

    # 4. Sort descending for right-to-left insertion
    filtered_spans.sort(key=lambda s: s[0], reverse=True)

    # 5. Insert tags right-to-left
    result_parts = []
    curr_pos = len(raw_text)

    for start, end, category, frag_text in filtered_spans:
        after_text = html.escape(raw_text[end:curr_pos])
        span_text = html.escape(raw_text[start:end])
        tagged_span = f'<mark class="{category}">{span_text}</mark>'
        
        result_parts.append(after_text)
        result_parts.append(tagged_span)
        curr_pos = start

    result_parts.append(html.escape(raw_text[:curr_pos]))
    annotated_text = "".join(reversed(result_parts))

    # Build HTML table for the right pane
    table_rows = []
    for idx, row in df.iterrows():
        page = html.escape(str(row.get('Seitenzahl', '-')))
        ort = html.escape(str(row.get('ort', '-')))
        kreis = html.escape(str(row.get('kreis', '-')))
        massnahme = html.escape(str(row.get('massnahme_id', '-')))
        datierung = html.escape(str(row.get('datierung_norm', '-')))
        befunde = html.escape(str(row.get('befunde_norm', '-')))
        funde = html.escape(str(row.get('funde_norm', '-')))
        autor = html.escape(str(row.get('autor', '-')))

        row_html = f"""
        <tr>
            <td><strong>S. {page}</strong></td>
            <td><span class="badge ort">{ort}</span> <br><small class="text-muted">{kreis}</small></td>
            <td><span class="badge aktivitaet">{massnahme}</span></td>
            <td><span class="badge datierung">{datierung}</span></td>
            <td><span class="badge befund">{befunde}</span></td>
            <td><span class="badge fund">{funde}</span></td>
            <td><span class="badge autor">{autor}</span></td>
        </tr>
        """
        table_rows.append(row_html)

    table_content = "".join(table_rows)

    css_styles = """
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 15px; background-color: #f4f6f9; color: #333; height: 100vh; display: flex; flex-direction: column; }
        h1 { margin: 0 0 10px 0; font-size: 20px; color: #1e293b; }
        
        .legend { display: flex; gap: 12px; margin-bottom: 12px; padding: 10px 15px; background-color: #fff; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 13px; }
        .legend-box { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
        
        .main-layout { display: flex; gap: 15px; flex: 1; min-height: 0; }
        
        .pane { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); display: flex; flex-direction: column; overflow: hidden; }
        .pane-text { flex: 1.2; }
        .pane-table { flex: 1.8; }
        
        .pane-header { padding: 10px 15px; background: #eef2f6; border-bottom: 1px solid #cbd5e1; font-weight: bold; font-size: 14px; color: #334155; }
        .pane-body { padding: 15px; overflow-y: auto; flex: 1; }
        
        .text-content { white-space: pre-wrap; font-family: Georgia, serif; font-size: 15px; line-height: 1.7; }
        
        /* Table Styles */
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th { background: #f1f5f9; padding: 8px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #cbd5e1; z-index: 10; }
        td { padding: 8px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
        tr:hover { background-color: #f8fafc; }
        
        /* Badges & Marks */
        mark.aktivitaet, .badge.aktivitaet { background-color: #cce5ff; color: #004085; padding: 2px 6px; border-radius: 4px; font-weight: 600; border: 1px solid #b8daff; display: inline-block; }
        mark.befund, .badge.befund { background-color: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 4px; font-weight: 600; border: 1px solid #f5c6cb; display: inline-block; }
        mark.fund, .badge.fund { background-color: #d1e7dd; color: #0f5132; padding: 2px 6px; border-radius: 4px; font-weight: 600; border: 1px solid #badbcc; display: inline-block; }
        mark.datierung, .badge.datierung { background-color: #fff3cd; color: #664d03; padding: 2px 6px; border-radius: 4px; font-weight: 600; border: 1px solid #ffecb5; display: inline-block; }
        mark.ort, .badge.ort { background-color: #e2e3e5; color: #1b1e21; padding: 2px 6px; border-radius: 4px; font-weight: 700; border: 1px solid #d6d8db; display: inline-block; }
        mark.autor, .badge.autor { background-color: #e2d9f3; color: #491217; padding: 2px 6px; border-radius: 4px; font-weight: 600; border: 1px solid #d3c4e3; display: inline-block; }
        
        .text-muted { color: #64748b; font-size: 11px; }
    </style>
    """

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Archäologische Text-Extraktion Preview ({os.path.basename(csv_path)})</title>
    {css_styles}
</head>
<body>
    <h1>Archäologische Extraktions-Vorschau ({os.path.basename(csv_path)})</h1>
    
    <div class="legend">
        <div class="legend-item"><span class="legend-box" style="background: #cce5ff; border: 1px solid #b8daff;"></span> Blau: Aktivität / Maßnahme</div>
        <div class="legend-item"><span class="legend-box" style="background: #f8d7da; border: 1px solid #f5c6cb;"></span> Rot: Befund</div>
        <div class="legend-item"><span class="legend-box" style="background: #d1e7dd; border: 1px solid #badbcc;"></span> Grün: Fund</div>
        <div class="legend-item"><span class="legend-box" style="background: #fff3cd; border: 1px solid #ffecb5;"></span> Gelb: Datierung</div>
        <div class="legend-item"><span class="legend-box" style="background: #e2e3e5; border: 1px solid #d6d8db;"></span> Grau: Ort / Kreis</div>
        <div class="legend-item"><span class="legend-box" style="background: #e2d9f3; border: 1px solid #d3c4e3;"></span> Lila: Autor</div>
    </div>
    
    <div class="main-layout">
        <div class="pane pane-text">
            <div class="pane-header">📄 Rohtext mit Farbhervorhebung</div>
            <div class="pane-body">
                <div class="text-content">{annotated_text}</div>
            </div>
        </div>
        
        <div class="pane pane-table">
            <div class="pane-header">📊 Extrahiertes Ergebnis (Tabelle)</div>
            <div class="pane-body">
                <table>
                    <thead>
                        <tr>
                            <th>Seite</th>
                            <th>Ort / Kreis</th>
                            <th>Aktivität / Maßnahme</th>
                            <th>Datierung</th>
                            <th>Befunde</th>
                            <th>Funde</th>
                            <th>Autor</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_content}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

    with open(html_out_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Preview erfolgreich generiert unter: {html_out_path}")

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        c_path, r_path, o_path = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        # Default fallback to 1970
        c_path = r"e:\AIBJB\LVR_1970_Split_Fixed.csv"
        r_path = r"e:\AIBJB\LVR_1970_raw_text.txt"
        o_path = r"e:\AIBJB\LVR_1970_Highlighted_Preview.html"
    
    create_highlighted_html(c_path, r_path, o_path)
