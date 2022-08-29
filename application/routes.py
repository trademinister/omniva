import urllib
from flask import redirect, request, render_template, abort, jsonify, session, make_response, send_file, render_template_string
import pyactiveresource

from application import app
from application import cipher

from application.models import *
from urllib.parse import urlencode, quote_plus

import traceback
import json
import shopify
import base64
import sys
import os
import base64
import hashlib
import hmac
import requests
import time

from application.lib import yageocoder
from application.lib import omniva
from application.lib.validator import *
from application.lib.main import *

from application.controllers.get_rates import *
from application.controllers.set_order import *
from application.controllers.get_services import *
from application.lib.signature_validation import shopify_sign_valid_ids_required

@app.route("/install")
def install():
    return render_template("install.html")

@app.route('/start', methods=['GET'])
def start():
    try:
        came_from = request.args.get("shop")
        merchant = Merchant.get(Merchant.myshopify_domain == came_from)
        valid = signature_validation(request.args.items(),app.config.get("SHOPIFY_API_SECRET"))
        if valid and merchant.active:
            locations = get_locations(merchant.myshopify_domain,
                                      app.config.get('SHOPIFY_API_VERSION'),
                                      merchant.token)
            shippings = []

            session = shopify.Session(came_from,
                                      app.config.get('SHOPIFY_API_VERSION'),
                                      merchant.token)
            shopify.ShopifyResource.activate_session(session)
            shop = shopify.Shop.current()
            metafields = shop.metafields()

            for row in Shipping.select():
                try:
                    shopify_order = shopify.Order.find(row.track_id)
                    shippings.insert(0,{
                        "id": row.id,
                        "order_id": row.order_id,
                        "data": row.data,
                        "created": row.created.__str__(),
                        "track_id": row.track_id,
                        "updated": row.updated.__str__(),
                        "shopify_order": json.dumps(shopify_order.to_dict())
                    })

                except Exception as e:
                    print("Ошибка в получение заказа Shopify: " + traceback.format_exc())

            fields = app.config["FIELDS"]

            for metafield in metafields:
                if metafield.namespace == app.config.get('METAFIELD_NAMESPACE') and metafield.key == "data":
                    fields = parse_metafield_value(metafield)
                    break

            return json.dumps({"status":True,"locations":locations, "shippings": shippings, "fields": json.dumps(fields)})
        else:
            abort(403)
    except Merchant.DoesNotExist:
        abort(403)
    return jsonify({"status":False})

@app.route('/shop_erasure',methods=['POST'])
def shop_erasure():
    headers = request.headers
    if 'X-Shopify-Shop-Domain' in headers:
        myshopify_domain = headers['X-Shopify-Shop-Domain']
        if request.is_json:
            try:

                data = request.get_json()

                merchant = Merchant.get(Merchant.myshopify_domain == myshopify_domain)

                if validate_webhook_request(request,app.config['SHOPIFY_API_SECRET']):
                    merchant.delete_instance()
                else:
                    abort(403)

            except Merchant.DoesNotExist:
                abort(422)
        else:
            abort(403)
    else:
        abort(403)
    return jsonify({"status":True})


def reinstall_app(shop_name):
    app.logger.info('reinstall app for {}'.format(shop_name))
    args = urllib.parse.urlencode({'shop': shop_name})
    url = 'https://{}/authorize?{}'
    # редирект в админку
    return redirect(url.format(app.config.get('HOSTNAME'), args))


@app.route('/')
@shopify_sign_valid_ids_required
def home():
    shop_name = request.args.get('shop')

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)

    except Merchant.DoesNotExist:

        return reinstall_app(shop_name)

    try:

        with shopify.Session.temp(shop_name,
                                  app.config.get('SHOPIFY_API_VERSION'),
                                  merchant.token):
            shop = shopify.Shop.current()

    except pyactiveresource.connection.UnauthorizedAccess:
        app.logger.warning(traceback.format_exc())

        return reinstall_app(shop_name)

    return render_template('home.html')


@app.route('/authorize')
def authorize():
    def get_permission_url(shop_name):
        shopify.Session.setup(api_key=app.config['SHOPIFY_API_KEY'],
                              secret=app.config['SHOPIFY_API_SECRET'])
        session = shopify.Session(shop_name, app.config.get('SHOPIFY_API_VERSION'))
        scope = app.config.get('SCOPE')
        redirect_url = app.config['REDIRECT_URL']
        return session.create_permission_url(scope, redirect_url)

    """авторизация приложения"""
    shop_name = request.args.get('shop')
    permission_url = get_permission_url(shop_name)
    return redirect(permission_url)

