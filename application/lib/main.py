import json
import shopify
import datetime
import requests
from iso3166 import countries

from application import cipher

from application.lib import yageocoder

def get_validated_address(invalidated_address, lang = "ru_RU"):

    city = invalidated_address["city"]
    address = invalidated_address["address1"]
    country = invalidated_address["country"]
    zip = invalidated_address.get("postal_code")

    if not zip:
        zip = invalidated_address.get("zip")

    try:
        country = countries.get(country).name
    except:
        pass

    if country == 'DE':
        country = 'Germany'

    print(invalidated_address)

    original_address = "{}, {}, {}, {}".format(country, city, address, zip)
    print('=' * 20)
    print(original_address)
    print('=' * 20)
    result = yageocoder.get_full_data(original_address, lang)

    splitted = invalidated_address["address1"].split(",")

    street = splitted[0]
    house = splitted[1] if len(splitted) > 1 else ""

    table = {
        "country_code": "country",
        "postal_code": "postal_code",
        "country": "country",
        "locality": "city",
        "province": "province"
    }

    if not result:
        result = invalidated_address.copy()

    if not 'street' in result or not result.get("street"):
        result["street"] = street

    if not 'house' in result or not result.get("house"):
        result["house"] = house

    for key in table:
        if key not in result or type(result.get(key)) == type(None):
            result[key] = invalidated_address[table[key]]

    return result

def is_in_range(value, min, max):
    if min > max:
        raise ValueError("Minimal value ({}) cannot be greater than maximum value ({})".format(min,max))

    if value >= min and value <= max:
        return True

    return False

def prepare_api_headers(token):
    return {"X-Shopify-Access-Token": token,"Content-Type": "application/json"}

'''
def get_product_sizes(app, id, shop_name, token):
    with shopify.Session.temp(shop_name,token):
        shop = shopify.Shop.current()
        metafields = shop.metafields()

        try:
            poruduct = shopify.Product.find(id)
            metafields = product.metafields()

            product_sizes = {}

            for metafield in metafields:
                key = metafield.key
                value = metafield.value
                if key == 'width' or key == 'height' or key == 'length':
                    product_sizes[key] = value

            if len(product_sizes.keys()) == 3:
                return product_sizes

            return False

        except:
            return False
'''

def get_rate(currency, price = 600, max_days = 14, min_days = 3, service_name = "", service_code = ""):
    time_now = datetime.datetime.now()
    min_delivery = (time_now + datetime.timedelta(days=min_days))\
            .strftime('%Y-%m-%d')
    max_delivery = (time_now + datetime.timedelta(days=max_days))\
            .strftime('%Y-%m-%d')

    price = price * 100
    price = round(price)

    return {
        "service_name": service_name,
        "service_code": service_code,
        "total_price": price,
        "currency": currency,
        "min_delivery_date": min_delivery,
        "max_delivery_date": max_delivery
    }

def get_locations(shop_name, version, token):
    with shopify.Session.temp(shop_name, version, token):
        shop = shopify.Shop.current()

        return [location.to_dict() for location in shopify.Location.find(limit=250)]

    return False

def parse_metafield_value(metafield):
    return json.loads(cipher.decrypt(json.loads(metafield.value)["data"].encode("utf-8")))
