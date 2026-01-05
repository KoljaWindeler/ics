from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.helpers.entity import async_generate_entity_id
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from functools import partial
import traceback
import logging
import datetime
from tzlocal import get_localzone

from collections import OrderedDict
from icalendar import Calendar
from urllib.request import urlopen, Request
import requests

_LOGGER = logging.getLogger(__name__)

# generals
DOMAIN = "ics"
PLATFORM = "sensor"
PLATFORMS = ["sensor"]
VERSION = "1.2.0"
ISSUE_URL = "https://github.com/koljawindeler/ics/issues"

# configuration
CONF_ICON = "icon"
CONF_ICS_URL = "url"
CONF_NAME = "name"
CONF_ID = "id"
CONF_TIMEFORMAT = "timeformat"
CONF_LOOKAHEAD = "lookahead"
CONF_SW = "startswith"
CONF_CONTAINS = "contains"
CONF_REGEX = "regex"
CONF_SHOW_BLANK = "show_blank"
CONF_FORCE_UPDATE = "force_update"
CONF_SHOW_REMAINING = "show_remaining"
CONF_SHOW_ONGOING = "show_ongoing"
CONF_GROUP_EVENTS = "group_events"
CONF_N_SKIP = "n_skip"
CONF_DESCRIPTION_IN_STATE = "description_in_state"
CONF_USER_AGENT = "user_agent"
CONF_HEADER_NAME = "header_name"
CONF_HEADER_VALUE = "header_value"
CONF_HEADERS = "headers"
CONF_VERBOSE_LOGGING = "verbose_logging"


# defaults
DEFAULT_ICON = 'mdi:calendar'
DEFAULT_NAME = "ics_sensor"
DEFAULT_ID = 1
DEFAULT_SW = ""
DEFAULT_CONTAINS = ""
DEFAULT_REGEX = ".*"
DEFAULT_TIMEFORMAT = "%A, %d.%m.%Y"
DEFAULT_LOOKAHEAD = 365
DEFAULT_SHOW_BLANK = ""
DEFAULT_FORCE_UPDATE = 0
DEFAULT_SHOW_REMAINING = True
DEFAULT_SHOW_ONGOING = False
DEFAULT_GROUP_EVENTS = True
DEFAULT_N_SKIP = 0
DEFAULT_DESCRIPTION_IN_STATE = False
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'

# error
ERROR_URL = "invalid_url"
ERROR_ICS = "invalid_ics"
ERROR_TIMEFORMAT = "invalid_timeformat"
ERROR_SMALL_ID = "invalid_small_id"
ERROR_SMALL_LOOKAHEAD = "invalid_lookahead"
ERROR_ID_NOT_UNIQUE = "id_not_unique"
ERROR_NEGATIVE_SKIP = "skip_negative"

# extend schema to load via YAML
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_ICS_URL): cv.string,
	vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
	vol.Optional(CONF_ID, default=DEFAULT_ID): vol.Coerce(int),
	vol.Optional(CONF_TIMEFORMAT, default=DEFAULT_TIMEFORMAT): cv.string,
	vol.Optional(CONF_SW, default=DEFAULT_SW): cv.string,
	vol.Optional(CONF_CONTAINS, default=DEFAULT_CONTAINS): cv.string,
	vol.Optional(CONF_REGEX, default=DEFAULT_REGEX): cv.string,
	vol.Optional(CONF_LOOKAHEAD, default=DEFAULT_LOOKAHEAD): vol.Coerce(int),
	vol.Optional(CONF_SHOW_BLANK, default=DEFAULT_SHOW_BLANK): cv.string,
	vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): vol.Coerce(int),
	vol.Optional(CONF_SHOW_REMAINING, default=DEFAULT_SHOW_REMAINING): cv.boolean,
	vol.Optional(CONF_SHOW_ONGOING, default=DEFAULT_SHOW_ONGOING): cv.boolean,
	vol.Optional(CONF_GROUP_EVENTS, default=DEFAULT_GROUP_EVENTS): cv.boolean,
	vol.Optional(CONF_N_SKIP, default=DEFAULT_N_SKIP): vol.Coerce(int),
	vol.Optional(CONF_DESCRIPTION_IN_STATE, default=DEFAULT_DESCRIPTION_IN_STATE): cv.boolean,
	vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.string,
	vol.Optional(CONF_USER_AGENT, default=""): cv.string,	
	vol.Optional(CONF_HEADER_NAME, default=""): cv.string,
	vol.Optional(CONF_HEADER_VALUE, default=""): cv.string,
	# YAML: accept a mapping of headers
	vol.Optional(CONF_HEADERS, default={}): {cv.string: cv.string},
	vol.Optional(CONF_VERBOSE_LOGGING, default=False): cv.boolean,
})


