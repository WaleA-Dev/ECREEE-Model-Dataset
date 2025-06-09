import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
import time

COUNTRIES = [
    'Benin', 'Burkina Faso', 'Cabo Verde', 'Cote d\'Ivoire',
    'The Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau',
    'Liberia', 'Mali', 'Niger', 'Nigeria',
    'Senegal', 'Sierra Leone', 'Togo'
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {"User-Agent": "ECREEE-data-fetcher/1.0"}


def get_bbox(country):
    """Return bounding box for the country using Nominatim."""
    params = {
        'format': 'json',
        'country': country,
        'limit': 1,
    }
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"No bbox found for {country}")
    item = data[0]
    return float(item['boundingbox'][0]), float(item['boundingbox'][2]), float(item['boundingbox'][1]), float(item['boundingbox'][3])


def overpass_query(query):
    resp = requests.post(OVERPASS_URL, data={'data': query}, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def fetch_features(country, feature_type):
    south, west, north, east = get_bbox(country)
    bbox = f"({south},{west},{north},{east})"
    if feature_type == 'wind_plant':
        overpass = f"[out:json][timeout:60];(nwr['power'='plant']['generator:source'='wind']{bbox};);out center;"
    elif feature_type == 'solar_plant':
        overpass = f"[out:json][timeout:60];(nwr['power'='plant']['generator:source'='solar']{bbox};);out center;"
    elif feature_type == 'transmission_line':
        overpass = f"[out:json][timeout:60];(way['power'='line']{bbox};);out geom;"
    else:
        raise ValueError('Unknown feature type')
    data = overpass_query(overpass)
    features = []
    for elem in data.get('elements', []):
        if 'type' in elem and 'center' in elem:
            geom = {'type': 'Point', 'coordinates': [elem['center']['lon'], elem['center']['lat']]}
        elif elem.get('type') == 'way' and 'geometry' in elem:
            coords = [(pt['lon'], pt['lat']) for pt in elem['geometry']]
            geom = {'type': 'LineString', 'coordinates': coords}
        else:
            continue
        features.append({'geometry': shape(geom), 'properties': elem.get('tags', {})})
    if features:
        gdf = gpd.GeoDataFrame(features, crs='EPSG:4326')
    else:
        gdf = gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
    return gdf


def main():
    all_data = []
    for country in COUNTRIES:
        for feature in ['wind_plant', 'solar_plant', 'transmission_line']:
            try:
                gdf = fetch_features(country, feature)
                gdf['country'] = country
                gdf['feature'] = feature
                all_data.append(gdf)
                time.sleep(2)  # be nice to the server
            except Exception as e:
                print(f"Error fetching {feature} for {country}: {e}")
                continue
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.to_file('ecowrex_osm_data.geojson', driver='GeoJSON')
        print('Saved data to ecowrex_osm_data.geojson')


if __name__ == '__main__':
    main()
