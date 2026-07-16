import json
import os
import re
import pandas as pd
from pyproj import Transformer
import matplotlib.pyplot as plt

csv_path = r"e:\AIBJB\LVR_1970_Split_Fixed.csv"
geojson_path = r"e:\AIBJB\geonames.geojson"
html_out_path = r"e:\AIBJB\map_1970.html"
# Save the static plot in the artifacts folder so the agent can show it to the user
img_out_path = r"C:\Users\langm\.gemini\antigravity-ide\brain\9e622e93-f23c-4482-b136-f924e7d6a9fd\map_1970_static.png"

# Setup coordinate transformer
# EPSG:31466 is DHDN / 3-degree Gauss-Kruger zone 2
transformer = Transformer.from_crs("epsg:31466", "epsg:4326", always_xy=True)

def load_geonames(path):
    if not os.path.exists(path):
        print(f"WARNUNG: GeoNames-Datei nicht gefunden unter {path}. Fallback wird verwendet.")
        return {}
    print("Lade GeoNames-Referenzdaten fuer Orts-Zuordnung...")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        lookup = {}
        for f_feature in data.get("features", []):
            props = f_feature.get("properties", {})
            name = props.get("field_2")
            alt_name = props.get("field_3")
            lat = props.get("field_5")
            lon = props.get("field_6")
            
            if name:
                name_lower = name.lower()
                lookup[name_lower] = (lat, lon)
                # Split for variations like "Monheim am Rhein" -> "Monheim"
                parts = re.split(r'\s+|[-/]', name_lower)
                if parts:
                    main_part = parts[0]
                    if len(main_part) > 3 and main_part not in lookup:
                        lookup[main_part] = (lat, lon)
            if alt_name:
                alt_lower = alt_name.lower()
                lookup[alt_lower] = (lat, lon)
                parts = re.split(r'\s+|[-/]', alt_lower)
                if parts:
                    main_part = parts[0]
                    if len(main_part) > 3 and main_part not in lookup:
                        lookup[main_part] = (lat, lon)
        return lookup
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der GeoNames-Datei: {e}")
        return {}

def parse_and_convert(row, geonames_lookup):
    massnahme = str(row.get('massnahme_id', ''))
    ort = str(row.get('ort', ''))
    kreis = str(row.get('kreis', ''))
    
    # Try to find TK map sheet number
    tk_match = re.search(r'TK\s*(\d{4})', massnahme, re.IGNORECASE)
    tk_num = int(tk_match.group(1)) if tk_match else None
    
    r_match = re.search(r'r\s*(\d+)(?:-(\d+))?', massnahme, re.IGNORECASE)
    h_match = re.search(r'h\s*(\d+)(?:-(\d+))?', massnahme, re.IGNORECASE)
    
    if not r_match or not h_match:
        return None, None
        
    # Get r and h values (taking average if range)
    r1 = int(r_match.group(1))
    r_val = (r1 + int(r_match.group(2))) / 2 if r_match.group(2) else r1
    
    h1 = int(h_match.group(1))
    h_val = (h1 + int(h_match.group(2))) / 2 if h_match.group(2) else h1
    
    # Standardize to 5 digits (meters offset in sheet)
    r_str = str(int(r_val))
    if len(r_str) == 3:
        r_val_m = r_val * 100
    elif len(r_str) == 4:
        r_val_m = r_val * 10
    elif len(r_str) == 5:
        r_val_m = r_val
    else:
        return None, None
        
    h_str = str(int(h_val))
    if len(h_str) == 3:
        h_val_m = h_val * 100
    elif len(h_str) == 4:
        h_val_m = h_val * 10
    elif len(h_str) == 5:
        h_val_m = h_val
    else:
        return None, None

    # Determine northing prefix (5600000 or 5700000)
    is_north = False
    if tk_num:
        if tk_num // 100 <= 45:
            is_north = True
    else:
        # Fallback to geonames lookup
        ort_coords = geonames_lookup.get(ort.lower())
        if not ort_coords and kreis:
            ort_coords = geonames_lookup.get(kreis.lower())
        if ort_coords:
            lat_approx = ort_coords[0]
            if lat_approx >= 51.4:
                is_north = True
                
    h_prefix = 5700000 if is_north else 5600000
    
    # Full Gauss-Kruger coordinates (Zone 2: Rechtswert starts with 25xxxxx)
    easting = 2500000 + r_val_m
    northing = h_prefix + h_val_m
    
    # Convert to Lat/Lon
    lon, lat = transformer.transform(easting, northing)
    return lat, lon

