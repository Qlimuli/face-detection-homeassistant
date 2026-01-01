"""Config flow for Simple Local Face Recognition."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    DOMAIN,
    CONF_CAMERA_ENTITY,
    CONF_TOLERANCE,
    CONF_SCAN_INTERVAL,
    CONF_DETECT_UNKNOWN,
    CONF_MODEL,
    DEFAULT_TOLERANCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_DETECT_UNKNOWN,
    DEFAULT_MODEL,
    MODEL_HOG,
    MODEL_CNN,
)

_LOGGER = logging.getLogger(__name__)


def get_camera_entities(hass: HomeAssistant) -> list[str]:
    """Get all camera entities."""
    return [
        entity_id
        for entity_id in hass.states.async_entity_ids(CAMERA_DOMAIN)
    ]


class SimpleLocalFaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simple Local Face Recognition."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # Get available cameras
        cameras = get_camera_entities(self.hass)
        
        if not cameras:
            return self.async_abort(reason="no_cameras")

        if user_input is not None:
            # Validate input
            camera_entity = user_input[CONF_CAMERA_ENTITY]
            
            # Check if already configured for this camera
            await self.async_set_unique_id(f"{DOMAIN}_{camera_entity}")
            self._abort_if_unique_id_configured()

            # Create the entry
            return self.async_create_entry(
                title=f"Face Recognition - {camera_entity.split('.')[-1].replace('_', ' ').title()}",
                data=user_input,
            )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_CAMERA_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=CAMERA_DOMAIN)
                ),
                vol.Optional(
                    CONF_TOLERANCE, default=DEFAULT_TOLERANCE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=1.0,
                        step=0.05,
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=300,
                        step=1,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_DETECT_UNKNOWN, default=DEFAULT_DETECT_UNKNOWN
                ): selector.BooleanSelector(),
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=MODEL_HOG, label="HOG (Fast, less accurate)"),
                            selector.SelectOptionDict(value=MODEL_CNN, label="CNN (Slow, more accurate)"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "camera_count": str(len(cameras)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SimpleLocalFaceOptionsFlow:
        """Get the options flow for this handler."""
        return SimpleLocalFaceOptionsFlow(config_entry)


class SimpleLocalFaceOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Simple Local Face Recognition."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Update the config entry with new options
            return self.async_create_entry(
                title="",
                data={**self.config_entry.data, **user_input},
            )

        # Current values
        current_tolerance = self.config_entry.data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)
        current_scan_interval = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_detect_unknown = self.config_entry.data.get(CONF_DETECT_UNKNOWN, DEFAULT_DETECT_UNKNOWN)
        current_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TOLERANCE, default=current_tolerance
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=1.0,
                        step=0.05,
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_scan_interval
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=300,
                        step=1,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_DETECT_UNKNOWN, default=current_detect_unknown
                ): selector.BooleanSelector(),
                vol.Optional(CONF_MODEL, default=current_model): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=MODEL_HOG, label="HOG (Fast, less accurate)"),
                            selector.SelectOptionDict(value=MODEL_CNN, label="CNN (Slow, more accurate)"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
