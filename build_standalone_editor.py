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

# 2. Process documents (1973 and 1970)
docs_data = {}

def process_document(csv_fname, txt_fname, doc_key):
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

        def push_frag(val_str, cat_name, skos_val):
            for clean in parse_raw_fragments(val_str):
                raw_adj, noun_rem = split_adjective_noun(clean)
                if raw_adj and noun_rem:
                    fragments.append((raw_adj, 'datierung', row_id, 'Datierung (SKOS)'))
                    fragments.append((noun_rem, cat_name, row_id, skos_val))
                else:
                    fragments.append((clean, cat_name, row_id, skos_val))

        push_frag(mid, 'aktivitaet', str(row.get('massnahme_id', '')))
        push_frag(str(row.get('befunde_roh', '')), 'befund', str(row.get('befunde_norm', '')))
        push_frag(str(row.get('funde_roh', '')), 'fund', str(row.get('funde_norm', '')))
        push_frag(str(row.get('datierung_roh', '')), 'datierung', str(row.get('datierung_norm', '')))
        push_frag(str(row.get('ort', '')), 'ort', str(row.get('ort', '')))

    # Find spans in text
    spans = []
    for frag_text, category, row_id, skos_norm in fragments:
        pattern = re.escape(frag_text)
        for match in re.finditer(pattern, raw_text):
            start, end = match.span()
            spans.append({
                "start": start,
                "end": end,
                "category": category,
                "text": frag_text,
                "row_id": row_id,
                "skos": skos_norm
            })

    # Sort spans by start, then length descending
    spans.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))

    filtered_spans = []
    last_end = 0
    for s in spans:
        if s["start"] >= last_end:
            filtered_spans.append(s)
            last_end = s["end"]

    # Table rows formatting
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
        "raw_text": raw_text,
        "spans": filtered_spans,
        "table_rows": table_rows
    }

process_document("LVR_1973_Split_Fixed.csv", "LVR_1973_cleaned.txt", "LVR_1973_cleaned.txt")
process_document("LVR_1970_Split_Fixed.csv", "LVR_1970_cleaned.txt", "LVR_1970_cleaned.txt")

