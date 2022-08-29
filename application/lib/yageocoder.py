import requests
from urllib.parse import urlencode

def yageocoder(geocode, lang="ru_RU"):
    try:
        url = 'https://geocode-maps.yandex.ru/1.x/?apikey=5fa9d203-4294-40fe-bc83-f944213ee6a3&{}'
        params = {
            'format': 'json',
            'geocode': geocode,
            'results': 1,
            'lang': lang
        }
        url = url.format(urlencode(params))
        r = requests.get(url, timeout=6)

        if r.status_code != 200:

            return None

        return r.json()

    except:
        return None

def get_full_data(address, lang='ru_RU'):
    response = yageocoder(address, lang)
    if not response:
        return None
    try:
        found = int(response['response']['GeoObjectCollection']['metaDataProperty']['GeocoderResponseMetaData']['found'])
        if not found:
            return None

        GeoObject = response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
        point = GeoObject['Point']
        pos = point['pos'].split(' ')
        lat = pos[1]
        lon = pos[0]

        response = GeoObject['metaDataProperty']['GeocoderMetaData']
        address = response['Address']
        components = address['Components']
        result = {
        "country_code": address['country_code'],
        "postal_code": address.get('postal_code'),
        "coords": {
            "lat": lat,
            "lon": lon
        }}
        for component in components:
            result[component['kind']] = component['name']
        return result
    except Exception as e:
        print(e)
        return None

def get_coords(address):
    response = yageocoder(address)
    if not response:
        return None
    try:
        found = int(response['response']['GeoObjectCollection']['metaDataProperty']['GeocoderResponseMetaData']['found'])
        if not found:
            return None

        response = response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
        point = response['Point']
        pos = point['pos'].split(' ')
        lat = pos[1]
        lon = pos[0]
        return {
            "lat": lat,
            "lon": lon
        }
    except Exception as e:
        print(e)
        return None
