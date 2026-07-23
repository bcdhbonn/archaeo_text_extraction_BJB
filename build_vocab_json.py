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

vocab_file = os.path.join(vocab_dir, "arch_vocab_rhineland.ttl")
if not os.path.exists(vocab_file):
    vocab_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch_vocab_rhineland.ttl")

data = {
    "Datierung": [],
    "Befund": [],
    "Fund": []
}

if os.path.exists(vocab_file):
    print(f"📖 Parsing SKOS vocabulary from: {os.path.basename(vocab_file)}...")
    g = Graph()
    try:
        g.parse(vocab_file, format="turtle")
        
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

        seen_terms = {'Datierung': set(), 'Befund': set(), 'Fund': set()}

        for concept in g.subjects(RDF.type, SKOS.Concept):
            cat_name = get_category(concept)
            if not cat_name:
                continue

            pref_labels = []
            for label in g.objects(concept, SKOS.prefLabel):
                lang = getattr(label, 'language', None)
                if lang in [None, 'de', 'nl']:
                    term = str(label).strip()
                    if term:
                        pref_labels.append(term)

            if pref_labels:
                main_term = pref_labels[0]
                if main_term.lower() in seen_terms[cat_name]:
                    continue
                seen_terms[cat_name].add(main_term.lower())

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
        print(f"⚠️ Error parsing {vocab_file}: {e}")

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ SKOS JSON vocabulary saved to: {output_json}")
print(f"  Datierung concepts: {len(data['Datierung'])}")
print(f"  Befund concepts:    {len(data['Befund'])}")
print(f"  Fund concepts:      {len(data['Fund'])}")