def get_next_id(hass):
	"""Provide the next unused id."""
	if(hass is None):
		return 1
	for i in range(1, 999):
		if(async_generate_entity_id(ENTITY_ID_FORMAT, "ics_" + str(i), hass=hass) == PLATFORM + ".ics_" + str(i)):
			return i
	return 999


def ensure_config(user_input, hass):
	"""Make sure that needed Parameter exist and are filled with default if not."""
	out = {}
	out[CONF_NAME] = ""
	out[CONF_ICS_URL] = ""
	out[CONF_TIMEFORMAT] = DEFAULT_TIMEFORMAT
	out[CONF_SW] = DEFAULT_SW
	out[CONF_CONTAINS] = DEFAULT_CONTAINS
	out[CONF_REGEX] = DEFAULT_REGEX
	out[CONF_LOOKAHEAD] = DEFAULT_LOOKAHEAD
	out[CONF_SHOW_BLANK] = DEFAULT_SHOW_BLANK
	out[CONF_FORCE_UPDATE] = DEFAULT_FORCE_UPDATE
	out[CONF_SHOW_REMAINING] = DEFAULT_SHOW_REMAINING
	out[CONF_SHOW_ONGOING] = DEFAULT_SHOW_ONGOING
	out[CONF_GROUP_EVENTS] = DEFAULT_GROUP_EVENTS
	out[CONF_N_SKIP] = DEFAULT_N_SKIP
	out[CONF_DESCRIPTION_IN_STATE] = DEFAULT_DESCRIPTION_IN_STATE
	out[CONF_ICON] = DEFAULT_ICON
	out[CONF_USER_AGENT] = DEFAULT_USER_AGENT
	out[CONF_HEADER_NAME] = ""
	out[CONF_HEADER_VALUE] = ""
	out[CONF_HEADERS] = {}
	out[CONF_VERBOSE_LOGGING] = False
	out[CONF_ID] = get_next_id(hass)

	if user_input is not None:
		if CONF_NAME in user_input:
			out[CONF_NAME] = user_input[CONF_NAME]
		if CONF_ICS_URL in user_input:
			out[CONF_ICS_URL] = user_input[CONF_ICS_URL]
		if CONF_ID in user_input:
			out[CONF_ID] = user_input[CONF_ID]
		if CONF_TIMEFORMAT in user_input:
			out[CONF_TIMEFORMAT] = user_input[CONF_TIMEFORMAT]
		if CONF_SW in user_input:
			out[CONF_SW] = user_input[CONF_SW]
			if(out[CONF_SW] == " "):
				out[CONF_SW] = ""
		if CONF_CONTAINS in user_input:
			out[CONF_CONTAINS] = user_input[CONF_CONTAINS]
			if(out[CONF_CONTAINS] == " "):
				out[CONF_CONTAINS] = ""
		if CONF_REGEX in user_input:
			out[CONF_REGEX] = user_input[CONF_REGEX]
			if(out[CONF_REGEX] == " "):
				out[CONF_REGEX] = ""
		if CONF_LOOKAHEAD in user_input:
			out[CONF_LOOKAHEAD] = user_input[CONF_LOOKAHEAD]
		if CONF_SHOW_REMAINING in user_input:
			out[CONF_SHOW_REMAINING] = user_input[CONF_SHOW_REMAINING]
		if CONF_SHOW_ONGOING in user_input:
			out[CONF_SHOW_ONGOING] = user_input[CONF_SHOW_ONGOING]
		if CONF_SHOW_BLANK in user_input:
			out[CONF_SHOW_BLANK] = user_input[CONF_SHOW_BLANK]
			if(out[CONF_SHOW_BLANK] == " "):
				out[CONF_SHOW_BLANK] = ""
		if CONF_FORCE_UPDATE in user_input:
			out[CONF_FORCE_UPDATE] = user_input[CONF_FORCE_UPDATE]
		if CONF_GROUP_EVENTS in user_input:
			out[CONF_GROUP_EVENTS] = user_input[CONF_GROUP_EVENTS]
		if CONF_N_SKIP in user_input:
			out[CONF_N_SKIP] = user_input[CONF_N_SKIP]
		if CONF_DESCRIPTION_IN_STATE in user_input:
			out[CONF_DESCRIPTION_IN_STATE] = user_input[CONF_DESCRIPTION_IN_STATE]
		if CONF_ICON in user_input:
			out[CONF_ICON] = user_input[CONF_ICON]
		if CONF_USER_AGENT in user_input:
			out[CONF_USER_AGENT] = user_input[CONF_USER_AGENT]
		if CONF_HEADER_NAME in user_input:
			out[CONF_HEADER_NAME] = user_input[CONF_HEADER_NAME]
		if CONF_HEADER_VALUE in user_input:
			out[CONF_HEADER_VALUE] = user_input[CONF_HEADER_VALUE]
		if CONF_HEADERS in user_input:
			# accept either a dict (from YAML) or a string (from UI). If string, try to parse lines or JSON.
			val = user_input[CONF_HEADERS]
			if isinstance(val, dict):
				out[CONF_HEADERS] = val
			elif isinstance(val, str):
				val = val.strip()
				if val == "":
					out[CONF_HEADERS] = {}
				else:
					# try JSON first
					try:
						import json
						out[CONF_HEADERS] = json.loads(val)
					except Exception:
						# parse lines like 'Name: Value'
						headers = {}
						for line in val.splitlines():
							if ':' in line:
								k, v = line.split(':', 1)
								headers[k.strip()] = v.strip()
						out[CONF_HEADERS] = headers
			if CONF_VERBOSE_LOGGING in user_input:
				out[CONF_VERBOSE_LOGGING] = user_input[CONF_VERBOSE_LOGGING]
	return out


