from google.appengine.ext import db

class StationData(db.Model):
    id_vlille = db.IntegerProperty(required=True)
    name = db.StringProperty(required=True)