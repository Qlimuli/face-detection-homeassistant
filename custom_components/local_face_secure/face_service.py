"""Face recognition service logic."""
import logging
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import face_recognition
import numpy as np
from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.components.camera import async_get_image

from .const import (
    DEFAULT_TOLERANCE,
    ERROR_CAMERA_UNAVAILABLE,
    ERROR_MULTIPLE_FACES,
    ERROR_NO_FACE_DETECTED,
    ERROR_SNAPSHOT_FAILED,
    MAX_CONFIDENCE,
    MIN_CONFIDENCE,
)
from .storage import FaceStorage

_LOGGER = logging.getLogger(__name__)


class FaceRecognitionService:
    """Handle face recognition operations."""

    def __init__(self, hass: HomeAssistant, storage: FaceStorage) -> None:
        """Initialize the face recognition service."""
        self.hass = hass
        self.storage = storage
        self.tolerance = DEFAULT_TOLERANCE

    async def async_capture_and_encode_face(
        self, camera_entity_id: str
    ) -> Tuple[np.ndarray, List[float]]:
        """
        Capture image from camera and encode the face.
        
        Args:
            camera_entity_id: Entity ID of the camera
            
        Returns:
            Tuple of (image as numpy array, face encoding as list)
            
        Raises:
            ValueError: If no face or multiple faces detected
            RuntimeError: If camera snapshot fails
        """
        # Capture image from camera (must be done in event loop)
        try:
            image_bytes = await async_get_image(self.hass, camera_entity_id)
        except Exception as err:
            _LOGGER.error("Failed to get image from camera %s: %s", camera_entity_id, err)
            raise RuntimeError(ERROR_SNAPSHOT_FAILED) from err

        # Process image (CPU-bound, must run in executor)
        try:
            image, encoding = await self.hass.async_add_executor_job(
                self._process_and_encode_image, image_bytes.content
            )
        except ValueError as err:
            # Re-raise validation errors (no face, multiple faces)
            raise
        except Exception as err:
            _LOGGER.error("Error processing image: %s", err)
            raise RuntimeError(f"Error processing image: {err}") from err

        return image, encoding

    def _process_and_encode_image(
        self, image_bytes: bytes
    ) -> Tuple[np.ndarray, List[float]]:
        """
        Process image and extract face encoding (runs in executor).
        
        This method contains all CPU-bound operations and must only be called
        via async_add_executor_job.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Tuple of (image as numpy array, face encoding as list)
            
        Raises:
            ValueError: If no face or multiple faces detected
        """
        # Load image
        image = Image.open(BytesIO(image_bytes))
        image_array = np.array(image)

        # Detect faces
        face_locations = face_recognition.face_locations(image_array)

        if len(face_locations) == 0:
            _LOGGER.warning("No face detected in image")
            raise ValueError(ERROR_NO_FACE_DETECTED)

        if len(face_locations) > 1:
            _LOGGER.warning("Multiple faces detected: %d", len(face_locations))
            raise ValueError(ERROR_MULTIPLE_FACES)

        # Compute face encoding
        face_encodings = face_recognition.face_encodings(
            image_array, face_locations
        )

        if len(face_encodings) == 0:
            _LOGGER.error("Failed to compute face encoding")
            raise ValueError(ERROR_NO_FACE_DETECTED)

        # Convert numpy array to list for JSON serialization
        encoding_list = face_encodings[0].tolist()

        _LOGGER.debug("Successfully encoded face with %d features", len(encoding_list))
        return image_array, encoding_list

    async def async_teach_face(
        self, camera_entity_id: str, name: str, overwrite: bool = False
    ) -> None:
        """
        Teach the system a new face.
        
        Args:
            camera_entity_id: Camera entity to capture from
            name: Name to associate with the face
            overwrite: Whether to overwrite existing face
            
        Raises:
            ValueError: If face exists and overwrite=False, or face detection fails
            RuntimeError: If camera snapshot fails
        """
        _LOGGER.info("Teaching face for: %s", name)

        # Capture and encode face
        _, encoding = await self.async_capture_and_encode_face(camera_entity_id)

        # Save to storage
        await self.storage.async_save_face(name, encoding, overwrite=overwrite)

        _LOGGER.info("Successfully taught face: %s", name)

    async def async_recognize_face(
        self, camera_entity_id: str
    ) -> Optional[Dict[str, any]]:
        """
        Recognize a face from camera image.
        
        Args:
            camera_entity_id: Camera entity to capture from
            
        Returns:
            Dictionary with 'name' and 'confidence' if match found, None otherwise
            
        Raises:
            ValueError: If face detection fails
            RuntimeError: If camera snapshot fails
        """
        _LOGGER.debug("Starting face recognition from camera: %s", camera_entity_id)

        # Capture and encode face
        _, unknown_encoding = await self.async_capture_and_encode_face(
            camera_entity_id
        )

        # Get all known faces
        known_faces = self.storage.get_all_faces()

        if not known_faces:
            _LOGGER.info("No known faces in database")
            return None

        # Compare with known faces (CPU-bound, run in executor)
        result = await self.hass.async_add_executor_job(
            self._compare_faces, unknown_encoding, known_faces
        )

        return result

    def _compare_faces(
        self, unknown_encoding: List[float], known_faces: Dict[str, Dict]
    ) -> Optional[Dict[str, any]]:
        """
        Compare unknown face with known faces (runs in executor).
        
        Args:
            unknown_encoding: Encoding of the face to recognize
            known_faces: Dictionary of known face data
            
        Returns:
            Dictionary with 'name' and 'confidence' if match found, None otherwise
        """
        # Convert encoding back to numpy array
        unknown_encoding_array = np.array(unknown_encoding)

        best_match_name = None
        best_match_distance = float("inf")

        # Compare with each known face
        for name, face_data in known_faces.items():
            known_encoding = np.array(face_data["encoding"])

            # Calculate face distance (lower is better match)
            distance = face_recognition.face_distance(
                [known_encoding], unknown_encoding_array
            )[0]

            _LOGGER.debug("Face distance for %s: %.4f", name, distance)

            if distance < best_match_distance:
                best_match_distance = distance
                best_match_name = name

        # Check if best match is within tolerance
        if best_match_distance <= self.tolerance:
            # Convert distance to confidence percentage
            # Distance ranges from 0 (perfect match) to ~1 (no match)
            # We invert and scale to 0-100%
            confidence = (1 - best_match_distance) * 100
            confidence = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, confidence))

            _LOGGER.info(
                "Face recognized: %s (confidence: %.1f%%)",
                best_match_name,
                confidence,
            )

            return {
                "name": best_match_name,
                "confidence": round(confidence, 1),
            }

        _LOGGER.info("No matching face found (best distance: %.4f)", best_match_distance)
        return None

    async def async_delete_face(self, name: str) -> None:
        """Delete a face from storage."""
        await self.storage.async_delete_face(name)

    def list_faces(self) -> List[str]:
        """List all known face names."""
        return self.storage.list_face_names()
