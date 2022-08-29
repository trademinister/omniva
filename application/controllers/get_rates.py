from application import app
from application.models import *

from application.lib import yageocoder
from application.lib import omniva
from application.lib import mailer
from application.lib.validator import *
from application.lib.main import *
from application.lib.get_rates import get_rates as run_get_rates

from flask import jsonify, abort, request

import time
import math
import shopify
import json

encoding = "utf-8"

DIRNAME = app.config.get("DIRNAME") + "/application/"

PATH_TO_JSON = DIRNAME + "/json/"
PATH_TO_PRICES = PATH_TO_JSON + "/prices/"
PATH_TO_WEIGHTS = PATH_TO_PRICES + "/weight/"
PATH_TO_SIZES = PATH_TO_PRICES + "/size/"

ERROR_SUBJECT = "Omniva error"

@app.route('/get_rates', methods=['POST'])
def get_rates():
    if not (request.is_json and validate_webhook_request(request, app.config.get("SHOPIFY_API_SECRET"))):
        abort(403)

    headers = request.headers
    shop_name = headers['X-Shopify-Shop-Domain']

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)
    except Merchant.DoesNotExist:
        abort(403)

    if not merchant.active:
        abort(403)

    data = request.get_json()["rate"]
    print(json.dumps(data, indent=4, sort_keys=True))
    rates = run_get_rates(data)

    return jsonify({"rates": rates})


