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
            
            # Try to detect actual printed book page number
            txt_full = page.extract_text() or ""
            m_book = re.search(r'\b(\d{3,4})\b', txt_full[:120])
            book_page_label = m_book.group(1) if m_book else str(pdf_page_num)
            
            # 2-Column layout detection
            w, h = page.width, page.height
            top_y, bottom_y = h * 0.03, h * 0.97
            mid_x = w / 2.0
            
            left_crop = page.crop((0, top_y, mid_x, bottom_y))
            right_crop = page.crop((mid_x, top_y, w, bottom_y))
            
            left_text = left_crop.extract_text() or ""
            right_text = right_crop.extract_text() or ""
            
            if len(left_text.strip()) > 50 and len(right_text.strip()) > 50:
                page_text = f"--- SEITE {book_page_label} ---\n{left_text.strip()}\n\n{right_text.strip()}"
            else:
                full_crop = page.crop((0, top_y, w, bottom_y))
                page_text = f"--- SEITE {book_page_label} ---\n{(full_crop.extract_text() or '').strip()}"
                
            extracted_pages.append(page_text)
    
    full_text = "\n\n".join(extracted_pages)
    
    # Bereinigung: Silbentrennung am Zeilenende zusammenfügen
    full_text = re.sub(r'(\b[a-zäöüßA-ZÄÖÜ]+)-\s*\n\s*([a-zäöüßA-ZÄÖÜ]+)', r'\1\2', full_text)
    
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
