"""
@ Author	  : Kolja Windeler
@ Date		  : 06/02/2020
@ Description : Grabs an ics file and finds next event
@ Notes:		Copy this file and place it in your
				"Home Assistant Config folder\custom_components\sensor\" folder.
"""
import asyncio
import logging

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
from tzlocal import get_localzone
import recurring_ical_events
import datetime
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
CONF_SHOW_REMAINING = "show_remaining"
CONF_SHOW_BLANK = "show_blank"
CONF_FORCE_UPDATE = "force_update"

DEFAULT_NAME = "ics_sensor"
DEFAULT_SW = ""
DEFAULT_ID = 1
DEFAULT_TIMEFORMAT = "%A, %d.%m.%Y"
DEFAULT_LOOKAHEAD = 365
DEFAULT_SHOW_REMAINING = True
DEFAULT_SHOW_BLANK = ""
DEFAULT_FORCE_UPDATE = 0


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_ICSURL): cv.string,
	vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
	vol.Optional(CONF_ID, default=DEFAULT_ID): vol.Coerce(int),
	vol.Optional(CONF_TIMEFORMAT, default=DEFAULT_TIMEFORMAT): cv.string,
	vol.Optional(CONF_SW, default=DEFAULT_SW): cv.string,
	vol.Optional(CONF_LOOKAHEAD, default=DEFAULT_LOOKAHEAD): vol.Coerce(int),
	vol.Optional(CONF_SHOW_REMAINING, default=DEFAULT_SHOW_REMAINING): cv.boolean,
	vol.Optional(CONF_SHOW_BLANK, default=DEFAULT_SHOW_BLANK): cv.string,
	vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): vol.Coerce(int),
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
	show_remaining = config.get(CONF_SHOW_REMAINING)
	show_blank = config.get(CONF_SHOW_BLANK)
	force_update = config.get(CONF_FORCE_UPDATE)

	devices = []
	devices.append(ics_Sensor(hass, name, id, url, timeformat, lookahead, sw, show_remaining, show_blank, force_update))
	async_add_devices(devices)


class ics_Sensor(Entity):
	"""Representation of a Sensor."""

	def __init__(self,hass: HomeAssistantType,  name, id, url, timeformat, lookahead, sw, show_remaining, show_blank, force_update):
		"""Initialize the sensor."""
		self._state_attributes = None
		self._state = None
		self._name = name
		self._url = url
		self._sw = sw
		self._timeformat = timeformat
		self._lookahead = lookahead
		self._show_remaining = show_remaining
		self._show_blank = show_blank
		self._force_update = force_update
		self._lastUpdate = -1
		self.ics = {
			'extra':{
				'datetime':None,
				'remaining':-1,
				'description':"-",
				'last_updated': None,
				},
			'pickup_date': "-",
			}

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

	def exc(self):
		_LOGGER.error("\n\n============= ISC Integration Error ================")
		_LOGGER.error("unfortunately ICS hit an error, please open a ticket at")
		_LOGGER.error("https://github.com/KoljaWindeler/ics/issues")
		_LOGGER.error("and paste the following output:\n")
		_LOGGER.error(traceback.format_exc())
		_LOGGER.error("\nthanks, Kolja")
		_LOGGER.error("============= ISC Integration Error ================\n\n")


	def get_data(self):
		try:
			req = Request(url=self._url, data=None, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'})
			cal_string = urlopen(req).read().decode('ISO-8859-1')
			cal = Calendar.from_ical(cal_string)

			start_date = datetime.datetime.now().replace(minute=0, hour=0, second=0, microsecond=0)
			end_date = start_date + datetime.timedelta(days=self._lookahead)

			reoccuring_events = recurring_ical_events.of(cal).between(start_date, end_date)
			try:
				for i in reoccuring_events:
					if(i.get("DTSTART").params['VALUE'] == 'DATE'):
						d = i["DTSTART"].dt
						i["DTSTART"].dt = datetime.datetime(d.year,d.month,d.day)
					if(i["DTSTART"].dt.tzinfo == None or i["DTSTART"].dt.utcoffset() == None):
						i["DTSTART"].dt = i["DTSTART"].dt.replace(tzinfo=get_localzone())
				reoccuring_events = sorted(reoccuring_events, key=lambda x: x["DTSTART"].dt, reverse=False)
			except:
				self.exc()

			et = None
			self.ics['pickup_date'] = "no next event"
			self.ics['extra']['last_updated'] = datetime.datetime.now(get_localzone()).replace(microsecond=0)
			self.ics['extra']['datetime'] = None
			self.ics['extra']['remaining'] = -1
			self.ics['extra']['description'] = "-"

			if(len(reoccuring_events)>0):
				for e in reoccuring_events:
					event_date = e["DTSTART"].dt

					event_summary = ""
					if(e.has_key("SUMMARY")):
						event_summary = self.fix_text(e["SUMMARY"])
					elif(self._show_blank):
						event_summary = self.fix_text(self._show_blank)

					if(event_summary):
						if(event_summary.startswith(self.fix_text(self._sw)) and event_date>datetime.datetime.now(get_localzone())):
							if(et == None):
								self.ics['pickup_date'] = event_date.strftime(self._timeformat)
								self.ics['extra']['remaining'] = (event_date.date() - datetime.datetime.now(get_localzone()).date()).days
								self.ics['extra']['description'] = event_summary
								self.ics['extra']['datetime'] = event_date
								et = event_date
							elif(event_date == et):
								self.ics['extra']['description'] += " / " + event_summary
							else:
								break
		except:
			self.ics['pickup_date'] = "failure"
			self.exc()


	def update(self):
		"""Fetch new state data for the sensor.
		This is the only method that should fetch new data for Home Assistant.
		"""
		try:
			# first run
			if(self.ics['extra']['last_updated']==None):
				self.get_data()

			# update at midnight
			elif(self.ics['extra']['last_updated'].day != datetime.datetime.now().day):
				self.get_data()

			# update if datetime exists (there was an event in reach) and it is past now (look for the next event)
			if(self.ics['extra']['datetime']!=None):
				if(self.ics['extra']['datetime']<datetime.datetime.now(get_localzone())):
					self.get_data()

			# force updates (this should be last in line to avoid running twice)
			if(self.ics['extra']['last_updated']!=None and self._force_update>0):
				if(self.ics['extra']['last_updated']+datetime.timedelta(seconds=self._force_update) < datetime.datetime.now(get_localzone())):
					self.get_data()

			# update states
			self._state_attributes = self.ics['extra']
			self._state = self.ics['pickup_date']
			if(self._show_remaining):
				self._state += ' (%02i)' % self.ics['extra']['remaining']
		except:
			self._state = "error"
			self.exc()
