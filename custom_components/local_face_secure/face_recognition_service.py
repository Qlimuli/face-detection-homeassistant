"""Face recognition service using the face_recognition (dlib) library."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

import numpy as np

from .const import DEFAULT_TOLERANCE, CONFIDENCE_SCALE, LOG_PREFIX

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class FaceMatch:
    """Represents a successful face match result."""
    name: str
    confidence: int  # 0-100 percentage
    distance: float  # Raw face distance (lower = better match)


@dataclass
class FaceDetectionResult:
    """Represents the result of face detection on an image."""
    success: bool
    encoding: np.ndarray | None = None
    face_count: int = 0
    error_message: str | None = None


class FaceRecognitionError(Exception):
    """Base exception for face recognition errors."""
    pass


class NoFaceDetectedError(FaceRecognitionError):
    """Raised when no face is detected in the image."""
    pass


class MultipleFacesDetectedError(FaceRecognitionError):
    """Raised when multiple faces are detected when only one is expected."""
    pass


class ImageLoadError(FaceRecognitionError):
    """Raised when the image cannot be loaded or processed."""
    pass


def _load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    """Load an image from bytes into a numpy array.
    
    This is a CPU-bound operation that should be run in an executor.
    
    Args:
        image_bytes: Raw image data (JPEG, PNG, etc.)
        
    Returns:
        Image as a numpy array suitable for face_recognition.
        
    Raises:
        ImageLoadError: If the image cannot be loaded.
    """
    import face_recognition
    from PIL import Image
    
    try:
        # Use PIL to load the image, then convert to numpy array
        # This handles various image formats (JPEG, PNG, etc.)
        pil_image = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary (face_recognition expects RGB)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        
        return np.array(pil_image)
        
    except Exception as err:
        raise ImageLoadError(f"Failed to load image: {err}") from err


def _detect_and_encode_face(image_array: np.ndarray) -> FaceDetectionResult:
    """Detect faces and compute encoding for a single face.
    
    This is a CPU-bound operation that should be run in an executor.
    Uses dlib's HOG-based face detector and 128D face encoding.
    
    Args:
        image_array: Image as a numpy array (RGB format).
        
    Returns:
        FaceDetectionResult with encoding if exactly one face found.
    """
    import face_recognition
    
    try:
        # Detect face locations first (using HOG for speed)
        # model="hog" is faster, model="cnn" is more accurate but needs GPU
        face_locations = face_recognition.face_locations(image_array, model="hog")
        face_count = len(face_locations)
        
        if face_count == 0:
            return FaceDetectionResult(
                success=False,
                face_count=0,
                error_message="No face detected in the image"
            )
        
        if face_count > 1:
            return FaceDetectionResult(
                success=False,
                face_count=face_count,
                error_message=f"Multiple faces detected ({face_count}), expected exactly one"
            )
        
        # Compute the 128-dimensional face encoding
        # known_face_locations speeds up encoding by skipping detection
        encodings = face_recognition.face_encodings(
            image_array,
            known_face_locations=face_locations
        )
        
        if not encodings:
            return FaceDetectionResult(
                success=False,
                face_count=face_count,
                error_message="Face detected but encoding failed"
            )
        
        return FaceDetectionResult(
            success=True,
            encoding=encodings[0],
            face_count=1
        )
        
    except Exception as err:
        _LOGGER.error("%s Face detection error: %s", LOG_PREFIX, err)
        return FaceDetectionResult(
            success=False,
            error_message=f"Face detection failed: {err}"
        )


def _compare_faces(
    image_array: np.ndarray,
    known_encodings: dict[str, np.ndarray],
    tolerance: float = DEFAULT_TOLERANCE
) -> list[FaceMatch]:
    """Compare faces in an image against known encodings.
    
    This is a CPU-bound operation that should be run in an executor.
    
    Args:
        image_array: Image as a numpy array (RGB format).
        known_encodings: Dictionary mapping names to face encodings.
        tolerance: How strict the matching should be (lower = stricter).
        
    Returns:
        List of FaceMatch objects for all matched faces, sorted by confidence.
    """
    import face_recognition
    
    if not known_encodings:
        _LOGGER.debug("%s No known faces to compare against", LOG_PREFIX)
        return []
    
    try:
        # Detect all faces in the image
        face_locations = face_recognition.face_locations(image_array, model="hog")
        
        if not face_locations:
            _LOGGER.debug("%s No faces detected in scan image", LOG_PREFIX)
            return []
        
        # Get encodings for all detected faces
        detected_encodings = face_recognition.face_encodings(
            image_array,
            known_face_locations=face_locations
        )
        
        if not detected_encodings:
            return []
        
        matches: list[FaceMatch] = []
        known_names = list(known_encodings.keys())
        known_encoding_arrays = list(known_encodings.values())
        
        # Compare each detected face against all known faces
        for face_encoding in detected_encodings:
            # Calculate face distances (lower = more similar)
            # This is more informative than boolean compare_faces
            distances = face_recognition.face_distance(
                known_encoding_arrays,
                face_encoding
            )
            
            # Find the best match (lowest distance)
            if len(distances) > 0:
                best_match_idx = np.argmin(distances)
                best_distance = distances[best_match_idx]
                
                # Only accept matches within tolerance
                if best_distance <= tolerance:
                    # Convert distance to confidence percentage
                    # Distance of 0 = 100% confidence, distance of tolerance = ~50%
                    confidence = int(
                        (1 - (best_distance / tolerance)) * CONFIDENCE_SCALE
                    )
                    confidence = max(0, min(CONFIDENCE_SCALE, confidence))
                    
                    matches.append(FaceMatch(
                        name=known_names[best_match_idx],
                        confidence=confidence,
                        distance=float(best_distance)
                    ))
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
        
    except Exception as err:
        _LOGGER.error("%s Face comparison error: %s", LOG_PREFIX, err)
        return []


class FaceRecognitionProcessor:
    """High-level face recognition processor for Home Assistant.
    
    All CPU-bound operations are wrapped to run in the executor
    to avoid blocking the event loop.
    """

    def __init__(self, hass: HomeAssistant, tolerance: float = DEFAULT_TOLERANCE) -> None:
        """Initialize the face recognition processor.
        
        Args:
            hass: Home Assistant instance for executor access.
            tolerance: Face matching tolerance (0.0 - 1.0, lower = stricter).
        """
        self._hass = hass
        self._tolerance = tolerance

    async def async_detect_and_encode(
        self,
        image_bytes: bytes
    ) -> FaceDetectionResult:
        """Detect and encode a face from image bytes.
        
        Runs CPU-bound operations in the executor to avoid blocking.
        
        Args:
            image_bytes: Raw image data.
            
        Returns:
            FaceDetectionResult with encoding if successful.
        """
        try:
            # Load image in executor (CPU-bound)
            image_array = await self._hass.async_add_executor_job(
                _load_image_from_bytes,
                image_bytes
            )
            
            # Detect and encode in executor (CPU-bound)
            result = await self._hass.async_add_executor_job(
                _detect_and_encode_face,
                image_array
            )
            
            return result
            
        except ImageLoadError as err:
            return FaceDetectionResult(
                success=False,
                error_message=str(err)
            )
        except Exception as err:
            _LOGGER.error("%s Unexpected error in face detection: %s", LOG_PREFIX, err)
            return FaceDetectionResult(
                success=False,
                error_message=f"Unexpected error: {err}"
            )

    async def async_find_matches(
        self,
        image_bytes: bytes,
        known_encodings: dict[str, np.ndarray]
    ) -> list[FaceMatch]:
        """Find face matches in an image against known encodings.
        
        Runs CPU-bound operations in the executor to avoid blocking.
        
        Args:
            image_bytes: Raw image data.
            known_encodings: Dictionary of known face encodings.
            
        Returns:
            List of FaceMatch objects for matched faces.
        """
        try:
            # Load image in executor (CPU-bound)
            image_array = await self._hass.async_add_executor_job(
                _load_image_from_bytes,
                image_bytes
            )
            
            # Compare faces in executor (CPU-bound)
            matches = await self._hass.async_add_executor_job(
                _compare_faces,
                image_array,
                known_encodings,
                self._tolerance
            )
            
            return matches
            
        except ImageLoadError as err:
            _LOGGER.error("%s Failed to load image for matching: %s", LOG_PREFIX, err)
            return []
        except Exception as err:
            _LOGGER.error("%s Unexpected error in face matching: %s", LOG_PREFIX, err)
            return []
