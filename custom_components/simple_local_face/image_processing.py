"""Image processing platform for Simple Local Face Recognition."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from homeassistant.components.image_processing import (
    ImageProcessingFaceEntity,
    FaceInformation,
)
from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import FaceEncodingStore
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
    EVENT_FACE_RECOGNIZED,
    EVENT_FACE_DETECTED,
    STATE_NO_FACE,
    STATE_UNKNOWN,
    ATTR_FACES,
    ATTR_TOTAL_FACES,
    ATTR_KNOWN_FACES,
    ATTR_UNKNOWN_FACES,
    ATTR_CONFIDENCE,
    ATTR_LAST_DETECTION,
    ATTR_TRAINED_FACES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the face recognition image processing platform."""
    camera_entity = config_entry.data[CONF_CAMERA_ENTITY]
    tolerance = config_entry.data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)
    scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    detect_unknown = config_entry.data.get(CONF_DETECT_UNKNOWN, DEFAULT_DETECT_UNKNOWN)
    model = config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

    store: FaceEncodingStore = hass.data[DOMAIN][config_entry.entry_id]["store"]

    entity = SimpleFaceRecognitionEntity(
        hass=hass,
        camera_entity=camera_entity,
        store=store,
        tolerance=tolerance,
        scan_interval=scan_interval,
        detect_unknown=detect_unknown,
        model=model,
        config_entry_id=config_entry.entry_id,
    )

    async_add_entities([entity], True)


