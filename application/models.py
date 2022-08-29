from peewee import CharField, DateTimeField, TextField, BooleanField, IntegerField, FloatField
from application import db

import datetime

class Shipping(db.Model):
    order_id = CharField(unique=True)
    data = CharField(null=True)
    created = DateTimeField(default=datetime.datetime.utcnow, null=True)
    track_id = CharField(null=True)
    updated = DateTimeField(default=datetime.datetime.utcnow, null=True)

class Merchant(db.Model):
    myshopify_domain = CharField(unique=True)
    name = CharField(null=True)
    updated = DateTimeField(default=datetime.datetime.utcnow, null=True)  # время создания в юникоде
    active = BooleanField(default=True, null=True) # Доступен ли магазин или нет
    token = CharField(null=True)
