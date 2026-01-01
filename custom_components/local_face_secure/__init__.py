"""Local Face Secure - Home Assistant Custom Component for local face recognition.

This integration provides face recognition services using the face_recognition
(dlib) library. All processing runs locally within Home Assistant - no external
services or Docker containers required.

Features:
- Teach faces from camera snapshots
- Match faces against stored encodings
- Persistent storage of face encodings
- Event firing on face recognition

All CPU-bound operations run in the executor to avoid blocking the event loop.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_TEACH_FACE,
    SERVICE_SCAN_MATCH,
    SERVICE_DELETE_FACE,
    SERVICE_LIST_FACES,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    EVENT_FACE_RECOGNIZED,
    EVENT_DATA_NAME,
    EVENT_DATA_CONFIDENCE,
    DEFAULT_TOLERANCE,
    LOG_PREFIX,
)
from .storage import FaceEncodingStore
from .face_recognition_service import FaceRecognitionProcessor

_LOGGER = logging.getLogger(__name__)

# Service schemas with validation
SERVICE_TEACH_FACE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_NAME): cv.string,
})

SERVICE_SCAN_MATCH_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
})

SERVICE_DELETE_FACE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
})

# Configuration schema (minimal - component uses config entries or defaults)
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("tolerance", default=DEFAULT_TOLERANCE): vol.All(
            vol.Coerce(float),
            vol.Range(min=0.0, max=1.0)
        ),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Local Face Secure component.
    
    This is called by Home Assistant when the component is loaded.
    We initialize storage, load persisted data, and register services.
    
    Args:
        hass: Home Assistant instance.
        config: Configuration from configuration.yaml.
        
    Returns:
        True if setup was successful.
    """
    _LOGGER.info("%s Setting up Local Face Secure integration", LOG_PREFIX)

    # Get configuration options
    conf = config.get(DOMAIN, {})
    tolerance = conf.get("tolerance", DEFAULT_TOLERANCE)

    # Initialize the face encoding store and load persisted data
    store = FaceEncodingStore(hass)
    await store.async_load()

    # Initialize the face recognition processor
    processor = FaceRecognitionProcessor(hass, tolerance=tolerance)

    # Store references in hass.data for access by services
    hass.data[DOMAIN] = {
        "store": store,
        "processor": processor,
        "tolerance": tolerance,
    }

    # Register services
    await _async_register_services(hass)

    _LOGGER.info(
        "%s Setup complete. %d face(s) loaded from storage",
        LOG_PREFIX, store.count
    )
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register all component services.
    
    Services are the primary way users interact with this component.
    Each service is wrapped with error handling to prevent crashes.
    """

    async def handle_teach_face(call: ServiceCall) -> dict[str, Any]:
        """Handle the teach_face service call.
        
        Captures a snapshot from the specified camera, detects exactly one face,
        computes its encoding, and stores it with the given name.
        
        Service data:
            entity_id: Camera entity to capture from
            name: Name to associate with the face
            
        Returns:
            Service response with success status and message.
        """
        entity_id = call.data[ATTR_ENTITY_ID]
        name = call.data[ATTR_NAME].strip()

        if not name:
            raise HomeAssistantError("Name cannot be empty")

        _LOGGER.info(
            "%s Teaching face '%s' from camera %s",
            LOG_PREFIX, name, entity_id
        )

        store: FaceEncodingStore = hass.data[DOMAIN]["store"]
        processor: FaceRecognitionProcessor = hass.data[DOMAIN]["processor"]

        # Capture snapshot from camera
        try:
            # async_get_image is the standard way to get camera snapshots
            # It handles various camera integrations transparently
            image = await async_get_image(hass, entity_id)
        except HomeAssistantError as err:
            _LOGGER.error(
                "%s Failed to capture image from %s: %s",
                LOG_PREFIX, entity_id, err
            )
            raise HomeAssistantError(
                f"Failed to capture image from camera: {err}"
            ) from err

        # Detect and encode the face
        result = await processor.async_detect_and_encode(image.content)

        if not result.success:
            _LOGGER.warning(
                "%s Face teaching failed for '%s': %s",
                LOG_PREFIX, name, result.error_message
            )
            raise HomeAssistantError(result.error_message)

        # Store the encoding
        store.add_encoding(name, result.encoding)
        
        # Persist to storage
        await store.async_save()

        _LOGGER.info(
            "%s Successfully learned face for '%s'",
            LOG_PREFIX, name
        )

        return {
            "success": True,
            "message": f"Successfully learned face for '{name}'",
            "name": name,
        }

    async def handle_scan_match(call: ServiceCall) -> dict[str, Any]:
        """Handle the scan_match service call.
        
        Captures a snapshot from the specified camera and compares all
        detected faces against stored encodings. Fires an event for
        each recognized face.
        
        Service data:
            entity_id: Camera entity to capture from
            
        Returns:
            Service response with list of matched faces.
        """
        entity_id = call.data[ATTR_ENTITY_ID]

        _LOGGER.debug("%s Scanning for faces from %s", LOG_PREFIX, entity_id)

        store: FaceEncodingStore = hass.data[DOMAIN]["store"]
        processor: FaceRecognitionProcessor = hass.data[DOMAIN]["processor"]

        # Check if we have any faces to match against
        known_encodings = store.get_all_encodings()
        if not known_encodings:
            _LOGGER.warning("%s No faces stored, cannot perform matching", LOG_PREFIX)
            return {
                "success": False,
                "message": "No faces stored. Use teach_face first.",
                "matches": [],
            }

        # Capture snapshot from camera
        try:
            image = await async_get_image(hass, entity_id)
        except HomeAssistantError as err:
            _LOGGER.error(
                "%s Failed to capture image from %s: %s",
                LOG_PREFIX, entity_id, err
            )
            raise HomeAssistantError(
                f"Failed to capture image from camera: {err}"
            ) from err

        # Find matches
        matches = await processor.async_find_matches(
            image.content,
            known_encodings
        )

        # Fire events for each match
        for match in matches:
            event_data = {
                EVENT_DATA_NAME: match.name,
                EVENT_DATA_CONFIDENCE: match.confidence,
            }
            hass.bus.async_fire(EVENT_FACE_RECOGNIZED, event_data)
            _LOGGER.info(
                "%s Recognized '%s' with %d%% confidence",
                LOG_PREFIX, match.name, match.confidence
            )

        return {
            "success": True,
            "matches": [
                {"name": m.name, "confidence": m.confidence}
                for m in matches
            ],
            "message": f"Found {len(matches)} match(es)",
        }

    async def handle_delete_face(call: ServiceCall) -> dict[str, Any]:
        """Handle the delete_face service call.
        
        Removes a stored face encoding by name.
        
        Service data:
            name: Name of the face to delete
            
        Returns:
            Service response with success status.
        """
        name = call.data[ATTR_NAME].strip()

        _LOGGER.info("%s Deleting face '%s'", LOG_PREFIX, name)

        store: FaceEncodingStore = hass.data[DOMAIN]["store"]

        if not store.remove_encoding(name):
            raise HomeAssistantError(f"No face found with name '{name}'")

        # Persist the change
        await store.async_save()

        _LOGGER.info("%s Successfully deleted face '%s'", LOG_PREFIX, name)

        return {
            "success": True,
            "message": f"Successfully deleted face '{name}'",
            "name": name,
        }

    async def handle_list_faces(call: ServiceCall) -> dict[str, Any]:
        """Handle the list_faces service call.
        
        Returns a list of all stored face names.
        
        Returns:
            Service response with list of face names.
        """
        store: FaceEncodingStore = hass.data[DOMAIN]["store"]
        names = store.get_names()

        _LOGGER.debug("%s Listing %d stored face(s)", LOG_PREFIX, len(names))

        return {
            "success": True,
            "faces": names,
            "count": len(names),
        }

    # Register all services with their schemas
    # SupportsResponse.OPTIONAL allows services to return data
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEACH_FACE,
        handle_teach_face,
        schema=SERVICE_TEACH_FACE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_MATCH,
        handle_scan_match,
        schema=SERVICE_SCAN_MATCH_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_FACE,
        handle_delete_face,
        schema=SERVICE_DELETE_FACE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_FACES,
        handle_list_faces,
        schema=None,  # No parameters needed
        supports_response=SupportsResponse.OPTIONAL,
    )

    _LOGGER.debug("%s Registered %d services", LOG_PREFIX, 4)