@app.route('/finalize')
def finalize():
    def create_webhook(shop_name,token, topic, address):
        headers = prepare_api_headers(token)

        data = {
            "webhook": {
                "topic": topic,
                "address": address,
                "format": "json"
             }
        }

        data = json.dumps(data)

        return requests.post("https://" + shop_name + "/admin/api/2019-04/webhooks.json",headers=headers,data=data)

    def create_needed_webhooks(shop_name, token):
        root_url = "https://" + app.config['HOSTNAME']

        create_webhook(shop_name, token,"app/uninstalled", root_url + "/shop_erasure")
        create_webhook(shop_name, token,"orders/create", root_url + "/set_order")

    def create_carrier_service(shop_name,token):
        headers = prepare_api_headers(token)
        url = 'https://{}/admin/carrier_services.json'.format(shop_name)
        data = {
            'carrier_service': {
                #'name': app.config.get("METAFIELD_NAMESPACE"),
                'name': 'Omniva',
                'callback_url': 'https://{}/get_rates'.format(app.config.get("HOSTNAME")),
                'service_discovery': True
            }
        }

        return requests.post(url, json=data, headers=headers)

    shop_name = request.args.get('shop')

    shopify.Session.setup(api_key=app.config['SHOPIFY_API_KEY'],
                          secret=app.config['SHOPIFY_API_SECRET'])
    session = shopify.Session(shop_name, app.config.get('SHOPIFY_API_VERSION'))
    token = session.request_token(request.args.to_dict())

    create_needed_webhooks(shop_name, token)
    c_response = create_carrier_service(shop_name, token)

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)
        print('merchant FOUND')
    except Merchant.DoesNotExist:
        print('MERCHANT NOT FOUND, CREATING A NEW ONE')
        merchant = Merchant()
        merchant.myshopify_domain = shop_name
        merchant.name = shop_name.split('.')[0]

    merchant.token = token
    merchant.save()

    url = 'https://{}/admin/apps/{}'
    # редирект в админку
    return redirect(url.format(shop_name, app.config.get('SHOPIFY_API_KEY')))

@app.route('/update_shop', methods=['GET', 'POST'])
def update_shop():
    if request.method == 'GET':
        return jsonify({"status":True})
    else:
        if request.is_json:
            data = request.get_json()
            print(data)
            try:
                came_from = data['from']
                merchant = Merchant.get(Merchant.myshopify_domain == came_from)
                if merchant.active:
                    session = shopify.Session(came_from,
                                              app.config.get('SHOPIFY_API_VERSION'),
                                              merchant.token)
                    shopify.ShopifyResource.activate_session(session)
                    shop = shopify.Shop.current()
                    metafield = {
                        'namespace': app.config.get('METAFIELD_NAMESPACE'),
                        'key': "data",
                        'type': "json",
                        'value': json.dumps({
                            "data": cipher.encrypt(json.dumps(data)).decode("utf-8")
                        })
                    }
                    print("metafield added: ", metafield)
                    shop.add_metafield(shopify.Metafield(metafield))
                    return jsonify({"status":True})
                else:
                    abort(403)
            except Merchant.DoesNotExist:
                abort(400)
        else:
            abort(400)

@app.route('/merchant', methods=['GET', 'POST'])
def save():
    try:
        shop_name = session.get('shop_name')

        if not shop_name:
            abort(403)

        merchant = Merchant.get(Merchant.myshopify_domain == shop_name)

        if request.method == 'POST':

            print(request.is_json)

            if not request.is_json:
                abort(403)


            data = json.dumps(request.get_json())
            data = cipher.encrypt(data).decode('utf-8')

            # сохраняем в базу
            merchant.merchant = data
            merchant.save()

            # сохраняем в метаполе
            metafield = {
                'namespace': app.config.get('METAFIELD_NAMESPACE'),
                'key': 'merchant',
                'type': 'single_line_text_field',
                'value': data
            }

            with shopify.Session.temp(shop_name,
                                      app.config.get('SHOPIFY_API_VERSION'), merchant.token):
                shop = shopify.Shop.current()
                shop.add_metafield(shopify.Metafield(metafield))

            return jsonify({'status': True})

        else:
            data = None

            # попытаемся получить с метаполей
            with shopify.Session.temp(shop_name,
                                      app.config.get('SHOPIFY_API_VERSION'), merchant.token):
                shop = shopify.Shop.current()
                metafields = shop.metafields()

                for metafield in metafields:

                    if metafield.namespace == app.config.get('METAFIELD_NAMESPACE') \
                            and metafield.key == 'merchant':
                        data = metafield.value

            # попытаемся получить с базы
            if not data:
                data = merchant.merchant

            if not data:

                return jsonify({})

            data = cipher.decrypt(data.encode('utf-8'))
            data = json.loads(data)

            return jsonify(data)

    except:
        traceback.print_exc()
        abort(403)
