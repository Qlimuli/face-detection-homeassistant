"""Face recognition image processing logic for Local Face Secure."""
from __future__ import annotations

import logging
from typing import Any
import io
import base64

import numpy as np

from homeassistant.core import HomeAssistant
from homeassistant.components.camera import async_get_image
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "local_face_secure.face_encodings"
STORAGE_VERSION = 1


class FaceRecognitionProcessor:
    """Handle face recognition processing."""

    def __init__(self, hass: HomeAssistant, default_tolerance: float = 0.6) -> None:
        """Initialize the face recognition processor."""
        self.hass = hass
        self.default_tolerance = default_tolerance
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._known_faces: dict[str, list[float]] = {}
        self._face_recognition = None

    def _ensure_face_recognition(self) -> None:
        """Lazy load face_recognition library."""
        if self._face_recognition is None:
            try:
                import face_recognition
                self._face_recognition = face_recognition
                _LOGGER.debug("face_recognition library loaded successfully")
            except ImportError as err:
                _LOGGER.error("Failed to import face_recognition: %s", err)
                raise HomeAssistantError(
                    "face_recognition library not installed. "
                    "Please install dlib and face_recognition."
                ) from err

    async def async_load_encodings(self) -> None:
        """Load face encodings from persistent storage."""
        _LOGGER.debug("Loading face encodings from storage")
        
        try:
            data = await self._store.async_load()
            
            if data is not None and "faces" in data:
                self._known_faces = data["faces"]
                _LOGGER.info(
                    "Loaded %d face encodings from storage",
                    len(self._known_faces)
                )
            else:
                self._known_faces = {}
                _LOGGER.info("No existing face encodings found")
                
        except Exception as err:
            _LOGGER.error("Error loading face encodings: %s", err)
            self._known_faces = {}

    async def async_save_encodings(self) -> None:
        """Save face encodings to persistent storage."""
        _LOGGER.debug("Saving face encodings to storage")
        
        try:
            await self._store.async_save({"faces": self._known_faces})
            _LOGGER.debug("Face encodings saved successfully")
        except Exception as err:
            _LOGGER.error("Error saving face encodings: %s", err)
            raise

    async def _async_get_camera_image(self, entity_id: str) -> bytes:
        """Get image from camera entity."""
        try:
            image = await async_get_image(self.hass, entity_id)
            return image.content
        except HomeAssistantError as err:
            _LOGGER.error("Failed to get image from camera %s: %s", entity_id, err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error getting camera image: %s", err)
            raise HomeAssistantError(f"Failed to get camera image: {err}") from err

    def _process_image_for_encoding(self, image_bytes: bytes) -> np.ndarray:
        """Convert image bytes to numpy array for face_recognition."""
        self._ensure_face_recognition()
        
        try:
            # Use PIL to load the image
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Convert to numpy array
            return np.array(image)
            
        except Exception as err:
            _LOGGER.error("Error processing image: %s", err)
            raise HomeAssistantError(f"Failed to process image: {err}") from err

    def _compute_face_encoding(self, image_array: np.ndarray) -> tuple[bool, list[float] | str]:
        """
        Compute face encoding from image array.
        
        Returns:
            Tuple of (success, encoding or error message)
        """
        self._ensure_face_recognition()
        
        try:
            # Find face locations
            face_locations = self._face_recognition.face_locations(image_array)
            
            if not face_locations:
                return False, "No face detected in the image"
            
            if len(face_locations) > 1:
                _LOGGER.warning(
                    "Multiple faces detected (%d), using the first one",
                    len(face_locations)
                )
            
            # Compute encoding for the first face
            encodings = self._face_recognition.face_encodings(
                image_array, 
                known_face_locations=[face_locations[0]]
            )
            
            if not encodings:
                return False, "Could not compute face encoding"
            
            # Convert numpy array to list for JSON serialization
            encoding_list = encodings[0].tolist()
            
            return True, encoding_list
            
        except Exception as err:
            _LOGGER.error("Error computing face encoding: %s", err)
            return False, f"Error computing encoding: {err}"

    def _compare_faces(
        self, 
        unknown_encoding: list[float], 
        tolerance: float
    ) -> tuple[bool, str | None, float | None, float | None]:
        """
        Compare unknown encoding against all known faces.
        
        Returns:
            Tuple of (matched, name, confidence, distance)
        """
        self._ensure_face_recognition()
        
        if not self._known_faces:
            return False, None, None, None
        
        try:
            unknown_np = np.array(unknown_encoding)
            
            best_match_name = None
            best_match_distance = float("inf")
            
            for name, known_encoding in self._known_faces.items():
                known_np = np.array(known_encoding)
                
                # Calculate face distance
                distances = self._face_recognition.face_distance(
                    [known_np], 
                    unknown_np
                )
                distance = distances[0]
                
                if distance < best_match_distance:
                    best_match_distance = distance
                    best_match_name = name
            
            # Check if best match is within tolerance
            if best_match_distance <= tolerance:
                # Convert distance to confidence percentage
                # Lower distance = higher confidence
                confidence = round((1 - best_match_distance) * 100, 2)
                return True, best_match_name, confidence, round(best_match_distance, 4)
            
            return False, None, None, None
            
        except Exception as err:
            _LOGGER.error("Error comparing faces: %s", err)
            return False, None, None, None

    async def async_teach_face(
        self, 
        entity_id: str, 
        name: str
    ) -> tuple[bool, str]:
        """
        Teach a new face from camera snapshot.
        
        Args:
            entity_id: Camera entity ID
            name: Name to associate with the face
            
        Returns:
            Tuple of (success, message)
        """
        _LOGGER.debug("Teaching face '%s' from camera '%s'", name, entity_id)
        
        # Get image from camera
        try:
            image_bytes = await self._async_get_camera_image(entity_id)
        except HomeAssistantError as err:
            return False, str(err)
        
        # Process image in executor to avoid blocking
        try:
            image_array = await self.hass.async_add_executor_job(
                self._process_image_for_encoding,
                image_bytes
            )
        except HomeAssistantError as err:
            return False, str(err)
        
        # Compute face encoding in executor
        success, result = await self.hass.async_add_executor_job(
            self._compute_face_encoding,
            image_array
        )
        
        if not success:
            return False, result
        
        # Store the encoding
        self._known_faces[name] = result
        
        # Save to persistent storage
        try:
            await self.async_save_encodings()
        except Exception as err:
            return False, f"Failed to save encoding: {err}"
        
        return True, f"Successfully learned face for '{name}'"

    async def async_scan_match(
        self, 
        entity_id: str, 
        tolerance: float | None = None
    ) -> dict[str, Any]:
        """
        Scan camera for face and match against known faces.
        
        Args:
            entity_id: Camera entity ID
            tolerance: Match tolerance (lower = stricter)
            
        Returns:
            Dict with match results
        """
        if tolerance is None:
            tolerance = self.default_tolerance
            
        _LOGGER.debug(
            "Scanning for face match from camera '%s' (tolerance: %s)",
            entity_id,
            tolerance
        )
        
        # Check if we have any known faces
        if not self._known_faces:
            return {
                "matched": False,
                "reason": "No known faces in database",
                "faces_detected": 0,
            }
        
        # Get image from camera
        try:
            image_bytes = await self._async_get_camera_image(entity_id)
        except HomeAssistantError as err:
            return {
                "matched": False,
                "reason": f"Camera error: {err}",
                "faces_detected": 0,
            }
        
        # Process image in executor
        try:
            image_array = await self.hass.async_add_executor_job(
                self._process_image_for_encoding,
                image_bytes
            )
        except HomeAssistantError as err:
            return {
                "matched": False,
                "reason": f"Image processing error: {err}",
                "faces_detected": 0,
            }
        
        # Compute face encoding in executor
        success, result = await self.hass.async_add_executor_job(
            self._compute_face_encoding,
            image_array
        )
        
        if not success:
            return {
                "matched": False,
                "reason": result,
                "faces_detected": 0,
            }
        
        # Compare against known faces in executor
        matched, name, confidence, distance = await self.hass.async_add_executor_job(
            self._compare_faces,
            result,
            tolerance
        )
        
        if matched:
            return {
                "matched": True,
                "name": name,
                "confidence": confidence,
                "distance": distance,
                "faces_detected": 1,
            }
        
        return {
            "matched": False,
            "reason": "Face detected but no match found",
            "faces_detected": 1,
        }

    async def async_delete_face(self, name: str) -> bool:
        """
        Delete a face encoding from storage.
        
        Args:
            name: Name of the face to delete
            
        Returns:
            True if deleted, False if not found
        """
        if name not in self._known_faces:
            return False
        
        del self._known_faces[name]
        
        try:
            await self.async_save_encodings()
        except Exception as err:
            _LOGGER.error("Error saving after deletion: %s", err)
            raise
        
        return True

    def get_known_faces(self) -> list[str]:
        """Return list of known face names."""
        return list(self._known_faces.keys())
