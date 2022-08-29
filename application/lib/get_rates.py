import json
from application.lib.main import get_rate

def get_rates(data):
    _zones = [
        {  # zone 0
            'price': 5,
            'countries': ["EE"]
        },
        {  # zone 1
            'price': 7,
            'countries': [
                "LV",
                "LT",
                "AT",
                "BE",
                "BG",
                "ES",
                "NL",
                "HU",
                "IE",
                "IT",
                "GR",
                "LU",
                "MT",
                "PL",
                "PT",
                "FR",
                "SE",
                "RO",
                "DE",
                "SK",
                "SI",
                "FI",
                "GB",
                "DK",
                "CZ",
                "RU",
                "HR",
                "MD",
                "UA",
                "BY"
            ]
        },
        {  # zone 2
            'price': 11
        }
    ]

    vat = 0.2  # 20%
    min_days = 2
    max_days = 8
    destination = data["destination"]
    destination["locality"] = destination["city"]
    destination["country_code"] = destination["country"]
    validated_address = destination
    country_code = validated_address["country_code"]

    zone = None

    for i in range(2):

        if country_code in _zones[i].get('countries'):
            zone = _zones[i]
            break

    if not zone:
        zone = _zones[2]

    price = zone.get('price')

    total_price = (1 + vat) * price

    rates = [
        get_rate("EUR", total_price, max_days, min_days,
                 "Business Registered Maxi Letter",
                 "trmOmniva_XN_POSTALCODE")
    ]

    return rates


if __name__ == '__main__':
    data = '''{
    "currency": "EUR",
    "destination": {
        "address1": "402, 46, World Cup-ro 12-gil",
        "address2": "",
        "address3": null,
        "address_type": null,
        "city": "Mapo-gu",
        "company_name": null,
        "country": "KR",
        "email": null,
        "fax": null,
        "name": "Kim Seowon",
        "phone": "010-7323-3808",
        "postal_code": "04003",
        "province": "KR-11"
    },
    "items": [
        {
            "fulfillment_service": "manual",
            "grams": 4,
            "name": "Bretzel",
            "price": 550,
            "product_id": 1324829442134,
            "properties": {},
            "quantity": 1,
            "requires_shipping": true,
            "sku": "GER003",
            "taxable": false,
            "variant_id": 12301294239830,
            "vendor": "Pinpinpin.it"
        },
        {
            "fulfillment_service": "manual",
            "grams": 4,
            "name": "Beer",
            "price": 550,
            "product_id": 1324829409366,
            "properties": {},
            "quantity": 1,
            "requires_shipping": true,
            "sku": "GER002",
            "taxable": false,
            "variant_id": 12301294207062,
            "vendor": "Pinpinpin.it"
        },
        {
            "fulfillment_service": "manual",
            "grams": 4,
            "name": "Fernsehturm",
            "price": 550,
            "product_id": 1325245399126,
            "properties": {},
            "quantity": 1,
            "requires_shipping": true,
            "sku": "BER005",
            "taxable": false,
            "variant_id": 12305689575510,
            "vendor": "Pinpinpin.it"
        },
        {
            "fulfillment_service": "manual",
            "grams": 4,
            "name": "Altes Rathaus",
            "price": 550,
            "product_id": 1325245825110,
            "properties": {},
            "quantity": 1,
            "requires_shipping": true,
            "sku": "MUN001",
            "taxable": false,
            "variant_id": 12305707696214,
            "vendor": "Pinpinpin.it"
        },
        {
            "fulfillment_service": "manual",
            "grams": 4,
            "name": "Brandenburger Tor",
            "price": 550,
            "product_id": 1325284622422,
            "properties": {},
            "quantity": 1,
            "requires_shipping": true,
            "sku": "BER003",
            "taxable": false,
            "variant_id": 12306770002006,
            "vendor": "Pinpinpin.it"
        }
    ],
    "locale": "en",
    "origin": {
        "address1": "Virna 6",
        "address2": "",
        "address3": null,
        "address_type": null,
        "city": "Muuga k\u00fcla",
        "company_name": "Pinpinpin.it",
        "country": "EE",
        "email": null,
        "fax": null,
        "name": null,
        "phone": "",
        "postal_code": "74004",
        "province": "Viimsi vald, Harjumaa"
    }
}'''

    data = json.loads(data)
    res = get_rates(data)
    print(res)