class SimpleFaceRecognitionEntity(ImageProcessingFaceEntity):
    """Face recognition image processing entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        camera_entity: str,
        store: FaceEncodingStore,
        tolerance: float,
        scan_interval: int,
        detect_unknown: bool,
        model: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the face recognition entity."""
        self.hass = hass
        self._camera_entity = camera_entity
        self._store = store
        self._tolerance = tolerance
        self._scan_interval = scan_interval
        self._detect_unknown = detect_unknown
        self._model = model
        self._config_entry_id = config_entry_id

        # Entity attributes
        camera_name = camera_entity.split(".")[-1].replace("_", " ").title()
        self._attr_name = f"Face Recognition {camera_name}"
        self._attr_unique_id = f"{DOMAIN}_{camera_entity}"

        # State
        self._state = STATE_NO_FACE
        self._faces: list[dict[str, Any]] = []
        self._total_faces = 0
        self._known_faces = 0
        self._unknown_faces = 0
        self._last_detection: datetime | None = None
        self._processing = False

        # Cleanup
        self._remove_interval_listener = None

    @property
    def camera_entity(self) -> str:
        """Return camera entity id."""
        return self._camera_entity

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            ATTR_FACES: self._faces,
            ATTR_TOTAL_FACES: self._total_faces,
            ATTR_KNOWN_FACES: self._known_faces,
            ATTR_UNKNOWN_FACES: self._unknown_faces,
            ATTR_LAST_DETECTION: self._last_detection.isoformat() if self._last_detection else None,
            ATTR_TRAINED_FACES: self._store.get_all_names(),
            "camera_entity": self._camera_entity,
            "tolerance": self._tolerance,
            "model": self._model,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()

        # Set up periodic scanning
        if self._scan_interval > 0:
            self._remove_interval_listener = async_track_time_interval(
                self.hass,
                self._async_scheduled_scan,
                timedelta(seconds=self._scan_interval),
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is removed from hass."""
        if self._remove_interval_listener:
            self._remove_interval_listener()
            self._remove_interval_listener = None

    async def _async_scheduled_scan(self, now: datetime) -> None:
        """Handle scheduled scan."""
        await self.async_update()

    async def async_update(self) -> None:
        """Update the entity by processing camera image."""
        if self._processing:
            _LOGGER.debug("Already processing, skipping")
            return

        self._processing = True

        try:
            # Get image from camera
            try:
                camera_image = await async_get_image(self.hass, self._camera_entity)
                image_data = camera_image.content
            except Exception as err:
                _LOGGER.error("Failed to get image from %s: %s", self._camera_entity, err)
                return

            # Process image in executor
            result = await self.hass.async_add_executor_job(
                self._process_image, image_data
            )

            if result is None:
                return

            # Update state
            self._faces = result["faces"]
            self._total_faces = result["total_faces"]
            self._known_faces = result["known_faces"]
            self._unknown_faces = result["unknown_faces"]

            if self._total_faces == 0:
                self._state = STATE_NO_FACE
            elif self._known_faces > 0:
                # Set state to first recognized person
                known_names = [f["name"] for f in self._faces if f["name"] != STATE_UNKNOWN]
                self._state = known_names[0] if known_names else STATE_UNKNOWN
                self._last_detection = datetime.now()

                # Fire events for recognized faces
                for face in self._faces:
                    if face["name"] != STATE_UNKNOWN:
                        self.hass.bus.async_fire(
                            EVENT_FACE_RECOGNIZED,
                            {
                                "entity_id": self.entity_id,
                                "camera_entity": self._camera_entity,
                                "name": face["name"],
                                "confidence": face["confidence"],
                            },
                        )
            else:
                self._state = STATE_UNKNOWN
                self._last_detection = datetime.now()

                if self._detect_unknown:
                    self.hass.bus.async_fire(
                        EVENT_FACE_DETECTED,
                        {
                            "entity_id": self.entity_id,
                            "camera_entity": self._camera_entity,
                            "unknown_count": self._unknown_faces,
                        },
                    )

            # Call parent to process faces
            faces_info = [
                FaceInformation(
                    confidence=face.get("confidence", 0),
                    name=face.get("name"),
                )
                for face in self._faces
            ]
            self.process_faces(faces_info, self._total_faces)

        except Exception as err:
            _LOGGER.error("Error processing image: %s", err)
        finally:
            self._processing = False

    def _process_image(self, image_data: bytes) -> dict[str, Any] | None:
        """Process image and detect faces (runs in executor)."""
        try:
            import face_recognition
            import cv2

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                _LOGGER.error("Failed to decode image")
                return None

            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Detect faces
            face_locations = face_recognition.face_locations(rgb_image, model=self._model)

            if not face_locations:
                return {
                    "faces": [],
                    "total_faces": 0,
                    "known_faces": 0,
                    "unknown_faces": 0,
                }

            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

            # Get stored encodings
            stored_encodings = self._store.encodings
            known_names = list(stored_encodings.keys())
            known_encodings_flat = []
            known_names_flat = []

            for name, encodings in stored_encodings.items():
                for encoding in encodings:
                    known_encodings_flat.append(np.array(encoding))
                    known_names_flat.append(name)

            # Match faces
            faces = []
            known_count = 0
            unknown_count = 0

            for face_encoding, face_location in zip(face_encodings, face_locations):
                name = STATE_UNKNOWN
                confidence = 0.0

                if known_encodings_flat:
                    # Compare with known faces
                    face_distances = face_recognition.face_distance(
                        known_encodings_flat, face_encoding
                    )
                    
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        best_distance = face_distances[best_match_index]

                        if best_distance <= self._tolerance:
                            name = known_names_flat[best_match_index]
                            confidence = round(1.0 - best_distance, 2)
                            known_count += 1
                        else:
                            unknown_count += 1
                    else:
                        unknown_count += 1
                else:
                    unknown_count += 1

                # Get face location
                top, right, bottom, left = face_location

                faces.append({
                    "name": name,
                    "confidence": confidence,
                    "location": {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left,
                    },
                })

            return {
                "faces": faces,
                "total_faces": len(face_encodings),
                "known_faces": known_count,
                "unknown_faces": unknown_count,
            }

        except Exception as err:
            _LOGGER.error("Error in face processing: %s", err)
            return None

    async def async_process_image(self, image: bytes) -> None:
        """Process an image from service call."""
        # This method is called by the image_processing.scan service
        await self.async_update()
