"""Provide the initial setup."""
import logging
from integrationhelper.const import CC_STARTUP_VERSION
from .const import *

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
	"""Provide Setup of platform."""
	_LOGGER.info(
		CC_STARTUP_VERSION.format(name=DOMAIN, version=VERSION, issue_link=ISSUE_URL)
	)
	return True


async def async_setup_entry(hass, config_entry):
	"""Set up this integration using UI/YAML."""
	hass.config_entries.async_update_entry(
		config_entry,
		data=ensure_config(config_entry.data, hass)
	)
	config_entry.add_update_listener(update_listener)
	# Add sensor
	hass.async_create_background_task(
		hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM),
		name=DOMAIN
	)
	return True


async def async_remove_entry(hass, config_entry):
	"""Handle removal of an entry."""
	try:
		await hass.config_entries.async_forward_entry_unload(config_entry, PLATFORM)
		_LOGGER.info(
			"Successfully removed sensor from the ICS integration"
		)
	except ValueError:
		pass


async def update_listener(hass, entry):
	"""Update listener."""
	entry.data = entry.options
	await hass.config_entries.async_forward_entry_unload(entry, PLATFORM)
	hass.async_create_background_task(
		hass.config_entries.async_forward_entry_setup(entry, PLATFORM),
		name=DOMAIN
	)
