"""
This module provides integration with Octopus Germany for Home Assistant.

It defines the coordinator and sensor entities to fetch and display
electricity price information.
"""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensor_ev import build_ev_entities
from .sensor_meter import build_meter_entities
from .sensor_tariff import build_tariff_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Octopus Germany price sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    account_number = data["account_number"]

    if coordinator.data is None:
        _LOGGER.debug("No data in coordinator, triggering refresh")
        await coordinator.async_refresh()

    if coordinator.data:
        _LOGGER.debug("Coordinator data keys: %s", coordinator.data.keys())

    entities = []

    account_numbers = entry.data.get("account_numbers", [])
    if not account_numbers and account_number:
        account_numbers = [account_number]

    if not account_numbers and coordinator.data:
        account_numbers = list(coordinator.data.keys())

    _LOGGER.debug("Creating sensors for accounts: %s", account_numbers)

    for acc_num in account_numbers:
        if coordinator.data and acc_num in coordinator.data:
            account_data = coordinator.data[acc_num]
            entities.extend(build_tariff_entities(acc_num, coordinator, account_data))
            entities.extend(build_meter_entities(acc_num, coordinator, account_data))
            entities.extend(build_ev_entities(acc_num, coordinator, account_data))
        else:
            if coordinator.data is None:
                _LOGGER.error("No coordinator data available")
            elif acc_num not in coordinator.data:
                _LOGGER.warning("Account %s missing from coordinator data", acc_num)
            elif "products" not in coordinator.data[acc_num]:
                _LOGGER.warning(
                    "No 'products' key in coordinator data for account %s", acc_num
                )
            else:
                _LOGGER.warning(
                    "Unknown issue detecting products for account %s", acc_num
                )

    # Only add entities if we have any
    if entities:
        _LOGGER.debug(
            "Adding %d entities: %s",
            len(entities),
            [type(e).__name__ for e in entities],
        )
        async_add_entities(entities)
    else:
        _LOGGER.warning("No entities to add for any account")