# helper to validate user input
async def check_data(user_input, hass, own_id=None):
	"""Check validity of the provided date."""
	ret = {}
	if(CONF_ICS_URL in user_input):
		try:
			# build headers dict from possible sources
			_headers = {}
			# YAML/config may provide mapping or UI may provide a string — normalize both
			if CONF_HEADERS in user_input:
				val = user_input[CONF_HEADERS]
				if isinstance(val, dict):
					_headers.update(val)
				elif isinstance(val, str):
					val = val.strip()
					if val != "":
						# try JSON first
						try:
							import json
							parsed = json.loads(val)
							if isinstance(parsed, dict):
								_headers.update(parsed)
						except Exception:
							# parse lines like 'Name: Value'
							headers = {}
							for line in val.splitlines():
								if ':' in line:
									k, v = line.split(':', 1)
									headers[k.strip()] = v.strip()
								_headers.update(headers)
			# single header fields (backwards compat)
			if user_input.get(CONF_HEADER_NAME):
				_headers[user_input.get(CONF_HEADER_NAME)] = user_input.get(CONF_HEADER_VALUE, "")
			cal_string = await async_load_data(hass, user_input[CONF_ICS_URL], user_input.get(CONF_USER_AGENT, ""), headers=_headers, verbose=user_input.get(CONF_VERBOSE_LOGGING, False))
			try:
				Calendar.from_ical(cal_string)
			except Exception:
				_LOGGER.error(traceback.format_exc())
				ret["base"] = ERROR_ICS
				return ret
		except Exception:
			_LOGGER.error(traceback.format_exc())
			ret["base"] = ERROR_URL
			return ret

	if(CONF_TIMEFORMAT in user_input):
		try:
			datetime.datetime.now(get_localzone()).strftime(user_input[CONF_TIMEFORMAT])
		except Exception:
			_LOGGER.error(traceback.format_exc())
			ret["base"] = ERROR_TIMEFORMAT
			return ret

	if(CONF_ID in user_input):
		if(user_input[CONF_ID] < 0):
			_LOGGER.error("ICS: ID below zero")
			ret["base"] = ERROR_SMALL_ID
			return ret

	if(CONF_LOOKAHEAD in user_input):
		if(user_input[CONF_LOOKAHEAD] < 1):
			_LOGGER.error("ICS: Lookahead < 1")
			ret["base"] = ERROR_SMALL_LOOKAHEAD
			return ret

	if(CONF_ID in user_input):
		if((own_id != user_input[CONF_ID]) and (hass is not None)):
			if(async_generate_entity_id(ENTITY_ID_FORMAT, "ics_" + str(user_input[CONF_ID]), hass=hass) != PLATFORM + ".ics_" + str(user_input[CONF_ID])):
				_LOGGER.error("ICS: ID not unique")
				ret["base"] = ERROR_ID_NOT_UNIQUE
				return ret

	if(CONF_N_SKIP in user_input):
		if(user_input[CONF_N_SKIP] < 0):
			_LOGGER.error("ICS: Skip below zero")
			ret["base"] = ERROR_NEGATIVE_SKIP
			return ret
	return ret


