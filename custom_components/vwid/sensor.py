from .libvwid import vwid
import asyncio
import logging
import aiohttp
import voluptuous as vol
from datetime import timedelta
from typing import Any, Callable, Dict, Optional
from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import (
    ATTR_NAME,
    CONF_NAME,
    CONF_PASSWORD,
    DEVICE_CLASS_BATTERY,
)
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from .const import (
    DOMAIN,
    CONF_VIN
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    session = async_get_clientsession(hass)
    api = vwid(session)
    api.set_credentials(config[CONF_NAME], config[CONF_PASSWORD])
    api.set_vin(config[CONF_VIN])
    sensor = VwidSensor(api)
    async_add_entities([sensor], update_before_add=True)

class VwidSensor(Entity):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._name = 'State of charge'
        self._state = None
        self._available = True
        self.attrs = {'vin': self.api.vin}
        #self.attrs: Dict[str, Any] = {ATTR_PATH: self.repo}
        self.entity_id = ENTITY_ID_FORMAT.format(self.api.vin + '_soc')
        
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return (self.api.vin + '_soc')

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self):
        return self._state
        
    @property
    def device_class(self):
        return DEVICE_CLASS_BATTERY
        
    @property
    def unit_of_measurement(self):
        return '%'

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        return self.attrs

    async def async_update(self):
        data = await self.api.get_status()
        if (data):
            # Add state of charge as value
            self._state = int(data['data']['batteryStatus']['currentSOC_pct'])

            # For now, just flatten tree structure and add two-level deep parameters as attributes
            for key1 in data['data'].keys():
                element = data['data'][key1]
                if isinstance(element, dict):
                    for key2 in data['data'][key1].keys():
                        value = data['data'][key1][key2]
                        if not ((type(value) in [dict, list]) or ('Timestamp' in key2)):
                            # Convert mix of camelcase and snakecase to just camelcase
                            key_camelcase = ''.join((x[:1].upper() + x[1:]) for x in key2.split('_'))
                            self.attrs[key_camelcase] = value
                                
            self._available = True
        else:
            self._available = False
            _LOGGER.exception("Error retrieving data")