vocab_json_str = json.dumps(vocab_data, ensure_ascii=False)
docs_json_str = json.dumps(docs_data, ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <title>Archäologische Extraktions-Vorschau & Text-Annotator</title>
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
        mark {{ border-radius: 4px; padding: 2px 5px; cursor: pointer; font-weight: 600; position: relative; transition: all 0.2s ease; display: inline; }}
        mark:hover {{ filter: brightness(0.92); box-shadow: 0 0 8px rgba(0,0,0,0.2); }}
        mark.aktivitaet {{ background-color: #dbeafe; color: #1e40af; border-bottom: 2px solid #3b82f6; }}
        mark.ort {{ background-color: #f1f5f9; color: #334155; border-bottom: 2px solid #64748b; }}
        mark.datierung {{ background-color: #fef9c3; color: #854d0e; border-bottom: 2px solid #eab308; }}
        mark.befund {{ background-color: #fee2e2; color: #991b1b; border-bottom: 2px solid #ef4444; }}
        mark.fund {{ background-color: #dcfce7; color: #166534; border-bottom: 2px solid #10b981; }}
        
        mark.selected-pulse {{ animation: pulseHighlight 1.5s ease-in-out infinite; transform: scale(1.05); display: inline-block; }}
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
        tr.table-row.active-row {{ background-color: #e0f2fe; border-left: 4px solid #0284c7; }}

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
        
        .vocab-list {{ display: flex; flex-direction: column; gap: 8px; max-height: 420px; overflow-y: auto; }}
        .vocab-item {{ background: #ffffff; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 8px; cursor: grab; transition: all 0.2s ease; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }}
        .vocab-item:hover {{ border-color: #0284c7; background: #f0f9ff; }}
        .vocab-item .term-title {{ font-weight: bold; font-size: 14px; color: #0f172a; }}
        .vocab-item .term-alt {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
        .vocab-item .btn-assign {{ font-size: 11px; padding: 4px 10px; background: #0284c7; border: none; border-radius: 5px; color: white; cursor: pointer; font-weight: bold; }}
        .vocab-item .btn-assign:hover {{ background: #0369a1; }}

        /* Floating Selection Popup */
        #selectionTooltip {{ position: absolute; display: none; background: #ffffff; border: 1px solid #0284c7; padding: 8px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); z-index: 100; gap: 6px; }}
        #selectionTooltip button {{ padding: 6px 12px; font-size: 12px; font-weight: bold; border-radius: 6px; cursor: pointer; }}

        /* Mark Editor Modal / Card */
        .anno-card {{ background: #ffffff; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 6px; font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .anno-header {{ display: flex; justify-content: space-between; align-items: center; font-weight: bold; font-size: 12px; color: #64748b; }}
        .anno-text {{ color: #0f172a; font-style: italic; background: #f8fafc; padding: 6px 10px; border-radius: 4px; margin-top: 4px; border: 1px solid #f1f5f9; }}
        .anno-skos {{ color: #0284c7; font-weight: bold; display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 13px; }}
        .btn-delete {{ background: #ef4444; color: white; border: none; padding: 4px 10px; border-radius: 5px; font-size: 11px; cursor: pointer; font-weight: bold; }}
        .btn-delete:hover {{ background: #dc2626; }}

        .toast {{ position: fixed; bottom: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 200; }}
    </style>
</head>
<body>

    <!-- Header Navigation -->
    <header>
        <h1>🏛️ Archäologische Extraktions-Vorschau & Text-Annotator</h1>
        <div class="header-controls">
            <select id="docSelect" onchange="loadDocument(this.value)">
                <option value="LVR_1973_cleaned.txt">LVR 1973 (PDF S. 70-94)</option>
                <option value="LVR_1970_cleaned.txt">LVR 1970</option>
            </select>
            <button onclick="document.getElementById('fileInput').click()">📄 Eigene Datei öffnen</button>
            <input type="file" id="fileInput" style="display:none" onchange="handleFileUpload(event)">
            
            <button class="btn-success" onclick="exportCSV()">💾 CSV Export</button>
            <button class="btn-primary" onclick="exportJSON()">📄 JSON Export</button>
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

        <!-- Right Pane: Sidebar -->
        <div class="pane pane-sidebar">
            <div class="sidebar-tabs">
                <div class="tab-btn active" onclick="switchTab('table')">📊 Extraktions-Tabelle</div>
                <div class="tab-btn" onclick="switchTab('vocab')">📚 SKOS Vokabular</div>
                <div class="tab-btn" onclick="switchTab('annotations')">📋 Annotationen (<span id="annoCount">0</span>)</div>
            </div>

            <!-- Tab 1: CSV Table View -->
            <div class="tab-content active" id="tabTable">
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

            <!-- Tab 2: SKOS Vocab Search -->
            <div class="tab-content" id="tabVocab">
                <div class="search-box">
                    <input type="text" id="vocabSearch" class="search-input" placeholder="🔍 SKOS Vokabular durchsuchen (z.B. Michelsberger, Schüssel, Krug, Mauer)..." oninput="filterVocab(this.value)">
                </div>
                <div class="vocab-list" id="vocabList"></div>
            </div>

            <!-- Tab 3: Annotations Manager -->
            <div class="tab-content" id="tabAnnotations">
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
    </div>

    <div class="toast" id="toast">Nachricht</div>

    <script>
        const EMBEDDED_VOCAB = {vocab_json_str};
        const EMBEDDED_DOCS = {docs_json_str};

        let currentCategory = 'aktivitaet';
        let rawVocabularies = EMBEDDED_VOCAB;
        let activeDocKey = 'LVR_1973_cleaned.txt';
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

        function setCategory(cat) {{
            currentCategory = cat;
            document.querySelectorAll('.cat-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector(`.cat-${{cat}}`).classList.add('active');
        }}

        function switchTab(tabName) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            if (tabName === 'table') {{
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('tabTable').classList.add('active');
            }} else if (tabName === 'vocab') {{
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('tabVocab').classList.add('active');
            }} else {{
                document.querySelectorAll('.tab-btn')[2].classList.add('active');
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
                
                const taggedSpan = `<mark class="${{s.category}}" id="${{markId}}" data-row="${{s.row_id}}" onclick="handleMarkClick(event, '${{markId}}')">${{spanText}}</mark>`;
                
                resultParts.push(afterText);
                resultParts.push(taggedSpan);
                currPos = s.start;

                annotations.push({{
                    id: markId,
                    text: rawText.substring(s.start, s.end),
                    category: s.category,
                    row_id: s.row_id,
                    skos: s.skos || null
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

        function highlightRowInText(rowId) {{
            document.querySelectorAll('.table-row').forEach(r => r.classList.remove('active-row'));
            const tblRow = document.getElementById(`tbl_${{rowId}}`);
            if (tblRow) tblRow.classList.add('active-row');

            const marks = document.querySelectorAll(`mark[data-row="${{rowId}}"]`);
            if (marks.length > 0) {{
                const firstMark = marks[0];
                firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                marks.forEach(m => {{
                    m.classList.add('selected-pulse');
                    setTimeout(() => m.classList.remove('selected-pulse'), 2000);
                }});
            }}
        }}

        function handleMarkClick(evt, markId) {{
            evt.stopPropagation();
            activeMarkId = markId;
            const markEl = document.getElementById(markId);
            if (markEl) {{
                const rowId = markEl.getAttribute('data-row');
                if (rowId) {{
                    document.querySelectorAll('.table-row').forEach(r => r.classList.remove('active-row'));
                    const tblRow = document.getElementById(`tbl_${{rowId}}`);
                    if (tblRow) {{
                        tblRow.classList.add('active-row');
                        tblRow.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                    }}
                }}
            }}
            switchTab('vocab');
            const anno = annotations.find(a => a.id === markId);
            if (anno) {{
                document.getElementById('vocabSearch').value = anno.text;
                filterVocab(anno.text);
            }}
        }}

        function filterVocab(query) {{
            const listEl = document.getElementById('vocabList');
            listEl.innerHTML = '';
            const q = query.toLowerCase().trim();

            let matches = [];
            for (let cat in rawVocabularies) {{
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

        function loadDocument(docName) {{
            activeDocKey = docName;
            document.getElementById('currentDocTitle').innerText = `📄 ${{docName}}`;
            if (EMBEDDED_DOCS[docName]) {{
                renderHighlightedText(EMBEDDED_DOCS[docName]);
                renderTable(EMBEDDED_DOCS[docName].table_rows || []);
                showToast(`Dokument ${{docName}} geladen`);
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
                    document.getElementById('textBody').innerText = raw;
                    document.getElementById('currentDocTitle').innerText = `📄 ${{file.name}}`;
                    annotations = [];
                    updateAnnotationsUI();
                    showToast(`Datei ${{file.name}} geladen`);
                }};
                reader.readAsText(file);
            }}
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
                tooltip.style.left = `${{rect.left + window.scrollX}}px`;
                tooltip.style.top = `${{rect.top + window.scrollY - 45}}px`;
                tooltip.style.display = 'flex';
            }}
        }}

        function annotateSelected(category) {{
            if (!selectedRange) return;
            const text = selectedRange.toString().trim();
            if (!text) return;

            const id = 'anno_' + Date.now();
            const mark = document.createElement('mark');
            mark.className = category;
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
                }}
                updateAnnotationsUI();
                showToast(`SKOS Begriff "${{skosTerm}}" zugewiesen!`);
            }}
        }}

        function handleDropOnText(evt) {{
            evt.preventDefault();
            const raw = evt.dataTransfer.getData('text/plain');
            if (raw) {{
                try {{
                    const item = JSON.parse(raw);
                    assignSKOSDirect(item.term);
                }} catch(e){{}}
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
                        <span>${{anno.category.toUpperCase()}}</span>
                        <button class="btn-delete" onclick="deleteAnnotation('${{anno.id}}')">Entfernen</button>
                    </div>
                    <div class="anno-text">"${{escapeHtml(anno.text)}}"</div>
                    ${{anno.skos ? `<div class="anno-skos">🏷️ ${{escapeHtml(anno.skos)}} (SKOS)</div>` : '<div style="color: #64748b; font-size: 11px;">Kein SKOS-Begriff zugewiesen</div>'}}
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
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }}

        // Init
        filterVocab('');
        loadDocument('LVR_1973_cleaned.txt');
    </script>
</body>
</html>
"""

editor_path = os.path.join(root_dir, "annotation_editor.html")
with open(editor_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"✅ Standalone Annotation Editor created at: {editor_path}")
