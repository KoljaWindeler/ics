"""
@ Author	  : Kolja Windeler
@ Date		  : 06/02/2020
@ Description : Grabs an ics file and finds next event
@ Notes:		Copy this file and place it in your
				"Home Assistant Config folder\custom_components\sensor\" folder.
"""
import asyncio

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import (CONF_NAME)
from homeassistant.helpers.typing import HomeAssistantType

import logging
import unicodedata
import voluptuous as vol

from urllib.request import urlopen, Request
from icalendar import Calendar, Event
import recurring_ical_events
import datetime
import pytz
import traceback


_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:calendar'
DOMAIN = "ics"

CONF_ICSURL = "url"
CONF_NAME = "name"
CONF_ID = "id"
CONF_TIMEFORMAT = "timeformat"
CONF_LOOKAHEAD = "lookahead"
CONF_SW = "startswith"

DEFAULT_NAME = "ics_sensor"
DEFAULT_SW = ""
DEFAULT_ID = 1
DEFAULT_TIMEFORMAT = "%A, %d.%m.%Y"
DEFAULT_LOOKAHEAD = 365


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_ICSURL): cv.string,
	vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
	vol.Optional(CONF_ID, default=DEFAULT_ID): vol.Coerce(int),
	vol.Optional(CONF_TIMEFORMAT, default=DEFAULT_TIMEFORMAT): cv.string,
	vol.Optional(CONF_SW, default=DEFAULT_SW): cv.string,
	vol.Optional(CONF_LOOKAHEAD, default=DEFAULT_LOOKAHEAD): vol.Coerce(int),
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
	"""Set up date afval sensor."""
	url = config.get(CONF_ICSURL)
	name = config.get(CONF_NAME)
	id = config.get(CONF_ID)
	sw = config.get(CONF_SW)
	timeformat = config.get(CONF_TIMEFORMAT)
	lookahead = config.get(CONF_LOOKAHEAD)

	devices = []
	devices.append(ics_Sensor(hass, name, id, url, timeformat, lookahead, sw))
	async_add_devices(devices)


class ics_Sensor(Entity):
	"""Representation of a Sensor."""

	def __init__(self,hass: HomeAssistantType,  name, id, url, timeformat, lookahead, sw):
		"""Initialize the sensor."""
		self._state_attributes = None
		self._state = None
		self._name = name
		self._url = url
		self._sw = sw
		self._timeformat = timeformat
		self._lookahead = lookahead
		self._lastUpdate = -1

		self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, "ics_" + str(id), hass=hass)
	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._name

	@property
	def device_state_attributes(self):
		"""Return the state attributes."""
		return self._state_attributes

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def icon(self):
		"""Return the icon to use in the frontend."""
		return ICON

	def fix_text(self,s):
		s=''.join(e for e in s if (e.isalnum() or e==' '))
		s = s.replace(chr(195), 'u')
		s = s.replace(chr(188), 'e')
		return s

	def get_data(self):
		self.ics = {}
		extra = {}
		extra['description'] = "-"
		extra['remaining'] = -1
		self.ics['pickup_date'] = "-"
		self.ics['extra'] = extra

		try:
			req = Request(url=self._url, data=None, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
			cal_string = urlopen(req).read().decode('ISO-8859-1')
			cal = Calendar.from_ical(cal_string)

			start_date = datetime.datetime.now()
			end_date = datetime.datetime.now() + datetime.timedelta(days = self._lookahead)

			reoccuring_events = recurring_ical_events.of(cal).between(start_date, end_date)

			self.ics['pickup_date'] = "no pick up"

			if(len(reoccuring_events)>0):
				# sort events so strange ordered calerdar will be ok
				try:
					reoccuring_events = sorted(reoccuring_events, key=lambda x: x["DTSTART"].dt, reverse=False)
				except:
					print("sorting failure")
					print(traceback.format_exc())
				# loop, to find first events
				for e in reoccuring_events:
					if(e.has_key('SUMMARY')):
						date = e['DTSTART'].dt
						self.ics['pickup_date'] = date.strftime(self._timeformat)
						if(e.get('DTSTART').params['VALUE'] == 'DATE'):
							rem = date - datetime.datetime.now(pytz.utc).date()
						else:
							rem = date.date() - datetime.datetime.now(pytz.utc).date()
						extra['remaining'] = rem.days
						extra['description'] = self.fix_text(e['SUMMARY'])
						if(extra['description'].startswith(self.fix_text(self._sw))):
							break

		except:
			print("\n\n============= ISC Integration Error ================")
			print("unfortunately ICS hit an error, please open a ticket at")
			print("https://github.com/KoljaWindeler/ics/issues")
			print("and paste the following output:\n")
			print(traceback.format_exc())
			print("\nthanks, Kolja")
			print("============= ISC Integration Error ================\n\n")
			self.ics['pickup_date'] = "failure"

	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		if self._lastUpdate != str(datetime.datetime.now().strftime("%d")):
			self.get_data()
		try:
			if(self.ics['extra']['remaining']>0):
				self._state = self.ics['pickup_date'] + ' (%02i)' % self.ics['extra']['remaining']
			else:
				self._state = self.ics['pickup_date']
			self._state_attributes = self.ics['extra']
		except:
			self._state = "error"
