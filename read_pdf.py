#!/usr/bin/env python3
"""
read_pdf.py - Schnelles Einlesen von PDF-Seiten der Bonner Jahrbücher (BJB).
Unterstützt sowohl PDF-Seitennummern (z.B. 1 bis 90) als auch gedruckte Buchseitenzahlen (z.B. 598 bis 620).
"""

import sys
import os
import re

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pdfplumber

PDF_BASE_DIR = r"D:\Sciebo\BCDH_Projektbox\Projekte\BonnerJahrbuecher_etxract_2026\BJB_PDF_1970_2014"

def find_pdf(filename):
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    
    # Check in PDF_BASE_DIR recursively
    if os.path.exists(PDF_BASE_DIR):
        for root, dirs, files in os.walk(PDF_BASE_DIR):
            for f in files:
                if f.lower() == filename.lower() or f.lower() == f"{filename.lower()}.pdf":
                    return os.path.join(root, f)
    
    # Check current directory
    if os.path.exists(filename):
        return os.path.abspath(filename)
    if os.path.exists(f"{filename}.pdf"):
        return os.path.abspath(f"{filename}.pdf")
    
    return None

def extract_pdf(filename, start_page=1, end_page=None):
    pdf_path = find_pdf(filename)
    if not pdf_path:
        print(f"❌ PDF-Datei «{filename}» wurde nicht gefunden!")
        print(f"   Gesucht in: {PDF_BASE_DIR}")
        return None

    print(f"📖 Öffne PDF: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pdf_pages = len(pdf.pages)
        print(f"   Gesamte PDF-Seiten: {total_pdf_pages}")
        
        # Check if the requested start_page is a printed book page (e.g. > total_pdf_pages)
        pdf_start_idx = 0
        pdf_end_idx = total_pdf_pages
        
        if start_page > total_pdf_pages:
            print(f"🔍 Suche gedruckte Buchseitenzahl {start_page} im PDF...")
            target_page_found = False
            for idx, p in enumerate(pdf.pages):
                txt = p.extract_text() or ""
                # Look for printed page numbers at top or bottom (e.g. "599", "598")
                header_footer = txt[:150] + " " + txt[-150:]
                m = re.findall(r'\b(\d{2,4})\b', header_footer)
                if str(start_page) in m:
                    pdf_start_idx = idx
                    target_page_found = True
                    break
            
            if not target_page_found:
                # Try finding offset from first page with a number
                for idx, p in enumerate(pdf.pages[:10]):
                    txt = p.extract_text() or ""
                    m = re.search(r'\b(\d{3,4})\b', txt[:150])
                    if m:
                        printed_start = int(m.group(1))
                        estimated_idx = max(0, min(total_pdf_pages - 1, idx + (start_page - printed_start)))
                        pdf_start_idx = estimated_idx
                        print(f"ℹ️ Geschätzte Position für Buchseite {start_page}: PDF-Seite {pdf_start_idx + 1}")
                        target_page_found = True
                        break
            else:
                print(f"✓ Buchseite {start_page} entspricht PDF-Seite {pdf_start_idx + 1}")
                
            if end_page is not None:
                if end_page >= start_page:
                    page_diff = end_page - start_page
                    pdf_end_idx = min(total_pdf_pages, pdf_start_idx + page_diff + 1)
                else:
                    pdf_end_idx = min(total_pdf_pages, pdf_start_idx + 10)
            else:
                pdf_end_idx = min(total_pdf_pages, pdf_start_idx + 15)
        else:
            # Standard PDF page index (1-based)
            pdf_start_idx = max(0, start_page - 1)
            pdf_end_idx = min(total_pdf_pages, end_page) if end_page is not None else total_pdf_pages

        print(f"📄 Lese PDF-Seiten {pdf_start_idx + 1} bis {pdf_end_idx} (von {total_pdf_pages})...")
        
        extracted_pages = []
        for p_idx in range(pdf_start_idx, pdf_end_idx):
            page = pdf.pages[p_idx]
            pdf_page_num = p_idx + 1
            
            txt_full = page.extract_text() or ""
            m_book = re.search(r'\b(\d{3,4})\b', (txt_full[:150] + " " + txt_full[-150:]))
            book_page_label = m_book.group(1) if m_book else str(pdf_page_num)
            
            # Extract words with coordinates to determine layout and reflow paragraphs
            words = page.extract_words()
            # Filter top header / running heads (top < 48)
            words = [w for w in words if w['top'] >= 48 and w['bottom'] <= page.height - 35]
            
            center_start = page.width * 0.35
            center_end = page.width * 0.65
            
            wide_center_crossings = 0
            for w in words:
                if w['text'].startswith('Abb.') or w['text'].startswith('Taf.'):
                    continue
                if (w['x1'] - w['x0']) > page.width * 0.48:
                    wide_center_crossings = 99
                    break
                if w['x0'] < center_start and w['x1'] > center_end:
                    wide_center_crossings += 1
                    
            is_two_col = False
            best_gutter_x = None
            
            if wide_center_crossings <= 2:
                max_gutter = 0
                non_banner = [w for w in words if not w['text'].startswith('Abb.') and (w['x1'] - w['x0']) < 140]
                best_cx = None
                min_cross = 999
                max_gut = 0
                for cx in range(int(center_start), int(center_end), 2):
                    crossing = sum(1 for w in non_banner if w['x0'] < cx and w['x1'] > cx)
                    min_l = min([cx - w['x1'] for w in non_banner if w['x1'] < cx] or [0])
                    min_r = min([w['x0'] - cx for w in non_banner if w['x0'] > cx] or [0])
                    gut = min_l + min_r
                    if crossing < min_cross or (crossing == min_cross and gut > max_gut):
                        min_cross = crossing
                        max_gut = gut
                        best_cx = cx
                if max_gut >= 6.0 and best_cx is not None and min_cross <= 3:
                    is_two_col = True
                    best_gutter_x = best_cx

            def assemble_col(col_words):
                if not col_words: return ""
                lines = []
                cur_line = []
                cur_y = None
                for w in sorted(col_words, key=lambda x: (round(x['top'] / 3.5) * 3.5, x['x0'])):
                    y = round(w['top'] / 3.5) * 3.5
                    if cur_y is None or abs(y - cur_y) <= 3.5:
                        cur_line.append(w)
                        if cur_y is None: cur_y = y
                    else:
                        cur_line.sort(key=lambda x: x['x0'])
                        lines.append((cur_y, " ".join(x['text'] for x in cur_line)))
                        cur_line = [w]
                        cur_y = y
                if cur_line:
                    cur_line.sort(key=lambda x: x['x0'])
                    lines.append((cur_y, " ".join(x['text'] for x in cur_line)))
                    
                paras = []
                cur_para = ""
                for y, l_text in lines:
                    l_text = l_text.strip()
                    if not cur_para:
                        cur_para = l_text
                    else:
                        if re.search(r'[\wöäüß]-[­]?$', cur_para):
                            cur_para = re.sub(r'-[­]?$', '', cur_para) + l_text
                        else:
                            cur_para += " " + l_text
                    
                    if l_text.startswith("Verbleib:") or (re.search(r'[.!?]$', l_text) and (re.match(r'^\d+\.\s+[A-ZÄÖÜ]', l_text) or re.match(r'^[A-ZÄÖÜ][a-zäöüß]+,\s+[A-ZÄÖÜ]', l_text))):
                        paras.append(cur_para)
                        cur_para = ""
                if cur_para:
                    paras.append(cur_para)
                return "\n\n".join(paras)

            if is_two_col and best_gutter_x:
                # Detect Dividers across the gutter (centered headings, figures)
                page_lines = {}
                for w in words:
                    y = round(w['top'] / 4.0) * 4.0
                    page_lines.setdefault(y, []).append(w)
                    
                dividers = []
                for y in sorted(page_lines.keys()):
                    row = sorted(page_lines[y], key=lambda x: x['x0'])
                    row_text = " ".join(x['text'] for x in row)
                    min_x = row[0]['x0']
                    max_x = row[-1]['x1']
                    
                    if max_x < best_gutter_x - 10 or min_x > best_gutter_x + 10:
                        continue
                        
                    touches_left_margin = (min_x < page.width * 0.22)
                    touches_right_margin = (max_x > page.width * 0.78)
                    
                    is_figure_caption = (re.match(r'^(?:Abb\.|Taf\.|Karte|Fig\.)\s*\d+', row_text, re.I) is not None)
                    is_center_heading = (not touches_left_margin and not touches_right_margin and len(row) <= 6)
                    is_wide_banner = (not touches_left_margin and len(row) <= 8 and any(k in row_text.lower() for k in ['zeit', 'epoche', 'ausgrabung', 'jahrhundert']))
                    
                    if is_figure_caption or is_center_heading or is_wide_banner:
                        div_top = min(w['top'] for w in row)
                        div_bot = max(w['bottom'] for w in row)
                        dividers.append((div_top, div_bot, row_text, row))
                        
                band_ranges = []
                curr_y = 0
                for div_top, div_bot, div_title, div_row in dividers:
                    if div_top > curr_y + 8:
                        band_ranges.append(('columns', curr_y, div_top - 2, None))
                    band_ranges.append(('banner', div_top - 2, div_bot + 2, div_row))
                    curr_y = div_bot + 2
                band_ranges.append(('columns', curr_y, 9999, None))
                
                reconstructed_bands = []
                for b_type, y_start, y_end, b_content in band_ranges:
                    if b_type == 'banner':
                        b_text = assemble_col(b_content)
                        if b_text: reconstructed_bands.append(b_text)
                    else:
                        b_words = [w for w in words if y_start <= w['top'] < y_end]
                        if not b_words: continue
                        left_b = [w for w in b_words if w['x1'] <= best_gutter_x]
                        right_b = [w for w in b_words if w['x0'] >= best_gutter_x]
                        lt = assemble_col(left_b)
                        rt = assemble_col(right_b)
                        if lt: reconstructed_bands.append(lt)
                        if rt: reconstructed_bands.append(rt)
                        
                page_body = "\n\n".join(reconstructed_bands)
            else:
                page_body = assemble_col(words)
                
            page_text = f"--- SEITE {book_page_label} ---\n\n{page_body.strip()}"
            extracted_pages.append(page_text)
    
    full_text = "\n\n".join(extracted_pages)
    
    # OCR Glued words & punctuation cleanup
    full_text = re.sub(r'([a-zäöüß0-9]{2,})([.!?])([A-ZÄÖÜ])', r'\1\2 \3', full_text)
    full_text = re.sub(r'([a-zäöüß0-9])([,;:])([A-ZÄÖÜa-zäöüß0-9])', r'\1\2 \3', full_text)
    full_text = re.sub(r'([a-zäöüß0-9])([–—])([A-ZÄÖÜa-zäöüß])', r'\1 \2 \3', full_text)
    full_text = re.sub(r'([a-zäöüß]{3,})(bei|auf|in|im|aus|nach|vor|unter|über|vom|von|mit|durch|zu|zur|zum|und|oder)\s+([A-ZÄÖÜ])', r'\1 \2 \3', full_text)
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    out_filename = f"LVR_{base_name}_extracted.txt"
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_filename)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        
    print(f"\n✅ Erfolgreich extrahiert!")
    print(f"📁 Gespeichert als: {out_path}")
    print(f"📊 Umfang: {len(full_text.split())} Wörter, {len(extracted_pages)} Seiten.")
    print(f"💡 Diese Datei kann nun im Annotations-Editor über den Button «📂 Text öffnen» direkt geladen werden.")
    
    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung:")
        print("  python read_pdf.py <jahrgang_oder_datei> [start_seite] [end_seite]")
        print("\nBeispiele:")
        print("  python read_pdf.py 1984.pdf 598 605     (mit gedruckten Buchseiten)")
        print("  python read_pdf.py 1984.pdf 1 10        (mit PDF-Seitenzahlen)")
        print("  python read_pdf.py 1999 1 20")
        sys.exit(1)
        
    fn = sys.argv[1]
    sp = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    ep = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    extract_pdf(fn, sp, ep)
