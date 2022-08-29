import requests

OMNIVA_VOLUME = 39 * 38 * 64

WSDL = "https://edixml.post.ee/epmx/services/messagesService.wsdl"
HEADERS = {'content-type': 'text/xml; charset=utf-8'}

def get_parcel_points(country, county="", locality="", limit=4, code=-1):
    offload_places = requests.get("https://www.omniva.ee/locations.json", timeout=7).json()
    counter = 0
    for offload_place in offload_places:
        if counter <= limit and offload_place["A0_NAME"] == country and (offload_place["A1_NAME"] == county or county == "") and (offload_place["A2_NAME"] == locality or locality == "") and (offload_place["TYPE"] == str(code) or code < 0):
            counter += 1
            yield offload_place

def get_size(current_height):
    if current_height > 39:
        parcel_size = "XL"
    elif current_height > 19:
        parcel_size = "L"
    elif current_height > 9:
        parcel_size = "M"
    else:
        parcel_size = "S"

    return parcel_size

class Sender():
    def __init__(self, username, password, type):
        self.username = username
        self.password = password
        self.wsdl = WSDL
        self.headers = HEADERS
        self.type = type
        self.__set_session__(username, password)

    def __set_session__(self, username, password):
        session = requests.Session()
        session.auth = (username, password)
        self.session = session

    def _prepare_adddress_body(self, name, phone, email):
        return """
        <person_name>{name}</person_name>
        <!--Optional:-->
        <phone>{phone}</phone>
        <!--Optional:-->
        <mobile>{phone}</mobile>
        <!--Optional:-->
        <email>{email}</email>
        """.format(
            name = name,
            phone = phone,
            email = email
        )

    def _prepare_return_address(self, name, phone, email, delivery_point, country, street, post_code):
        body = self._prepare_adddress_body(name, phone, email)
        return """
        {body}
        <address postcode="{post_code}" country="{country}" street="{street}"/>
        """.format(
            body = body,
            country = country,
            street = street,
            post_code = post_code
        )

    def _prepare_address(self, name, phone, email, delivery_point, country, street, offload_postcode="", postcode=""):
        body = self._prepare_adddress_body(name, phone, email)

        if postcode != "":
            postcode = 'postcode="{}"'.format(postcode)

        if offload_postcode != "":
            offload_postcode = 'offloadPostcode="{}"'.format(offload_postcode)

        return """
        {body}
        <address {postcode} {offload_postcode} deliverypoint="{delivery_point}" country="{country}" street="{street}"/>
        """.format(
            body = body,
            offload_postcode = offload_postcode,
            country = country,
            street = street,
            postcode = postcode,
            delivery_point = delivery_point
        )

    def _prepare_service(self, service, price):
        return '<option code="{}" payed_amount="{}"/>'.format(service, price)

    def _prepare_services(self, services, price):
        services_str = ""
        for service in services:
            services_str += self._prepare_service(service, price)
        return services_str

    def _perepare_items(self, service, client_data, office_data, items, services, additional_data):
        items_str = ""

        name = client_data["name"]
        phone = client_data["phone"]
        email = client_data["email"]
        country = client_data["country"]
        street = client_data["street"]
        receiver_id = client_data["id"]
        post_code = client_data["postal_code"]

        delivery_point = office_data["deliverypoint"]
        offload_postcode = office_data["offload_postcode"]

        address = self._prepare_address(name, phone, email, delivery_point, country, street, offload_postcode = offload_postcode, postcode = post_code)
        return_address = self._prepare_return_address(name, phone, email, delivery_point, country, street, post_code)

        for item in items:
            weight = item["weight"]
            length = item["length"]
            width = item["width"]
            height = item["height"]
            price = item["price"]

            monetary_values = ""
            additional_tags = ""

            for add_service in services:
                if add_service == "BP":
                    monetary_values = """
                    <monetary_values>
                        <values code="item_value" amount="{price}"/>
                    </monetary_values>
                    """.format(price = price)

                    additional_tags = """
                    <!--Optional:-->
                    <account>{}</account>
                    <!--Optional:-->
                    <reference_number>{}</reference_number>
                    """.format(
                        additional_data["account"],
                        additional_data["reference_number"]
                    )

            services_str = self._prepare_services(services, price)

            if services_str != "":
                add_service = """
                <add_service>
                    <!--1 or more repetitions:-->
                    {}
                </add_service>
                """.format(services_str)
            else:
                add_service = ""

            items_str += """
            <item service="{service}">
                <!--Optional:-->
                {add_service}
                <measures weight="{weight}" length="{length}" width="{width}" height="{height}"/>
                {monetary_values}
                {additional_tags}
                  <!--Optional:-->
                  <show_return_code_sms>false</show_return_code_sms>
                  <!--Optional:-->
                  <show_return_code_email>false</show_return_code_email>
                <receiverAddressee>
                 {address}
              </receiverAddressee>
              <returnAddressee>
                {return_address}
              </returnAddressee>
            </item>
            """.format(
                service = service,
                weight = weight,
                length = length,
                width = width,
                height = height,
                street = street,
                price = price,
                address = address,
                return_address = return_address,
                monetary_values = monetary_values,
                additional_tags = additional_tags,
                add_service = add_service
            )

        return items_str

    def _get_xml_template(self, type, partner, msg_type, items):
        return """
        <soap-env:Envelope
            xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
            <soap-env:Body>
                <ns0:{type}
                    xmlns:ns0="http://service.core.epmx.application.eestipost.ee/xsd">
                    <partner>{partner}</partner>
                    <interchange msg_type="{msg_type}">
                        <header sender_cd="{partner}" currency_cd="EUR"/>
                        <item_list>
                            {items}
                        </item_list>
                    </interchange>
                </ns0:{type}>
            </soap-env:Body>
        </soap-env:Envelope>
        """.format(
            type = type,
            partner = partner,
            msg_type = msg_type,
            items = items
        )

    def _prepare_xml(self, service, partner, client_data, office_data, msg_type, items, services, additional_data):
        receiver_id = client_data["id"]

        items_str = self._perepare_items(service, client_data, office_data, items, services, additional_data)

        return self._get_xml_template(self.type, partner, msg_type, items_str).format(
            partner = partner,
            items = items_str,
            msg_type = msg_type
        ).strip()

    def send(self, service, partner, client_data, office_data, msg_type, items, services = [], additional_data = {} ):
        str_xml = self._prepare_xml(service, partner, client_data, office_data, msg_type, items, services, additional_data)
        print('*** b2c send XML ***')
        print(str_xml)
        print('*** /b2c send XML ***')
        response = self.session.post(self.wsdl, data=str_xml.encode("utf-8"), headers=self.headers)
        return response

    def get_card(self, barcode):
        return self.session.post(self.wsdl, headers = self.headers, data = """
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://service.core.epmx.application.eestipost.ee/xsd">
           <soapenv:Header/>
           <soapenv:Body>
              <xsd:addrcardMsgRequest>
                 <partner>{partner}</partner>
                 <sendAddressCardTo>response</sendAddressCardTo>
                 <barcodes>
                    <!--1 or more repetitions:-->
                    <barcode>{barcode}</barcode>
                 </barcodes>
              </xsd:addrcardMsgRequest>
           </soapenv:Body>
        </soapenv:Envelope>
        """.format(
            partner = self.username,
            barcode = barcode
        ))

    def get_cards(self, barcodes):
        barcodes_str = ""

        for barcode in barcodes:
            barcodes_str += "<barcode>{}</barcode>".format(barcode)

        return self.session.post(self.wsdl, headers = self.headers, data = """
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://service.core.epmx.application.eestipost.ee/xsd">
           <soapenv:Header/>
           <soapenv:Body>
              <xsd:addrcardMsgRequest>
                 <partner>{partner}</partner>
                 <sendAddressCardTo>response</sendAddressCardTo>
                 <barcodes>
                    <!--1 or more repetitions:-->
                    {barcodes}
                 </barcodes>
              </xsd:addrcardMsgRequest>
           </soapenv:Body>
        </soapenv:Envelope>
        """.format(
            partner = self.username,
            barcodes = barcodes_str
        ))