def create_form(page, user_input, hass):
	"""Create form for UI setup."""
	user_input = ensure_config(user_input, hass)

	data_schema = OrderedDict()
	if(page == 1):
		# prepare headers default: convert dict to multiline string for the form
		header_default = ""
		if isinstance(user_input.get(CONF_HEADERS), dict) and len(user_input.get(CONF_HEADERS))>0:
			lines = []
			for k, v in user_input.get(CONF_HEADERS).items():
				lines.append(f"{k}: {v}")
			header_default = "\n".join(lines)
		elif isinstance(user_input.get(CONF_HEADERS), str):
			header_default = user_input.get(CONF_HEADERS)
		data_schema[vol.Required(CONF_NAME, default=user_input[CONF_NAME])] = str
		data_schema[vol.Required(CONF_ICS_URL, default=user_input[CONF_ICS_URL])] = str
		data_schema[vol.Required(CONF_ID, default=user_input[CONF_ID])] = int
		data_schema[vol.Optional(CONF_TIMEFORMAT, default=user_input[CONF_TIMEFORMAT])] = str
		data_schema[vol.Optional(CONF_SW, default=user_input[CONF_SW])] = str
		data_schema[vol.Optional(CONF_CONTAINS, default=user_input[CONF_CONTAINS])] = str
		data_schema[vol.Optional(CONF_REGEX, default=user_input[CONF_REGEX])] = str
		data_schema[vol.Optional(CONF_LOOKAHEAD, default=user_input[CONF_LOOKAHEAD])] = int
		data_schema[vol.Optional(CONF_ICON, default=user_input[CONF_ICON])] = str
		data_schema[vol.Optional(CONF_USER_AGENT, default=user_input[CONF_USER_AGENT])] = str
		data_schema[vol.Optional(CONF_HEADERS, default=header_default)] = str

	elif(page == 2):
		data_schema[vol.Optional(CONF_SHOW_BLANK, default=user_input[CONF_SHOW_BLANK])] = str
		data_schema[vol.Optional(CONF_FORCE_UPDATE, default=user_input[CONF_FORCE_UPDATE])] = int
		data_schema[vol.Optional(CONF_N_SKIP, default=user_input[CONF_N_SKIP])] = int
		data_schema[vol.Optional(CONF_SHOW_REMAINING, default=user_input[CONF_SHOW_REMAINING])] = bool
		data_schema[vol.Optional(CONF_SHOW_ONGOING, default=user_input[CONF_SHOW_ONGOING])] = bool
		data_schema[vol.Optional(CONF_GROUP_EVENTS, default=user_input[CONF_GROUP_EVENTS])] = bool
		data_schema[vol.Optional(CONF_DESCRIPTION_IN_STATE, default=user_input[CONF_DESCRIPTION_IN_STATE])] = bool
	return data_schema


def _load_data(url,user_agent, headers=None, header_name=None, header_value=None, verbose=False):
	"""Load data from URL, exported to const to call it from sensor and from config_flow."""
	# prepare headers
	built = {}
	if headers and isinstance(headers, dict):
		built.update(headers)
	# User-Agent preference: explicit user_agent should override existing
	if user_agent:
		built['User-Agent'] = user_agent
	# backward compatibility for single header fields
	if header_name is not None and header_name != "" and header_value is not None:
		built[header_name] = header_value
	if(url.lower().startswith("file://")):
		# log curl-equivalent for debugging
		if verbose:
			try:
				curl_parts = ["curl -sS --location --fail"]
				curl_parts.append(f"'{url}'")
				for k, v in built.items():
					curl_parts.append(f"-H '{k}: {v}'")
				curl_cmd = ' '.join(curl_parts)
				_LOGGER.debug("ICS fetch (curl): %s", curl_cmd)
			except Exception:
				pass
		req = Request(url=url, data=None, headers=built)
		return urlopen(req).read().decode('ISO-8859-1')
	# log curl-equivalent for debugging
	if verbose:
		try:
			curl_parts = ["curl -sS --location --fail"]
			curl_parts.append(f"'{url}'")
			for k, v in built.items():
				curl_parts.append(f"-H '{k}: {v}'")
			curl_cmd = ' '.join(curl_parts)
			_LOGGER.debug("ICS fetch (curl): %s", curl_cmd)
		except Exception:
			pass
	resp = requests.get(url, headers=built, allow_redirects=True)
	# also log status code for quick diagnostics (only if verbose)
	if verbose:
		_LOGGER.debug("ICS fetch response: %s %s", resp.status_code, resp.headers.get('content-type'))
	return resp.content

async def async_load_data(hass, url, user_agent, headers=None, header_name=None, header_value=None, verbose=False):
	"""Load data from URL, exported to const to call it from sensor and from config_flow."""
	return await hass.async_add_executor_job(_load_data, url, user_agent, headers, header_name, header_value, verbose)
