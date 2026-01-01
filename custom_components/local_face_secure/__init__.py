"""The Local Face Secure integration."""
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIDENCE,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    DOMAIN,
    ERROR_CAMERA_UNAVAILABLE,
    ERROR_FACE_EXISTS,
    ERROR_FACE_NOT_FOUND,
    ERROR_INVALID_CAMERA,
    ERROR_MULTIPLE_FACES,
    ERROR_NO_FACE_DETECTED,
    ERROR_SNAPSHOT_FAILED,
    EVENT_FACE_DELETED,
    EVENT_FACE_RECOGNIZED,
    EVENT_FACE_TAUGHT,
    SERVICE_DELETE_FACE,
    SERVICE_LIST_FACES,
    SERVICE_SCAN_MATCH,
    SERVICE_TEACH_FACE,
)
from .face_service import FaceRecognitionService
from .storage import FaceStorage

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_TEACH_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_NAME): cv.string,
    }
)

SERVICE_SCAN_MATCH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_DELETE_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
    }
)

SERVICE_LIST_FACES_SCHEMA = vol.Schema({})

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({}),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Local Face Secure component."""
    _LOGGER.info("Setting up Local Face Secure integration")

    # Initialize storage
    storage = FaceStorage(hass)
    await storage.async_load()

    # Initialize face recognition service
    face_service = FaceRecognitionService(hass, storage)

    # Store instances in hass.data
    hass.data[DOMAIN] = {
        "storage": storage,
        "service": face_service,
    }

    # Register services
    async def handle_teach_face(call: ServiceCall) -> None:
        """Handle teach_face service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        name = call.data[ATTR_NAME]

        _LOGGER.info("Service call: teach_face for %s from %s", name, entity_id)

        # Validate camera entity
        if not _is_valid_camera_entity(hass, entity_id):
            _LOGGER.error("Invalid camera entity: %s", entity_id)
            raise ValueError(ERROR_INVALID_CAMERA)

        try:
            await face_service.async_teach_face(entity_id, name, overwrite=False)

            # Fire event
            hass.bus.async_fire(
                EVENT_FACE_TAUGHT,
                {
                    ATTR_NAME: name,
                    ATTR_ENTITY_ID: entity_id,
                },
            )

            _LOGGER.info("Successfully taught face: %s", name)

        except ValueError as err:
            error_msg = str(err)
            _LOGGER.error("Failed to teach face %s: %s", name, error_msg)
            
            # Provide user-friendly error messages
            if ERROR_FACE_EXISTS in error_msg or "already exists" in error_msg:
                raise ValueError(
                    f"Face '{name}' already exists. Delete it first or use a different name."
                ) from err
            elif ERROR_NO_FACE_DETECTED in error_msg:
                raise ValueError(
                    "No face detected in camera image. Please ensure a face is clearly visible."
                ) from err
            elif ERROR_MULTIPLE_FACES in error_msg:
                raise ValueError(
                    "Multiple faces detected. Please ensure only one person is in frame."
                ) from err
            else:
                raise

        except RuntimeError as err:
            _LOGGER.error("Runtime error teaching face %s: %s", name, err)
            raise ValueError(
                f"Failed to capture image from camera: {err}"
            ) from err

    async def handle_scan_match(call: ServiceCall) -> None:
        """Handle scan_match service call."""
        entity_id = call.data[ATTR_ENTITY_ID]

        _LOGGER.info("Service call: scan_match from %s", entity_id)

        # Validate camera entity
        if not _is_valid_camera_entity(hass, entity_id):
            _LOGGER.error("Invalid camera entity: %s", entity_id)
            raise ValueError(ERROR_INVALID_CAMERA)

        try:
            result = await face_service.async_recognize_face(entity_id)

            if result:
                # Fire recognition event
                hass.bus.async_fire(
                    EVENT_FACE_RECOGNIZED,
                    {
                        ATTR_NAME: result["name"],
                        ATTR_CONFIDENCE: result["confidence"],
                        ATTR_ENTITY_ID: entity_id,
                    },
                )

                _LOGGER.info(
                    "Face recognized: %s (%.1f%% confidence)",
                    result["name"],
                    result["confidence"],
                )
            else:
                _LOGGER.info("No matching face found")

        except ValueError as err:
            error_msg = str(err)
            _LOGGER.error("Failed to scan face: %s", error_msg)

            # Provide user-friendly error messages
            if ERROR_NO_FACE_DETECTED in error_msg:
                raise ValueError(
                    "No face detected in camera image. Please ensure a face is clearly visible."
                ) from err
            elif ERROR_MULTIPLE_FACES in error_msg:
                raise ValueError(
                    "Multiple faces detected. Please ensure only one person is in frame."
                ) from err
            else:
                raise

        except RuntimeError as err:
            _LOGGER.error("Runtime error scanning face: %s", err)
            raise ValueError(
                f"Failed to capture image from camera: {err}"
            ) from err

    async def handle_delete_face(call: ServiceCall) -> None:
        """Handle delete_face service call."""
        name = call.data[ATTR_NAME]

        _LOGGER.info("Service call: delete_face for %s", name)

        try:
            await face_service.async_delete_face(name)

            # Fire event
            hass.bus.async_fire(
                EVENT_FACE_DELETED,
                {
                    ATTR_NAME: name,
                },
            )

            _LOGGER.info("Successfully deleted face: %s", name)

        except KeyError as err:
            _LOGGER.error("Face not found: %s", name)
            raise ValueError(f"Face '{name}' not found in database") from err

    async def handle_list_faces(call: ServiceCall) -> None:
        """Handle list_faces service call."""
        _LOGGER.info("Service call: list_faces")

        faces = face_service.list_faces()
        _LOGGER.info("Known faces: %s", ", ".join(faces) if faces else "None")

        # Return as service response
        return {"faces": faces}

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEACH_FACE,
        handle_teach_face,
        schema=SERVICE_TEACH_FACE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_MATCH,
        handle_scan_match,
        schema=SERVICE_SCAN_MATCH_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_FACE,
        handle_delete_face,
        schema=SERVICE_DELETE_FACE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_FACES,
        handle_list_faces,
        schema=SERVICE_LIST_FACES_SCHEMA,
        supports_response=True,
    )

    _LOGGER.info("Local Face Secure integration setup complete")

    return True


def _is_valid_camera_entity(hass: HomeAssistant, entity_id: str) -> bool:
    """
    Validate that entity is a camera.
    
    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to validate
        
    Returns:
        True if entity is a valid camera
    """
    # Check if entity exists
    state = hass.states.get(entity_id)
    if state is None:
        return False

    # Check if it's a camera entity
    if not entity_id.startswith("camera."):
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Local Face Secure integration")

    # Remove services
    hass.services.async_remove(DOMAIN, SERVICE_TEACH_FACE)
    hass.services.async_remove(DOMAIN, SERVICE_SCAN_MATCH)
    hass.services.async_remove(DOMAIN, SERVICE_DELETE_FACE)
    hass.services.async_remove(DOMAIN, SERVICE_LIST_FACES)

    # Clean up data
    hass.data.pop(DOMAIN, None)

    return True
