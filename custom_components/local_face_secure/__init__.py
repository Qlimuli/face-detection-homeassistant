"""Local Face Secure - Home Assistant Custom Component for local face recognition."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import CONF_NAME

from .image_processing import FaceRecognitionProcessor

_LOGGER = logging.getLogger(__name__)

DOMAIN = "local_face_secure"

# Storage configuration
STORAGE_KEY = f"{DOMAIN}.face_encodings"
STORAGE_VERSION = 1

# Service names
SERVICE_TEACH_FACE = "teach_face"
SERVICE_SCAN_MATCH = "scan_match"
SERVICE_DELETE_FACE = "delete_face"
SERVICE_LIST_FACES = "list_faces"

# Service schema attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_NAME = "name"
ATTR_TOLERANCE = "tolerance"

# Event names
EVENT_FACE_RECOGNIZED = f"{DOMAIN}.recognized"
EVENT_FACE_TAUGHT = f"{DOMAIN}.taught"
EVENT_NO_FACE_FOUND = f"{DOMAIN}.no_face_found"

# Service schemas
SERVICE_TEACH_FACE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_NAME): cv.string,
})

SERVICE_SCAN_MATCH_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_TOLERANCE, default=0.6): vol.Coerce(float),
})

SERVICE_DELETE_FACE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
})

SERVICE_LIST_FACES_SCHEMA = vol.Schema({})

# Config schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Optional(ATTR_TOLERANCE, default=0.6): vol.Coerce(float),
        })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Local Face Secure component."""
    _LOGGER.info("Setting up Local Face Secure component")

    # Get configuration
    conf = config.get(DOMAIN, {})
    default_tolerance = conf.get(ATTR_TOLERANCE, 0.6)

    # Initialize the processor
    processor = FaceRecognitionProcessor(hass, default_tolerance)
    
    # Load stored face encodings
    await processor.async_load_encodings()

    # Store processor in hass.data
    hass.data[DOMAIN] = {
        "processor": processor,
        "config": conf,
    }

    # Register services
    async def handle_teach_face(call: ServiceCall) -> None:
        """Handle the teach_face service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        name = call.data[ATTR_NAME]

        _LOGGER.info("Teaching face for '%s' using camera '%s'", name, entity_id)

        try:
            success, message = await processor.async_teach_face(entity_id, name)
            
            if success:
                hass.bus.async_fire(EVENT_FACE_TAUGHT, {
                    "name": name,
                    "entity_id": entity_id,
                    "message": message,
                })
                _LOGGER.info("Successfully taught face: %s", name)
            else:
                hass.bus.async_fire(EVENT_NO_FACE_FOUND, {
                    "entity_id": entity_id,
                    "error": message,
                })
                _LOGGER.warning("Failed to teach face: %s", message)

        except Exception as err:
            _LOGGER.error("Error teaching face: %s", err)
            hass.bus.async_fire(EVENT_NO_FACE_FOUND, {
                "entity_id": entity_id,
                "error": str(err),
            })

    async def handle_scan_match(call: ServiceCall) -> None:
        """Handle the scan_match service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        tolerance = call.data.get(ATTR_TOLERANCE, default_tolerance)

        _LOGGER.info("Scanning for face match using camera '%s'", entity_id)

        try:
            result = await processor.async_scan_match(entity_id, tolerance)

            if result["matched"]:
                # Fire recognition event
                hass.bus.async_fire(EVENT_FACE_RECOGNIZED, {
                    "name": result["name"],
                    "confidence": result["confidence"],
                    "entity_id": entity_id,
                    "distance": result["distance"],
                })
                _LOGGER.info(
                    "Face recognized: %s (confidence: %s%%)",
                    result["name"],
                    result["confidence"]
                )
            else:
                hass.bus.async_fire(EVENT_NO_FACE_FOUND, {
                    "entity_id": entity_id,
                    "reason": result.get("reason", "No match found"),
                    "faces_detected": result.get("faces_detected", 0),
                })
                _LOGGER.info("No face match found: %s", result.get("reason"))

        except Exception as err:
            _LOGGER.error("Error scanning for face match: %s", err)
            hass.bus.async_fire(EVENT_NO_FACE_FOUND, {
                "entity_id": entity_id,
                "error": str(err),
            })

    async def handle_delete_face(call: ServiceCall) -> None:
        """Handle the delete_face service call."""
        name = call.data[ATTR_NAME]

        _LOGGER.info("Deleting face encoding for '%s'", name)

        success = await processor.async_delete_face(name)
        
        if success:
            _LOGGER.info("Successfully deleted face: %s", name)
        else:
            _LOGGER.warning("Face not found for deletion: %s", name)

    async def handle_list_faces(call: ServiceCall) -> None:
        """Handle the list_faces service call."""
        faces = processor.get_known_faces()
        _LOGGER.info("Known faces: %s", faces)
        
        # Fire event with list of faces
        hass.bus.async_fire(f"{DOMAIN}.faces_listed", {
            "faces": faces,
            "count": len(faces),
        })

    # Register all services
    hass.services.async_register(
        DOMAIN, SERVICE_TEACH_FACE, handle_teach_face, schema=SERVICE_TEACH_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_MATCH, handle_scan_match, schema=SERVICE_SCAN_MATCH_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_FACE, handle_delete_face, schema=SERVICE_DELETE_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_FACES, handle_list_faces, schema=SERVICE_LIST_FACES_SCHEMA
    )

    _LOGGER.info("Local Face Secure component setup complete")
    return True


async def async_unload(hass: HomeAssistant) -> bool:
    """Unload the Local Face Secure component."""
    _LOGGER.info("Unloading Local Face Secure component")

    # Remove services
    hass.services.async_remove(DOMAIN, SERVICE_TEACH_FACE)
    hass.services.async_remove(DOMAIN, SERVICE_SCAN_MATCH)
    hass.services.async_remove(DOMAIN, SERVICE_DELETE_FACE)
    hass.services.async_remove(DOMAIN, SERVICE_LIST_FACES)

    # Clean up data
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]

    return True
