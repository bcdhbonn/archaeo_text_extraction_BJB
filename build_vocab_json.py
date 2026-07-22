import os
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from rdflib import Graph, RDF, SKOS

vocab_dir = r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\Vokabulare"
if not os.path.exists(vocab_dir):
    vocab_dir = os.path.dirname(os.path.abspath(__file__))

output_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocabularies.json")

files = {
    "Datierung": "HECTOR_Epoch.ttl",
    "Befund": "LVR_Befundansprachen.ttl",
    "Fund": "LVR_Fundansprachen.ttl"
}

data = {
    "Datierung": [],
    "Befund": [],
    "Fund": []
}

for cat_name, fname in files.items():
    fpath = os.path.join(vocab_dir, fname)
    if not os.path.exists(fpath):
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    
    if os.path.exists(fpath):
        print(f"📖 Parsing SKOS ({cat_name}): {fname}...")
        g = Graph()
        try:
            g.parse(fpath, format="turtle")
            seen = set()
            for concept in g.subjects(RDF.type, SKOS.Concept):
                pref_labels = []
                for label in g.objects(concept, SKOS.prefLabel):
                    lang = getattr(label, 'language', None)
                    if lang in [None, 'de', 'nl']:
                        term = str(label).strip()
                        if term:
                            pref_labels.append(term)

                if pref_labels:
                    main_term = pref_labels[0]
                    if main_term.lower() in seen:
                        continue
                    seen.add(main_term.lower())

                    alt_labels = []
                    for alt in g.objects(concept, SKOS.altLabel):
                        lang = getattr(alt, 'language', None)
                        if lang in [None, 'de', 'nl']:
                            alt_str = str(alt).strip()
                            if alt_str and alt_str.lower() != main_term.lower():
                                alt_labels.append(alt_str)

                    data[cat_name].append({
                        "term": main_term,
                        "alt": alt_labels[:5],
                        "category": cat_name
                    })
        except Exception as e:
            print(f"⚠️ Error parsing {fname}: {e}")

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ SKOS JSON vocabulary saved to: {output_json}")
print(f"  Datierung concepts: {len(data['Datierung'])}")
print(f"  Befund concepts:    {len(data['Befund'])}")
print(f"  Fund concepts:      {len(data['Fund'])}")
