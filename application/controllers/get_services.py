from application import app
from application.models import Merchant

from application.lib.validator import *

from flask import abort, request

@app.route('/get_services', methods=['GET'])
def get_services():
    if not signature_validation(request.args.items(),app.config.get("SHOPIFY_API_SECRET")):
        abort(403)

    myshopify_domain = request.args.get("shop")

    try:
        merchant = Merchant.get(Merchant.myshopify_domain == myshopify_domain)
    except Merchant.DoesNotExist:
        abort(403)

    if not merchant.active:
        abort(403)

    DIRNAME = app.config.get("DIRNAME") + "/application/"
    path_to_json = DIRNAME + "/json/"

    with open(path_to_json + "service_codes.json", "r") as file:
        return file.read()
