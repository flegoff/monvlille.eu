#!/usr/bin/env python
#
# Copyright 2011 Florian Le Goff & Samuel Lemaresquier
# Some parts : Copyright 2010 Google Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

import webapp2
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import memcache

import re
import logging

from vlille.station import Station
from models import StationData

MIN_WARN_BIKES = 2
MIN_WARN_FREE_ATTACHS = 2
MIN_BIKES = 1
MIN_FREE_ATTACHS = 1

TIMEOUT_LONG = 21600
TIMEOUT_STATION = 20


class StationHandler(webapp2.RequestHandler):
    def __init__(self, *args, **kwargs):
        super(StationHandler, self).__init__(*args, **kwargs)
        self.reg = re.compile('^/station/(\d+)')

    def _match_station(self):
        m = self.reg.match(self.request.path)
        if not m:
            return None

        station_id = m.group(1)

        station = memcache.get("station-" + station_id)

        if station is None:
            station_data = memcache.get("station-db-" + station_id)

            if station_data is None:
                station_data = StationData.get_by_key_name(station_id)
                memcache.set("station-db-" + station_id, station_data, time=TIMEOUT_LONG)

            station = Station(id=station_id)
            if station_data is None:
                logging.error("oh noes - station_id {0} is None !".format(station_id))
                return None
            station.name = station_data.name
            station.refresh()
            memcache.set("station-" + station_id, station, time=TIMEOUT_STATION)

        return station

    def _template(self, station, type_page):
        path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')

        if not station is None:
            self.response.out.write(template.render(path, {'type_page': type_page,
                                                           'station': station.to_dict()
                                                           }))
        else:
            self.response.out.write(template.render(path, {}))

    def get(self):
        station = self._match_station()

        if not station:
            self.response.set_status(404)
            return self._template(None, "blank.html")

        if station.bikes >= MIN_WARN_BIKES and station.free_attachs >= MIN_WARN_FREE_ATTACHS:
            return self._template(station, "ok")

        if station.bikes >= MIN_BIKES and station.free_attachs >= MIN_FREE_ATTACHS:
            return self._template(station, "warning")

        return self._template(station, "ko")


class IndexHandler(webapp2.RequestHandler):
    def _template(self, values, template_file):
        path = os.path.join(os.path.dirname(__file__), 'static', template_file)
        self.response.out.write(template.render(path, values))

    def get(self):
        stations = memcache.get("stations")

        if stations is None:
            logging.info("- rebuild liste des stations")
            stations = StationData.all()
            stations_light = []
            for station in stations:
                stations_light.append({'id_vlille': station.id_vlille, 'name': station.name})

            memcache.set("stations", stations_light, time=TIMEOUT_LONG)

        return self._template({'stations': stations}, "index_stations.html")


from vlille.system import Vlille


class RefreshHandler(webapp2.RequestHandler):
    def get(self):
        vlillef = Vlille()
        vlillef.load_stations()

        stations = []
        for station in vlillef.stations:
            stations.append(StationData(key_name=str(station.id),
                                        id_vlille=station.id,
                                        name=station.name))

        db.delete(StationData.all())
        db.put(stations)

        self.response.out.write("stations : %i" % len(vlillef.stations))


app = webapp2.WSGIApplication([('^/index', IndexHandler),
                               ('^/station/refresh', RefreshHandler),
                               ('^/station/\d+$', StationHandler)],
                               debug=True)
