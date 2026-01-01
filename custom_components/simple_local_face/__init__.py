"""Simple Local Face Recognition for Home Assistant."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.components.camera import async_get_image

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    SERVICE_TRAIN_FACE,
    SERVICE_REMOVE_FACE,
    SERVICE_LIST_FACES,
    ATTR_PERSON_NAME,
    ATTR_IMAGE_PATH,
    ATTR_CAMERA_ENTITY,
    DEFAULT_MODEL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.IMAGE_PROCESSING]

# Service schemas
TRAIN_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PERSON_NAME): cv.string,
        vol.Optional(ATTR_IMAGE_PATH): cv.string,
        vol.Optional(ATTR_CAMERA_ENTITY): cv.entity_id,
    }
)

REMOVE_FACE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PERSON_NAME): cv.string,
    }
)


class FaceEncodingStore:
    """Class to manage face encoding storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, list[list[float]]] = {}
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load data from storage."""
        data = await self._store.async_load()
        if data:
            self._data = data
        else:
            self._data = {}

    async def async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self._data)

    @property
    def encodings(self) -> dict[str, list[list[float]]]:
        """Return all encodings."""
        return self._data

    async def async_add_encoding(
        self, name: str, encoding: list[float]
    ) -> None:
        """Add a face encoding for a person."""
        async with self._lock:
            if name not in self._data:
                self._data[name] = []
            self._data[name].append(encoding)
            await self.async_save()

    async def async_remove_person(self, name: str) -> bool:
        """Remove all encodings for a person."""
        async with self._lock:
            if name in self._data:
                del self._data[name]
                await self.async_save()
                return True
            return False

    def get_all_names(self) -> list[str]:
        """Get all trained person names."""
        return list(self._data.keys())

    def get_encoding_count(self, name: str) -> int:
        """Get the number of encodings for a person."""
        return len(self._data.get(name, []))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Simple Local Face Recognition component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simple Local Face Recognition from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Initialize storage
    store = FaceEncodingStore(hass)
    await store.async_load()
    
    hass.data[DOMAIN][entry.entry_id] = {
        "store": store,
        "config": entry.data,
    }
    hass.data[DOMAIN]["store"] = store

    # Register services
    await _async_register_services(hass)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options update
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Remove services if no more entries
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_TRAIN_FACE)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_FACE)
            hass.services.async_remove(DOMAIN, SERVICE_LIST_FACES)
            hass.data[DOMAIN].pop("store", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register services for face recognition."""
    
    if hass.services.has_service(DOMAIN, SERVICE_TRAIN_FACE):
        return

    async def async_train_face(call: ServiceCall) -> None:
        """Train a face from an image."""
        person_name = call.data[ATTR_PERSON_NAME]
        image_path = call.data.get(ATTR_IMAGE_PATH)
        camera_entity = call.data.get(ATTR_CAMERA_ENTITY)

        if not image_path and not camera_entity:
            _LOGGER.error("Either image_path or camera_entity must be provided")
            return

        store: FaceEncodingStore = hass.data[DOMAIN].get("store")
        if not store:
            _LOGGER.error("Face recognition store not initialized")
            return

        image_data = None

        # Get image from camera
        if camera_entity:
            try:
                camera_image = await async_get_image(hass, camera_entity)
                image_data = camera_image.content
            except Exception as err:
                _LOGGER.error("Failed to get image from camera %s: %s", camera_entity, err)
                return
        
        # Get image from file
        elif image_path:
            try:
                def read_image():
                    with open(image_path, "rb") as f:
                        return f.read()
                image_data = await hass.async_add_executor_job(read_image)
            except Exception as err:
                _LOGGER.error("Failed to read image file %s: %s", image_path, err)
                return

        if not image_data:
            _LOGGER.error("No image data available")
            return

        # Process image and extract face encoding
        def process_image():
            import face_recognition
            import numpy as np
            
            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            import cv2
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return None
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Find faces and get encodings
            face_locations = face_recognition.face_locations(rgb_image, model=DEFAULT_MODEL)
            
            if not face_locations:
                return None
            
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            if not face_encodings:
                return None
            
            # Return the first face encoding as list
            return face_encodings[0].tolist()

        encoding = await hass.async_add_executor_job(process_image)

        if encoding:
            await store.async_add_encoding(person_name, encoding)
            _LOGGER.info(
                "Successfully trained face for %s (total encodings: %d)",
                person_name,
                store.get_encoding_count(person_name),
            )
            
            # Fire event
            hass.bus.async_fire(
                f"{DOMAIN}_face_trained",
                {
                    "person_name": person_name,
                    "encoding_count": store.get_encoding_count(person_name),
                },
            )
        else:
            _LOGGER.error("No face found in the provided image for %s", person_name)

    async def async_remove_face(call: ServiceCall) -> None:
        """Remove a trained face."""
        person_name = call.data[ATTR_PERSON_NAME]
        
        store: FaceEncodingStore = hass.data[DOMAIN].get("store")
        if not store:
            _LOGGER.error("Face recognition store not initialized")
            return

        if await store.async_remove_person(person_name):
            _LOGGER.info("Removed face data for %s", person_name)
            hass.bus.async_fire(
                f"{DOMAIN}_face_removed",
                {"person_name": person_name},
            )
        else:
            _LOGGER.warning("No face data found for %s", person_name)

    async def async_list_faces(call: ServiceCall) -> None:
        """List all trained faces."""
        store: FaceEncodingStore = hass.data[DOMAIN].get("store")
        if not store:
            _LOGGER.error("Face recognition store not initialized")
            return

        names = store.get_all_names()
        face_info = {
            name: store.get_encoding_count(name) for name in names
        }
        
        hass.bus.async_fire(
            f"{DOMAIN}_faces_listed",
            {"faces": face_info, "total_persons": len(names)},
        )
        _LOGGER.info("Trained faces: %s", face_info)

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_TRAIN_FACE, async_train_face, schema=TRAIN_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_FACE, async_remove_face, schema=REMOVE_FACE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_FACES, async_list_faces, schema=None
    )
