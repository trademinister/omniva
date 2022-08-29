from functools import wraps
from collections import OrderedDict
import hashlib
import hmac

from flask import current_app, abort, request


def signature_validation_with_ids(params, api_secret):
    """
    проверка подписи входящих get параметров c ids параметрами
    :param params: FLASK request.args.items(multi=True) для выборки одинаковых ключей
    :param api_secret: API secret key (app info) вашего public app с акаунта partner
    :return: bool
    """
    # достаем ids
    ids = []
    temp_params = []

    for param in params:

        if param[0] == 'ids[]':
            ids.append(param[1])

        else:
            temp_params.append(param)

    params = temp_params

    if ids:
        ids = ['"{}"'.format(str(row)) for row in ids]
        ids = ', '.join(ids)
        ids = '[' + ids + ']'
        params.append(('ids', ids))

    sorted_params = OrderedDict(sorted(params, key=lambda t: t[0]))
    hmac_param = sorted_params.pop('hmac')
    sorted_params = ['{}={}'.format(k, sorted_params[k]) for k in sorted_params]
    sorted_params = '&'.join(sorted_params)
    h = hmac.new(api_secret.encode('utf-8'), msg=sorted_params.encode('utf-8'),
                 digestmod=hashlib.sha256).hexdigest()

    return hmac.compare_digest(hmac_param, h)


def shopify_sign_valid_ids_required(f):
    """
    декоратор проверки подписи
    :param f:
    :return:
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            params = request.args.items(multi=True)
            api_secret = current_app.config.get('SHOPIFY_API_SECRET')

            valid = signature_validation_with_ids(params, api_secret)

            if not valid:
                abort(403)

        except:
            current_app.logger.warning('not sign validate {}'.format(request.args.get('shop', '')))
            abort(403)

        return f(*args, **kwargs)

    return decorated_function