@app.route('/get_rates1', methods=['POST'])
def get_rates1():

    if not (request.is_json and validate_webhook_request(request, app.config.get("SHOPIFY_API_SECRET"))):
        abort(403)

    start_time = time.time()

    headers = request.headers
    shop_name = headers['X-Shopify-Shop-Domain']

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)
    except Merchant.DoesNotExist:
        abort(403)

    if not merchant.active:
        abort(403)

    with shopify.Session.temp(merchant.myshopify_domain,
                              app.config.get('SHOPIFY_API_VERSION'), merchant.token):
        shop = shopify.Shop.current()
        metafields = shop.metafields()
        for metafield in metafields:
            key = metafield.key
            if metafield.namespace == app.config.get("METAFIELD_NAMESPACE") \
            and key == "data":
                metafield_data = parse_metafield_value(metafield)
                break

    with open(PATH_TO_JSON + "service_codes.json", "r", encoding=encoding) as file:
        data = file.read()
        service_codes = json.loads(data)

    with open(PATH_TO_JSON + "zones.json", "r", encoding=encoding) as file:
        data = file.read()
        zones = json.loads(data)

    with open(PATH_TO_WEIGHTS + "weight.json") as file:
        data = file.read()
        price_weights = json.loads(data)

    with open(PATH_TO_SIZES + "prices.json") as file:
        data = file.read()
        price_sizes = json.loads(data)

    vat = float(metafield_data["vat"]) / 100

    min_days = 1

    try:
        with open("{}/shops/{}/rates.json".format(PATH_TO_JSON, merchant.myshopify_domain), "r") as file:
            data = file.read()
            print(data)
            custom_rates = json.loads(data)
    except:
        custom_rates = []
        metafield_data["custom"] = False

    try:
        max_days = int(metafield_data["max_days"])
    except:
        max_days = min_days

    data = request.get_json()["rate"]
    print(json.dumps(data, indent=4, sort_keys=True))
    destination = data["destination"]

    if metafield_data.get("enable_yandex"):
        validated_address = get_validated_address(destination, "en_US")
    else:
        destination["locality"] = destination["city"]
        destination["country_code"] = destination["country"]
        validated_address = destination

    print(validated_address)

    country_code = validated_address["country_code"]
    locality = validated_address["locality"]

    if not country_code in price_sizes:
        
        msg = 'shop_name: {}\n Country is not supported by Omniva \n Country code: {}'.format(shop_name, country_code).encode(encoding)
        print(msg)
        mailer.send_mail(ERROR_SUBJECT, msg, 'dev@trademinister.de')
        mailer.send_mail(ERROR_SUBJECT, msg, metafield_data.get("email"))

        return jsonify({"rates": []})

    items = data["items"]

    is_post_office = metafield_data["post_office"]
    is_parcel_machine = metafield_data["machine"]

    if is_post_office or is_parcel_machine:

        if is_post_office and is_parcel_machine:
            code = -1
        elif is_parcel_machine:
            code = 0
        elif is_post_office:
            code = 1

        parcel_points = omniva.get_parcel_points(country_code, locality=locality, limit=math.inf, code = code)

    else:

        parcel_points = []

    items_price = physical_items = courier_price = total_weight_kg = current_weight = total_price = current_height = 0

    if metafield_data["calculate"] and not metafield_data["custom"]:
        for i, item in enumerate(items):

            quantity = int(item["quantity"])

            width = int(metafield_data["width"])
            height = int(metafield_data["height"])
            length = int(metafield_data["length"])

            volume = width * height * length

            parcel_size = omniva.get_size(height)

            weight = int(item["grams"])
            weight_kg = weight / 1000

            total_weight_kg += weight_kg

            price_list = price_sizes[country_code]
            current_price = price_list[parcel_size] + price_list[parcel_size] * vat

            courier_price += current_price
            items_price += (int(item["price"]) / 100) * quantity

            if current_height + height > 39 or current_weight > 30 and country_code in app.config.get("TO_PICKUP"):
                physical_items += 1 * quantity
                total_price += current_price * quantity

                for _ in range(quantity):
                    if current_height + height > 39 or current_weight > 30:

                        current_height = height
                        current_weight = weight
                    else:
                        current_height += height
                        current_weight += weight

                if i + 1 == len(items):
                    total_price += current_price

    if metafield_data["custom"] and len(custom_rates):
        for custom_rate in custom_rates:
            min_price = custom_rate["min_price"]
            max_price = custom_rate["max_price"] if custom_rate["max_price"] != False else math.inf
            print("Min price: {} | max price: {} | items price: {} | in range? {}".format(
                min_price,
                max_price,
                items_price,
                is_in_range(items_price, min_price, max_price)
            ))
            if is_in_range(items_price, min_price, max_price):
                custom_price = total_price = custom_rate["price"]
                print(custom_price, "CUSTOM PRICE")
                break

    elif metafield_data["calculate"]:
            pickup_price = 3.68 if len(metafield_data["courier_service"].split(".")) > 1 else 0

            fees = pickup_price  + .5 + items_price * .015
    else:
        fees = 0

        total_price += fees

    rates = [
        get_rate("EUR", total_price, max_days, min_days, parcel_point["NAME"], "trmOmniva_{}_{}".format(parcel_point["TYPE"], parcel_point["ZIP"]))
        for parcel_point in parcel_points if time.time() - start_time <= 7
    ]

    if metafield_data["courier"] and time.time() - start_time <= 7:
        found = False

        if not total_weight_kg:
            total_weight_kg = .01

        omniva_service = metafield_data["courier_service"].split(".")[0]

        if omniva_service in price_weights:
            if omniva_service != "XJ" and omniva_service != "XN":
                price_list = price_weights[omniva_service]
            else:
                service_details = price_weights[omniva_service]
                countries = service_details["countries"]
                zone = "1" if country_code in countries else "2"
                price_list = service_details[zone]
                print(price_list)
            for block in price_list:
                min_weight = block["min_weight"]
                max_weight = block["max_weight"]
                if is_in_range(total_weight_kg, min_weight, max_weight):
                    total_price = block.get("price")
                    if omniva_service == "CI":
                        if country_code in block:
                            found = True
                            total_price = block[country_code]
                            break
                    elif omniva_service == "XJ" or omniva_service == "XN":
                        found = True
                        break
                    elif omniva_service == "EA":
                        for zone in zones:
                            countries = zones[zone]
                            if country_code in countries:
                                found = True
                                total_price = block[zone]
                                break
                    elif omniva_service == "CC":
                        found = True
                        price_per_kg = block["price_per_kg"]
                        price_per_item = block["price_per_item"]
                        total_price = total_weight_kg * price_per_kg + physical_items * price_per_item
                        break

                    elif omniva_service == "LX" or omniva_service == "LZ" or omniva_service == "LA":
                        found = True
                        break

        elif country_code != "EE" and country_code != "LV" and country_code != "LT":
            found = True

        if found:
            service_name = ""

            service_name = service_codes[omniva_service]

            total_price += total_price * vat

            if not metafield_data["calculate"]:
                total_price = 0
            elif metafield_data["custom"]:
                total_price = custom_price
            else:
                total_price += fees

            rate = get_rate("EUR", total_price, max_days, min_days, service_name, "trmOmniva_{}_{}".format(metafield_data["courier_service"], "POSTALCODE"))
            rates.append(rate)

    print(len(rates), " RATES RETURNED")
    time_taken = time.time() - start_time
    print("The request took us {}s.".format(time_taken))

    if time_taken > 10:
        subject = "Omniva error"
        msg = 'shop_name: {}\n It took too much time to calculate shipment price \n Time taken: {}'.format(shop_name, time_taken).encode(encoding)
        print(msg)
        mailer.send_mail(ERROR_SUBJECT, msg, 'dev@trademinister.de')
        mailer.send_mail(ERROR_SUBJECT, msg, metafield_data.get("email"))

    return jsonify({"rates": rates})
