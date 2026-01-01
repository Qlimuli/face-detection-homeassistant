"""Simple Local Face Recognition for Home Assistant."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CAMERA_ENTITY,
    ATTR_IMAGE_PATH,
    ATTR_PERSON_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
    EVENT_FACE_TRAINED,
    SERVICE_CLEAR_FACES,
    SERVICE_REMOVE_FACE,
    SERVICE_TRAIN_FACE,
    STORAGE_DIR,
    STORAGE_FILE,
)

_LOGGER = logging.getLogger(__name__)

# Schema for train_face service
TRAIN_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PERSON_NAME): cv.string,
        vol.Exclusive(ATTR_IMAGE_PATH, "image_source"): cv.string,
        vol.Exclusive(ATTR_CAMERA_ENTITY, "image_source"): cv.entity_id,
    }
)

# Schema for remove_face service
REMOVE_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PERSON_NAME): cv.string,
    }
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def get_storage_path(hass: HomeAssistant) -> Path:
    """Get the path to the storage file."""
    return Path(hass.config.path(STORAGE_DIR)) / STORAGE_FILE


def load_encodings(hass: HomeAssistant) -> dict[str, list]:
    """Load face encodings from storage."""
    storage_path = get_storage_path(hass)
    if storage_path.exists():
        try:
            with open(storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as err:
            _LOGGER.error("Error loading face encodings: %s", err)
    return {}


def save_encodings(hass: HomeAssistant, encodings: dict[str, list]) -> bool:
    """Save face encodings to storage."""
    storage_path = get_storage_path(hass)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(storage_path, "w") as f:
            json.dump(encodings, f, indent=2)
        return True
    except IOError as err:
        _LOGGER.error("Error saving face encodings: %s", err)
        return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Simple Local Face Recognition from YAML."""
    hass.data.setdefault(DOMAIN, {"encodings": {}})
    
    # Load existing encodings
    encodings = await hass.async_add_executor_job(load_encodings, hass)
    hass.data[DOMAIN]["encodings"] = encodings
    _LOGGER.info("Loaded %d known faces", len(encodings))

    async def async_train_face(call: ServiceCall) -> None:
        """Handle the train_face service call."""
        person_name = call.data[ATTR_PERSON_NAME]
        image_path = call.data.get(ATTR_IMAGE_PATH)
        camera_entity = call.data.get(ATTR_CAMERA_ENTITY)

        _LOGGER.debug(
            "Training face for '%s' from %s",
            person_name,
            image_path or camera_entity,
        )

        image_data = None

        if image_path:
            # Load from file path
            if not os.path.isabs(image_path):
                image_path = hass.config.path(image_path)
            
            if not os.path.exists(image_path):
                _LOGGER.error("Image file not found: %s", image_path)
                return

            def load_image_from_file():
                with open(image_path, "rb") as f:
                    return f.read()

            image_data = await hass.async_add_executor_job(load_image_from_file)

        elif camera_entity:
            # Get image from camera entity
            camera = hass.components.camera
            try:
                image = await camera.async_get_image(camera_entity)
                image_data = image.content
            except Exception as err:
                _LOGGER.error("Error getting camera image: %s", err)
                return
        else:
            _LOGGER.error("No image source provided")
            return

        # Process the image and extract encoding
        encoding = await hass.async_add_executor_job(
            _compute_face_encoding, image_data
        )

        if encoding is None:
            _LOGGER.warning("No face found in image for '%s'", person_name)
            return

        # Store the encoding
        encodings = hass.data[DOMAIN]["encodings"]
        if person_name not in encodings:
            encodings[person_name] = []
        
        encodings[person_name].append(encoding)
        
        # Save to storage
        await hass.async_add_executor_job(save_encodings, hass, encodings)
        
        _LOGGER.info(
            "Successfully trained face for '%s' (total samples: %d)",
            person_name,
            len(encodings[person_name]),
        )

        # Fire event
        hass.bus.async_fire(
            EVENT_FACE_TRAINED,
            {
                "person_name": person_name,
                "total_samples": len(encodings[person_name]),
            },
        )

    async def async_remove_face(call: ServiceCall) -> None:
        """Handle the remove_face service call."""
        person_name = call.data[ATTR_PERSON_NAME]
        encodings = hass.data[DOMAIN]["encodings"]

        if person_name in encodings:
            del encodings[person_name]
            await hass.async_add_executor_job(save_encodings, hass, encodings)
            _LOGGER.info("Removed face data for '%s'", person_name)
        else:
            _LOGGER.warning("No face data found for '%s'", person_name)

    async def async_clear_faces(call: ServiceCall) -> None:
        """Handle the clear_faces service call."""
        hass.data[DOMAIN]["encodings"] = {}
        await hass.async_add_executor_job(save_encodings, hass, {})
        _LOGGER.info("Cleared all face data")

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_TRAIN_FACE, async_train_face, schema=TRAIN_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_FACE, async_remove_face, schema=REMOVE_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_FACES, async_clear_faces
    )

    return True


def _compute_face_encoding(image_data: bytes) -> list[float] | None:
    """Compute face encoding from image data (runs in executor)."""
    import io
    
    try:
        import face_recognition
        import numpy as np
        from PIL import Image
    except ImportError as err:
        _LOGGER.error("Required library not installed: %s", err)
        return None

    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Convert to numpy array
        image_array = np.array(image)
        
        # Find face locations
        face_locations = face_recognition.face_locations(image_array, model="hog")
        
        if not face_locations:
            _LOGGER.debug("No face detected in image")
            return None
        
        # Get encoding for the first face found
        encodings = face_recognition.face_encodings(image_array, face_locations)
        
        if encodings:
            return encodings[0].tolist()
        
        return None
        
    except Exception as err:
        _LOGGER.error("Error computing face encoding: %s", err)
        return None