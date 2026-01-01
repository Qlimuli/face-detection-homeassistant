"""Image processing platform for Simple Local Face Recognition."""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.const import ATTR_NAME, CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_TOLERANCE,
    DEFAULT_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
    EVENT_FACE_DETECTED,
    EVENT_FACE_RECOGNIZED,
    STATE_DETECTED,
    STATE_IDLE,
    STATE_NO_FACE,
    STATE_SCANNING,
    STATE_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the face recognition image processing platform."""
    # Ensure domain data exists
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"encodings": {}}

    tolerance = config[CONF_TOLERANCE]
    entities = []

    for camera in config[CONF_SOURCE]:
        entities.append(
            LocalFaceRecognitionEntity(
                hass=hass,
                camera_entity=camera[CONF_ENTITY_ID],
                name=camera.get(CONF_NAME, config.get(CONF_NAME, DEFAULT_NAME)),
                tolerance=tolerance,
            )
        )

    async_add_entities(entities, True)


class LocalFaceRecognitionEntity(ImageProcessingFaceEntity):
    """Entity for local face recognition processing."""

    def __init__(
        self,
        hass: HomeAssistant,
        camera_entity: str,
        name: str,
        tolerance: float,
    ) -> None:
        """Initialize the face recognition entity."""
        super().__init__()
        self.hass = hass
        self._camera_entity = camera_entity
        self._name = name
        self._tolerance = tolerance
        self._state = STATE_IDLE
        self._faces: list[dict[str, Any]] = []
        self._total_faces = 0
        self._last_detection: datetime | None = None
        self._matched_faces: list[str] = []
        self._confidence: float | None = None

        # Generate unique ID based on camera entity
        camera_name = split_entity_id(camera_entity)[1]
        self._attr_unique_id = f"local_face_{camera_name}"

    @property
    def camera_entity(self) -> str:
        """Return the camera entity ID."""
        return self._camera_entity

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if self._matched_faces:
            return self._matched_faces[0]
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "camera_entity": self._camera_entity,
            "tolerance": self._tolerance,
            "total_faces_detected": self._total_faces,
            "matched_faces": self._matched_faces,
            "faces": self._faces,
            "known_faces_count": len(self.hass.data.get(DOMAIN, {}).get("encodings", {})),
        }
        
        if self._last_detection:
            attrs["last_detection"] = self._last_detection.isoformat()
        
        if self._confidence is not None:
            attrs["confidence"] = round(self._confidence, 3)
            
        return attrs

    @property
    def total_faces(self) -> int:
        """Return the total number of faces detected."""
        return self._total_faces

    @property
    def faces(self) -> list[dict[str, Any]]:
        """Return the list of detected faces."""
        return self._faces

    async def async_process_image(self, image: bytes) -> None:
        """Process an image for face recognition."""
        self._state = STATE_SCANNING
        self.async_write_ha_state()

        # Get known encodings
        known_encodings = self.hass.data.get(DOMAIN, {}).get("encodings", {})

        if not known_encodings:
            _LOGGER.debug("No known faces to match against")

        # Run face recognition in executor to avoid blocking
        result = await self.hass.async_add_executor_job(
            self._process_image_sync,
            image,
            known_encodings,
            self._tolerance,
        )

        # Update state based on results
        self._faces = result["faces"]
        self._total_faces = result["total_faces"]
        self._matched_faces = result["matched_names"]
        self._confidence = result.get("best_confidence")

        if self._total_faces == 0:
            self._state = STATE_NO_FACE
        elif self._matched_faces:
            self._state = STATE_DETECTED
            self._last_detection = datetime.now()
            
            # Fire event for each recognized face
            for face_data in self._faces:
                if face_data.get("name") and face_data["name"] != "unknown":
                    self.hass.bus.async_fire(
                        EVENT_FACE_RECOGNIZED,
                        {
                            "entity_id": self.entity_id,
                            "name": face_data["name"],
                            "confidence": face_data.get("confidence", 0),
                            "camera_entity": self._camera_entity,
                        },
                    )
        else:
            self._state = STATE_UNKNOWN
            # Fire generic face detected event
            self.hass.bus.async_fire(
                EVENT_FACE_DETECTED,
                {
                    "entity_id": self.entity_id,
                    "total_faces": self._total_faces,
                    "camera_entity": self._camera_entity,
                },
            )

        self.async_write_ha_state()

    @staticmethod
    def _process_image_sync(
        image_data: bytes,
        known_encodings: dict[str, list],
        tolerance: float,
    ) -> dict[str, Any]:
        """Process image synchronously (runs in executor)."""
        import numpy as np
        
        try:
            import face_recognition
            from PIL import Image
        except ImportError as err:
            _LOGGER.error("Required library not installed: %s", err)
            return {
                "faces": [],
                "total_faces": 0,
                "matched_names": [],
                "best_confidence": None,
            }

        result = {
            "faces": [],
            "total_faces": 0,
            "matched_names": [],
            "best_confidence": None,
        }

        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            image_array = np.array(image)
            
            # Detect faces - use HOG for speed, CNN for accuracy
            face_locations = face_recognition.face_locations(image_array, model="hog")
            
            if not face_locations:
                _LOGGER.debug("No faces detected in image")
                return result
            
            result["total_faces"] = len(face_locations)
            
            # Get encodings for detected faces
            detected_encodings = face_recognition.face_encodings(
                image_array, face_locations
            )
            
            # Prepare known face data for comparison
            known_names = []
            known_encoding_list = []
            
            for name, encodings in known_encodings.items():
                for encoding in encodings:
                    known_names.append(name)
                    known_encoding_list.append(np.array(encoding))
            
            best_overall_confidence = 0.0
            
            # Process each detected face
            for idx, (face_location, face_encoding) in enumerate(
                zip(face_locations, detected_encodings)
            ):
                top, right, bottom, left = face_location
                
                face_data = {
                    "index": idx,
                    "location": {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left,
                    },
                    "name": "unknown",
                    "confidence": 0.0,
                }
                
                if known_encoding_list:
                    # Compare against known faces
                    distances = face_recognition.face_distance(
                        known_encoding_list, face_encoding
                    )
                    
                    if len(distances) > 0:
                        best_match_idx = np.argmin(distances)
                        best_distance = distances[best_match_idx]
                        
                        # Convert distance to confidence (0-1, where 1 is perfect match)
                        confidence = max(0, 1 - best_distance)
                        
                        if best_distance <= tolerance:
                            matched_name = known_names[best_match_idx]
                            face_data["name"] = matched_name
                            face_data["confidence"] = round(confidence, 3)
                            face_data["distance"] = round(best_distance, 3)
                            
                            if matched_name not in result["matched_names"]:
                                result["matched_names"].append(matched_name)
                            
                            if confidence > best_overall_confidence:
                                best_overall_confidence = confidence
                        else:
                            face_data["confidence"] = round(confidence, 3)
                            face_data["distance"] = round(best_distance, 3)
                            _LOGGER.debug(
                                "Face %d: best match '%s' with distance %.3f "
                                "(above tolerance %.3f)",
                                idx,
                                known_names[best_match_idx],
                                best_distance,
                                tolerance,
                            )
                
                result["faces"].append(face_data)
            
            if best_overall_confidence > 0:
                result["best_confidence"] = best_overall_confidence
            
            _LOGGER.debug(
                "Processed image: %d faces, matched: %s",
                result["total_faces"],
                result["matched_names"],
            )
            
        except Exception as err:
            _LOGGER.error("Error processing image: %s", err)
        
        return result