def main():
    if not os.path.exists(csv_path):
        print(f"❌ CSV-Datei nicht gefunden unter {csv_path}")
        return
        
    df = pd.read_csv(csv_path, sep=";")
    geonames_lookup = load_geonames(geojson_path)
    
    mapped_points = []
    for idx, row in df.iterrows():
        lat, lon = parse_and_convert(row, geonames_lookup)
        if lat and lon:
            mapped_points.append({
                'Seitenzahl': str(row.get('Seitenzahl', '-')),
                'ort': str(row.get('ort', '-')),
                'kreis': str(row.get('kreis', '-')),
                'massnahme_id': str(row.get('massnahme_id', '-')),
                'datierung_norm': str(row.get('datierung_norm', '-')),
                'befunde_norm': str(row.get('befunde_norm', '-')),
                'funde_norm': str(row.get('funde_norm', '-')),
                'autor': str(row.get('autor', '-')),
                'lat': lat,
                'lon': lon
            })
            
    print(f"Georeferenzierung: {len(mapped_points)} von {len(df)} Zeilen erfolgreich georeferenziert.")
    
    if mapped_points:
        # 1. Leaflet HTML-Karte generieren
        points_json = json.dumps(mapped_points, ensure_ascii=False, indent=2)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Archäologische Fundstellen 1970</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        html, body, #map {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
        }}
        .custom-popup {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
        }}
        .custom-popup h3 {{
            margin: 0 0 5px 0;
            font-size: 16px;
            color: #2c3e50;
        }}
        .custom-popup strong {{
            color: #34495e;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([51.1, 6.7], 9);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
        }}).addTo(map);

        var points = {points_json};

        var bounds = [];
        points.forEach(function(p) {{
            if (p.lat && p.lon) {{
                var marker = L.marker([p.lat, p.lon]).addTo(map);
                var popupContent = '<div class="custom-popup">' +
                    '<h3>' + p.ort + ' (' + p.kreis + ')</h3>' +
                    '<strong>Seitenzahl:</strong> ' + p.Seitenzahl + '<br>' +
                    '<strong>Maßnahme-ID:</strong> ' + p.massnahme_id + '<br>' +
                    '<strong>Datierung:</strong> ' + p.datierung_norm + '<br>' +
                    '<strong>Befunde:</strong> ' + p.befunde_norm + '<br>' +
                    '<strong>Funde:</strong> ' + p.funde_norm + '<br>' +
                    '<strong>Autor:</strong> ' + p.autor +
                    '</div>';
                marker.bindPopup(popupContent);
                bounds.push([p.lat, p.lon]);
            }}
        }});
        
        if (bounds.length > 0) {{
            map.fitBounds(bounds, {{ padding: [50, 50] }});
        }}
    </script>
</body>
</html>
"""
        with open(html_out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Interaktive Karte gespeichert unter: {html_out_path}")
        
        # 2. Statische Matplotlib-Grafik generieren
        lats = [p['lat'] for p in mapped_points]
        lons = [p['lon'] for p in mapped_points]
        labels = [p['ort'] for p in mapped_points]
        
        plt.figure(figsize=(12, 10))
        plt.scatter(lons, lats, color='#d35400', marker='o', s=120, edgecolors='black', alpha=0.8, zorder=5)
        
        # Label-Kollisionsvermeidung (einfacher Offset)
        for i, label in enumerate(labels):
            plt.annotate(
                label, 
                (lons[i], lats[i]), 
                textcoords="offset points", 
                xytext=(6, 6), 
                ha='left', 
                fontsize=9, 
                fontweight='semibold',
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", lw=0.5, alpha=0.8)
            )
            
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.title("Archäologische Fundstellen 1970 - Bonner Jahrbücher", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Längengrad (Longitude)", fontsize=12)
        plt.ylabel("Breitengrad (Latitude)", fontsize=12)
        
        # Sichern
        os.makedirs(os.path.dirname(img_out_path), exist_ok=True)
        plt.savefig(img_out_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Statische Grafik gespeichert unter: {img_out_path}")
    else:
        print("Keine Punkte mit Koordinaten gefunden.")

if __name__ == "__main__":
    main()
