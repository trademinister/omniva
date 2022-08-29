import base64, hashlib, hmac
from collections import OrderedDict

def validate_integer_value(value):
    if type(value).__name__ == 'unicode' or type(value).__name__ == 'str':
        try:
            value = float(value) # Если значение из строки нормально преобразуется во float, возвращаем True
            return True
        except Exception as e:
            return False
    elif type(value).__name__ == 'int' or type(value).__name__ == 'float':
        return True
    else:
        return False

def _hmac_is_valid(body, secret, hmac_to_verify):
    hash = hmac.new(secret.encode('utf-8'),body,hashlib.sha256)
    hmac_calculated = base64.b64encode(hash.digest())
    return hmac_calculated.decode('utf-8') == hmac_to_verify

def validate_webhook_request(request,secret):
    hash = request.headers['X-Shopify-Hmac-Sha256'] # HMAC от Shopify
    return _hmac_is_valid(request.get_data(),secret,hash)

def signature_validation(params, api_secret):
    """
    проверка подписи входящих get параметров
    :param params: request.args.items()
    :param api_secret: API secret key (app info) вашего public app с акаунта partner
    :return: bool
    """
    sorder_params = OrderedDict(sorted(params, key=lambda t: t[0]))
    hmac_param = sorder_params.pop('hmac')
    sorder_params = ['{}={}'.format(k, sorder_params[k]) for k in sorder_params]
    sorder_params = '&'.join(sorder_params)
    h = hmac.new(api_secret.encode('utf-8'), sorder_params.encode('utf-8'),hashlib.sha256).hexdigest()
    return hmac.compare_digest(hmac_param.encode('ascii'), h.encode('ascii'))

def is_address_validated(code,quality):
    code_validation = code == 'OVERRIDDEN' or code == 'CONFIRMED_MANUALLY' or code == 'VALIDATED'
    quality_validation = quality == 'GOOD' or quality == 'POSTAL_BOX' or quality == 'ON_DEMAND' or quality == 'UNDEF_05'

    if code_validation and quality_validation:
        return True
    return False

def validate_reuqest_v2(request, shopify_secret):
    try:
        normalized_args = ""
        url = request.url.split('?')[1]
        url = url.replace('%5B%5D','[]')
        args = url.split('&')
        keys = {}
        ids = []
        index = 0
        request_hmac = ""
        hmac_str = ''
        shop_name = ''
        for arg in args:
            if '[]' in arg:
                arg = arg.replace('[]','')
                devided = arg.split('=')
                key = devided[0]
                value = devided[1]
                if key == 'ids':
                    ids.append(int(value))
                if key in keys:
                    s_str = ', "{}"]'.format(value)
                    replace_str = "{}={}".format(key,keys[key]["value"])
                    keys[key]["value"] = keys[key]["value"].replace(']',s_str)
                    format_str = "{}={}".format(key,keys[key]["value"])
                    print(replace_str,format_str)
                    hmac_str = hmac_str.replace(replace_str,format_str)
                else:
                    keys[key] = {
                        "value": '["{}"]'.format(value).strip(),
                        "index": index
                    }
                    if not hmac_str:
                        hmac_str = key + "=" + keys[key]["value"]
                    else:
                        hmac_str += "&{}={}".format(key,keys[key][value])
            elif not 'hmac=' in arg:
                if 'shop' in arg:
                    shop_name = arg.split('=')[1]
                if not hmac_str:
                    hmac_str = arg
                else:
                    hmac_str += '&' + arg
            else:
                request_hmac = arg.split('=')[1]
            index += 1
        normalized_args = "?hmac="+request_hmac+"&"+hmac_str
        h = hmac.new(shopify_secret.encode('utf-8'),hmac_str.encode('utf-8'),hashlib.sha256).hexdigest()

        return hmac.compare_digest(request_hmac.encode('ascii'), h.encode('ascii'))

    except Exception as e:
        try:
            return signature_validation(request.args.items(), shopify_secret)
        except Exception as e:
            return False
