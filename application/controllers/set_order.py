import re
import traceback
import json
import smtplib
import iso8601
import base64
import io
import datetime

import shopify
from flask import redirect, request, render_template, abort, jsonify, make_response, render_template_string
from lxml import etree
from ftplib import FTP
from application.models import *
from application import app
from application import cipher
from application import logging
from application.lib.send_data import send_mail2
from application.lib import yageocoder
from application.lib import omniva
from application.lib.validator import *
from application.lib.main import *
from application.lib.send_data import send_mail_attach

charset = "utf-8"

@app.route('/set_order', methods=['GET','POST'])
def set_order():
    logging.info("Recieved request in " + str(datetime.datetime.now()))
    if request.method == "GET":
        if not validate_reuqest_v2(request, app.config["SHOPIFY_API_SECRET"]):
            logging.warning("Request is not valid")
            abort(403)

        logging.info("Request is valid")
        args = request.args.items()
        for arg in args:
            key = arg[0]
            value = arg[1]
            print(key, value)
            if key == "ids[]":
                order_id = value
            elif key == "shop":
                shop_name = value

    else:
        if not validate_webhook_request(request, app.config["SHOPIFY_API_SECRET"]):
            abort(403)

        shop_name = request.headers['X-Shopify-Shop-Domain']

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)
    except Merchant.DoesNotExist:
        logging.warning("Merchant {} does not exist".format(shop_name))
        abort(403)

    if not merchant.active:
        logging.warning("Merchant {} is not active".format(merchant.myshopify_domain))
        abort(403)

    logging.info("Merchant {} is active".format(merchant.myshopify_domain))

    with shopify.Session.temp(merchant.myshopify_domain,
                              app.config.get('SHOPIFY_API_VERSION'), merchant.token):
        shop = shopify.Shop.current()
        shop_email = shop.email
        customer_email = shop.customer_email

        if not customer_email:
            customer_email = shop_email

        metafields = shop.metafields()
        metafield_shippings = {}

        for metafield in metafields:
            key = metafield.key
            if metafield.namespace == app.config.get("METAFIELD_NAMESPACE"):
                if key == "data":
                    metafield_data = parse_metafield_value(metafield)
                    #print(metafield_data)
                elif key == "shipping":
                    parsed_metafield_shippings = parse_metafield_value(metafield)
                    #print("PARSED metafield_shippings", parsed_metafield_shippings)
                    if type(parsed_metafield_shippings) == type(dict()):
                        metafield_shippings = parsed_metafield_shippings

        if request.method == "POST":
            if not metafield_data["auto"]:
                return jsonify({"status": True})

            order = request.get_json()
            order_id = int(order["id"])
            shopify_order = shopify.Order.find(order_id)
        else:
            try:
                shopify_order = shopify.Order.find(order_id)
                order = shopify_order.to_dict()
            except Exception as e:
                msg = "Order with id {id} was not found on https://pinpinpin-it-eng.myshopify.com/admin/orders/{id}.json".format(id=id)
                logging.critical(msg)

                return render_template_string("<h1> Can't create labels as the order is outdated </h1>")

                return jsonify({
                    "status": False,
                    "msg": msg,
                    "error_msg": traceback.format_exc(),
                    "total_orders": len(shopify.Order.find())
                })

    date = iso8601.parse_date(order["created_at"])

    month = date.month
    day = date.day
    year = date.year
    date = "{}.{}.{}".format(day, month, year)

    order_name = order["name"]
    order_number = order_name.replace("#","")

    file_format = "pdf"

    file_name = "{}-{}-{}-label".format(merchant.name, date.replace("/",""), order_number)

    try:
        shipping = Shipping.get(Shipping.order_id == str(order_id))
        data = json.loads(cipher.decrypt(shipping.data))
        barcodes = data["barcodes"]

        username = metafield_data["username"]
        password = metafield_data["password"]

        request_type =  "preSendMsgRequest"

        b2c = omniva.Sender(username, password, request_type)

        barcode_response = b2c.get_cards(barcodes)

        print(barcode_response.headers)
        barcode_xml = barcode_response.text
        barcode_xml_obj = etree.fromstring(barcode_xml)
        tags = barcode_xml_obj.getchildren()[1].getchildren()[0].getchildren()

        try:
            for tag_i in tags:
                if tag_i.tag == "successAddressCards":
                    base64_string = tag_i.getchildren()[0].getchildren()[1].text
                    base64_bytes = base64.decodebytes(base64_string.encode(charset))

        except Exception as e:
            raise e
            return render_template_string("<h1>Failed to get documents for this order</h1>")

        response = make_response(base64_bytes)
        response.headers['Content-Type'] = "application/pdf"
        response.headers['Content-Disposition'] = "inline; filename={}.{}".format(order_number, file_format)

        print("\n RETURNED HERE \n")

        return response

    except Shipping.DoesNotExist:
        pass

    #print(type(id))

    address = metafield_data["address"]
    port = metafield_data["port"]

    timeout = 7

    ftp_login = metafield_data["ftp_login"]
    ftp_password = metafield_data["ftp_password"]

    ftp_dir = metafield_data["dir"]

    try:
        try:
            ftp = FTP(address, timeout=timeout)
        except Exception as e:
            ftp = FTP(timeout=timeout)
            ftp.connect(address, int(port))

        ftp.login(user=ftp_login, passwd=ftp_password)

        ftp.cwd(ftp_dir)

    except Exception as e:
        return jsonify({
            "status": False,
            "msg": "Can't conntect to {}:{}".format(address, port),
            "error_msg": traceback.format_exc()
        })

    additiona_data = {}

    if metafield_data.get("cod"):
        additiona_data = {
            "account": metafield_data["account"],
            "reference_number": metafield_data["reference_number"]
        }

    shipping_lines = order["shipping_lines"]

    if not len(shipping_lines):
        logging.warning("Order with id {} does not require shipping".format(order["id"]))
        return jsonify({
            "status": True,
            "msg": "This order does not require shipping"
        })

    for shipping_line in shipping_lines:
        code = shipping_line["code"]
        source = shipping_line["source"]
        #print(shipping_line)
        try:

            service_code, service, offload_postcode = code.split("_")

            courier_pickup = True if len(service.split(".")) > 1 else False

            service = service.split(".")[0]

            if service == "0":
                service = "PA"
            elif service == "1":
                service = "CA"

            shipping_address = order["shipping_address"]

            phone = order["phone"] if order["phone"] else shipping_address.get("phone")
            _phone = re.findall(r'[+\d]+', phone)
            phone = ''.join(_phone)

            if metafield_data.get("enable_yandex"):
                validated_address = get_validated_address(shipping_address, "et_EE")
                validated_address["street"] = "{}, {}".format(validated_address.get("street"), validated_address.get("house"))
            else:
                shipping_address["locality"] = shipping_address["city"]
                shipping_address["street"] = "{}".format(shipping_address["address1"])
                shipping_address["postal_code"] = shipping_address["zip"]

                validated_address = shipping_address

            logging.info("Validated address: {}".format(validated_address))

            print(validated_address)

            country_code = validated_address["country_code"]
            postal_code = validated_address["postal_code"]

            if country_code == "LV" and not "LV-" in  postal_code:
                return render_template_string("<h1>Invalid postal code {} for country with country code {}. It must start with LV-</h1>".format(postal_code, country_code))

            if (country_code == "EE" or country_code == "LT") and len(postal_code) != 5:
                return render_template_string("<h1>{} postal code (ZIP) is not valid for country code {}</h1>".format(postal_code, country_code))

            client_data = {
                "id": "",
                "name": shipping_address["name"],
                "phone": phone, # "+37253920030"
                "email": order["email"],
                "postal_code": postal_code,
                "country": country_code,
                "street": "{}, {}".format(validated_address["street"], shipping_address["address2"])
            }

            office_data = {
                "deliverypoint": validated_address["locality"],
                "offload_postcode": offload_postcode
            }

            items = order["line_items"]

            location = json.loads(metafield_data["location"])

            max_length = 64
            max_width = 38
            max_height = 39

            width = int(metafield_data["width"])
            height = int(metafield_data["height"])
            length = int(metafield_data["length"])

            omniva_item = {
                "weight": 0, # (int(item["grams"]) / 1000) * quantity
                "width": width / 100,
                "height": height / 100,
                "length": length / 100,
                "price": 0 # float(price) * quantity
            }

            items_counter = 0

            omniva_items = []
            omniva_objects = []

            for item in items:
                if 'origin_location' in item:
                    origin_location = item["origin_location"]
                    #print(origin_location, location)
                    if location["country_code"] == origin_location["country_code"] and \
                    location["city"] == origin_location["city"] and \
                    origin_location["address1"] == location["address1"] and \
                    origin_location["zip"] == location["zip"]:

                        omniva_items.append(item)

                        quantity = int(item["quantity"])
                        price = item["price"]
                        item_weight_kg = int(item["grams"]) / 1000

                        for _ in range(quantity):
                            items_counter += 1

                            if items_counter > int(metafield_data["items_in_package"]):
                                #print("{} IS GREATER THAN {}".format(items_counter, metafield_data["items_in_package"]))
                                items_counter = 0
                                copied_item_object = omniva_item.copy()
                                omniva_objects.append(copied_item_object)
                                omniva_item["weight"] = 0
                                omniva_item["price"] = 0
                            else:
                                omniva_item["weight"] += item_weight_kg * quantity
                                omniva_item["price"]  += float(price) * quantity

            if items_counter:
                items_counter = 0
                copied_item_object = omniva_item.copy()
                omniva_objects.append(copied_item_object)
                omniva_item["weight"] = 0
                omniva_item["price"] = 0

            if not omniva_item["width"]:
                return render_template_string("<h1>No items assigned to the chosen location ({}) found in this order</h1>".format(location["address1"]))

            #print(omniva_item)

            username = partner = client_data["id"] = metafield_data["username"]
            password = metafield_data["password"]

            request_type =  "preSendMsgRequest" if courier_pickup else "businessToClientMsgRequest" #

            b2c = omniva.Sender(username, password, request_type)

            msg_type = "elsinfov1"

            if service != "XJ" and service != "XN" and service != "CI" and service != "QB" and service != "EA" and service != "EP" and service != "CC" and service != "VC":
                additional_services = ("ST", "SF")
            else:
                additional_services = tuple()

            xml = b2c.send(service, partner, client_data, office_data, msg_type, omniva_objects, additional_services)

            #print(xml.content)

            logging.info("Xml sent, status code: " + str(xml.status_code))

            xml_obj = etree.fromstring(xml.text)
            response_tags = xml_obj.getchildren()[1].getchildren()[0].getchildren()

            for tag in response_tags:
                tag_name = tag.tag
                value = tag.text

                if tag_name == "prompt":
                    if value == "Messages successfully received!":
                        continue
                    else:
                        app.logger.error(xml.text)
                        # отправить емейл что ошибка и текст ошибки поле велью
                        send_mail2('omniva prompt error', xml.text,
                                   ['dev@trademinister.net', shop_email])
                        return render_template_string(xml.text)
                elif tag_name == "savedPacketInfo":
                    barcodes = [ barcode_tag.getchildren()[1].text for barcode_tag in tag.getchildren()]
                    if request_type == "businessToClientMsgRequest":
                        for barcode in barcodes:
                            barcode_response = b2c.get_card(barcode)

                            print(barcode_response.headers)
                            barcode_xml = barcode_response.text
                            barcode_xml_obj = etree.fromstring(barcode_xml)
                            tags = barcode_xml_obj.getchildren()[1].getchildren()[0].getchildren()

                            try:
                                for tag_i in tags:
                                    if tag_i.tag == "successAddressCards":

                                        base64_string = tag_i.getchildren()[0].getchildren()[1].text
                                        base64_bytes = base64.decodebytes(base64_string.encode(charset))

                                        ftp.storbinary("STOR {}.{}".format(order_number, file_format), io.BytesIO(base64_bytes))
                                        app.logger.warning('FILE STORE {} {}'.format(order_number, str(datetime.datetime.now())))
                                        subject = 'Omniva label for order {}.{}'.format(order_number, file_format)
                                        _filename = '{}.{}'.format(order_number, file_format)
                                        message = 'See in attach'

                                        try:
                                            send_mail_attach(subject, message, customer_email, base64_bytes, _filename)
                                        except:
                                            app.logger.error('send_mail_attach')

                            except Exception as e:
                                app.logger.error('EXCEPT FILE STORE')
                                app.logger.error(traceback.format_exc())
                                raise e
                                return render_template_string(
                                    """
                                    <h1> Error while getting parcel labels </h1>
                                    <h3> Xml response: {}</h3>
                                    """.format(barcode_response.text)
                                )

                    metafield_shipping = {
                        "order_id": order_id,
                        "status": "success",
                        "barcodes": barcodes,
                        "items": items
                    }

                    metafield_shippings[str(order_id)] = metafield_shipping

                    data = cipher.encrypt(json.dumps(metafield_shippings)).decode("utf-8")

                    if len(data) >= 63000:
                        data = cipher.encrypt(json.dumps([metafield_shipping])).decode("utf-8")

                    metafield = {
                        'namespace': app.config.get("METAFIELD_NAMESPACE"),
                        'key': "shipping",
                        'type': "json",
                        'value': json.dumps({
                            "data": data
                        })
                    }

                    with shopify.Session.temp(merchant.myshopify_domain,
                                              app.config.get('SHOPIFY_API_VERSION'), merchant.token):
                        shop = shopify.Shop.current()

                        fulfillment = shopify.Fulfillment({
                                              'order_id': order_id,
                                              'line_items': omniva_items,
                                              'location_id': location["id"]
                                          })
                        fulfillment.tracking_numbers = barcodes
                        fulfillment.tracking_company = "Omniva"
                        fulfillment.tracking_urls = [
                            "https://www.omniva.ee/private/track_and_trace?barcode={}&lang=eng".format(barcode)
                            for barcode in barcodes
                        ]
                        fulfillment.notify_customer = metafield_data["fulfillment"]
                        fulfillment.save()

                        shop.add_metafield(shopify.Metafield(metafield))

                    ftp.close()

                    order["barcodes"] = barcodes

                    shipping = Shipping()
                    shipping.order_id = str(order_id)
                    shipping.data = cipher.encrypt(json.dumps(order)).decode("utf-8")
                    shipping.track_id = ",".join(barcodes)
                    shipping.save()

                    try:
                        response = make_response(base64_bytes)
                        response.headers['Content-Type'] = "application/pdf"
                        response.headers['Content-Disposition'] = "inline; filename={}.{}".format(order_number, file_format)
                        return response
                    except Exception as e:
                        return jsonify({
                            "status": True,
                            "barcodes": barcodes
                        })

            ftp.close()
            return jsonify({
                "status": False
            })

        except Exception as e:
            error_msg = traceback.format_exc()
            logging.critical(error_msg)
            try:
                smtp_config = app.config.get("EMAIL")

                login = smtp_config["login"]
                password = smtp_config["password"]

                smtpObj = smtplib.SMTP('smtp.gmail.com', 587)
                smtpObj.starttls()
                smtpObj.login(login,password)
                smtpObj.sendmail(login,metafield_data["email"],"Error while preparing documents: {}".format(error_msg))

            except Exception as e:
                logging.error("Error while sending email: " + traceback.format_exc())

            return "Error occured while creating shipment"

    logging.warning("Omniva shipping lines were not found for order with id " + str(order["id"]))

    return jsonify({
        "status": True,
        "msg": "Omniva shipping lines were not found",
        "shipping_lines": shipping_lines
    })
