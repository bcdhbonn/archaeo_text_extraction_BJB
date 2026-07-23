# 🏛️ ArchaeoExtract-Rhineland

**Automated Text Mining, SKOS Normalization & Tiered GIS Georeferencing for the *Bonner Jahrbücher* (BJB)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Gemini 2.5](https://img.shields.io/badge/AI-Gemini%202.5-orange.svg)](https://ai.google.dev/)
[![SKOS Vocabularies](https://img.shields.io/badge/Vocabularies-HECTOR%20SKOS-green.svg)](https://github.com/bcdhbonn/hector-editor-skos)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Archaeologist's Overview

**ArchaeoExtract-Rhineland** is a domain-tailored AI assistant and interactive web application designed to help archaeologists extract, review, and georeference excavation reports from the *Bonner Jahrbücher* (BJB).

It automatically turns unstructured OCR reports into structured excavation records:
* 🟨 **Chronologies (`Datierung`)**: Roman emperors (*Augustus*, *Caligula*), cultural phases (*Michelsberger Kultur*, *Hallstatt C*), and century spans.
* 🟥 **Features (`Befund`)**: Immovable structures (*Wasserleitung*, *Fundamentplatte*, *Pfostengrube*, *Villa rustica*).
* 🟩 **Artifacts (`Fund`)**: Movable finds (*Terra Sigillata*, *Niederbieber 67b*, *Sesterz*, *Mahlstein*).
* 🗺️ **Locations (`Ort / GIS`)**: Automatic 3-tier georeferencing linked to interactive maps and QGIS export.

---

## 🔗 Data Sources & Repositories

* **Digitized BJB Excavation Reports**: [Heidelberg University Library BJB Archive](https://journals.ub.uni-heidelberg.de/index.php/bjb/index)
* **Controlled SKOS Vocabularies**: [BCDH HECTOR Editor SKOS Vocabularies](https://github.com/bcdhbonn/hector-editor-skos) (*Rhineland Archaeological Graph Authority*)

---

## ⚡ Quickstart Guide

### 1. Installation
Install required Python packages:

```bash
pip install pandas google-genai rdflib pdfplumber tqdm
```

Set your Google Gemini API key:
```bash
# PowerShell
$env:GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
```

### 2. Run Extraction on BJB Volume
Extract excavation reports from any volume (e.g., `1984.pdf`):

```bash
python Extraction_pipline_BJB.py 1984.pdf
```

### 3. Launch Annotation Editor
Rebuild and open the interactive standalone editor:

```bash
python build_standalone_editor.py
```

Then open **[`annotation_editor.html`](annotation_editor.html)** in your web browser.

---

## 🛠️ Archaeologist Workflows in the Editor

1. **📄 Interactive Reader View**: Inspect full report text alongside color-coded entity badges (`Datierung`, `Befund`, `Fund`).
2. **📖 1-Click SKOS Concept Proposal**: Highlight any unmapped term in the text to propose a new SKOS concept, select a `skos:broader` parent concept, and instantly re-scan the entire document.
3. **🗺️ 3-Tier GIS Map Verification**:
   - 🟢 **Tier 1 (Gazetteer)**: Auto-verified coordinates from Rhineland Gazetteer.
   - 🟡 **Tier 2 (GeoNames)**: Candidate search results with 1-click verification.
   - 🟠 **Tier 3 (Gemini AI)**: Estimated pins for local field names (*"Merzenicher Heide"*) with drag-and-drop pinpointing.
4. **📥 QGIS Export**: Click **`[ 📥 QGIS GeoJSON Export ]`** to download ready-to-use spatial layers (`.geojson`) for QGIS or ArcGIS.

---

## 📚 Technical Documentation

For complete developer specifications, regex OCR algorithms, and pipeline architecture, please read the **[Technical Wiki (WIKI.md)](WIKI.md)**.
