# Archäologische Text-Extraktion (Bonner Jahrbücher)

Dieses Repository enthält eine automatisierte Pipeline zur Extraktion von archäologischen Fundstellen, Befunden und Maßnahmen aus den digitalisierten Berichten der **"Bonner Jahrbücher"** (LVR).

Die Extraktion erfolgt sprachgesteuert mittels der **Google Gemini API** (`gemini-2.5-flash-lite`), während historische Begriffe mithilfe eines lokalen SKOS-Vokabulars normalisiert werden.

---

## Repository-Struktur

* **`Extraction_pipline_BJB.py`**: Das Hauptskript zur Text-Extraktion. Es liest wahlweise ein PDF ein, bereinigt den Text (entfernt z.B. Kopfzeilen und Abbildungsunterschriften) und sendet die Seiten an die Gemini API. Die extrahierten Daten werden strukturiert als semikolon-separierte CSV-Datei ausgegeben.
* **`archaevocabNLDE.ttl`**: Das archäologische SKOS-Vokabular (im Turtle-Format), das zur Normalisierung von Zeitstellungen, Funden und Befunden verwendet wird.
* **`LVR_1970_raw_text.txt`**: Ein beispielhafter extrahierter Rohtext der verarbeiteten Seiten.
* **`LVR_1970_Split_Fixed.csv`**: Die finale, bereinigte und strukturierte Export-Tabelle.

---

## Voraussetzungen & Installation

Zur Ausführung der Skripte wird Python 3.10+ benötigt. 

Installieren Sie die notwendigen Abhängigkeiten über `pip`:

```bash
pip install pandas google-genai tqdm rdflib pdfplumber
```

---

## Konfiguration

### 1. API Key hinterlegen
Um die Gemini API nutzen zu können, muss ein Google API Key vorliegen. Setzen Sie diesen am besten als Umgebungsvariable:

**Unter Windows (PowerShell):**
```powershell
$env:GOOGLE_API_KEY="IHR_API_KEY_HIER"
```

**Unter Linux/macOS:**
```bash
export GOOGLE_API_KEY="IHR_API_KEY_HIER"
```

*Hinweis: Wenn keine Umgebungsvariable gesetzt ist, nutzt das Skript einen vordefinierten Fallback-Key.*

### 2. Pfade im Skript anpassen
Öffnen Sie `Extraction_pipline_BJB.py` und passen Sie im Abschnitt `1. KONFIGURATION` die Pfade an:
* `pdf_base_dir`: Der Ordner, in dem Ihre PDF-Dateien liegen.
* `filename`: Der Dateiname des zu verarbeitenden PDFs (z. B. `1970.pdf`).
* `START_PAGE` / `END_PAGE`: Der Seitenbereich innerhalb des PDFs, der verarbeitet werden soll (0-indiziert im Code).

---

## Workflow: Ausführung der Pipeline

### Extraktion starten
Führen Sie das Extraktionsskript aus:
```bash
python Extraction_pipline_BJB.py
```
* **PDF-Modus**: Wenn das PDF gefunden wird, liest das Skript die Seiten ein, speichert den Rohtext als Sicherung (`LVR_[Jahr]_raw_text.txt`) und startet die KI-Extraktion.
* **Rohtext-Fallback**: Falls das PDF nicht lokal vorhanden ist, aber die entsprechende `LVR_[Jahr]_raw_text.txt` im selben Verzeichnis liegt, lädt das Skript die Seiten direkt aus dem Rohtext. Dies spart API-Kosten und ermöglicht Offline-Tests.

Das Ergebnis wird in eine Datei namens `LVR_[Jahr]_Split_Fixed.csv` geschrieben.

---

## Wichtige Besonderheiten der Extraktion

* **Abbildungsunterschriften**: Das Skript filtert über eine Regex-Prüfung in `clean_text` Bildunterschriften (z.B. mit Maßstabsangaben) heraus, damit diese nicht fälschlicherweise als archäologische Befunde klassifiziert werden und Seitenübergänge nicht stören.
* **Objektreferenzen**: Bildnummerierungen innerhalb der Einträge (z. B. `(Bild 22,5)`) werden bewusst im Fließtext der Funde/Befunde belassen und nicht als eigenständige Maßnahmen extrahiert.
