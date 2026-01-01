"""Persistent storage handler for face encodings."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION, LOG_PREFIX

_LOGGER = logging.getLogger(__name__)


class FaceEncodingStore:
    """Class to manage persistent storage of face encodings.
    
    Face encodings are numpy arrays that need to be converted to lists
    for JSON serialization. This class handles the conversion automatically.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the face encoding store.
        
        Args:
            hass: Home Assistant instance for storage access.
        """
        self._hass = hass
        # Home Assistant's Store helper handles JSON persistence automatically
        # Data is stored in .storage/local_face_secure.face_encodings
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        # In-memory cache of face encodings (name -> numpy array)
        self._encodings: dict[str, np.ndarray] = {}

    async def async_load(self) -> None:
        """Load face encodings from persistent storage.
        
        This should be called during component setup to restore
        previously learned faces after Home Assistant restarts.
        """
        try:
            data = await self._store.async_load()
            
            if data is None:
                _LOGGER.debug("%s No existing face data found, starting fresh", LOG_PREFIX)
                self._encodings = {}
                return

            # Convert stored lists back to numpy arrays
            self._encodings = {}
            faces_data = data.get("faces", {})
            
            for name, encoding_list in faces_data.items():
                try:
                    # Validate encoding data before conversion
                    if not isinstance(encoding_list, list):
                        _LOGGER.warning(
                            "%s Invalid encoding format for '%s', skipping",
                            LOG_PREFIX, name
                        )
                        continue
                    
                    self._encodings[name] = np.array(encoding_list, dtype=np.float64)
                    _LOGGER.debug("%s Loaded face encoding for '%s'", LOG_PREFIX, name)
                except (ValueError, TypeError) as err:
                    _LOGGER.warning(
                        "%s Failed to load encoding for '%s': %s",
                        LOG_PREFIX, name, err
                    )

            _LOGGER.info(
                "%s Loaded %d face encoding(s) from storage",
                LOG_PREFIX, len(self._encodings)
            )

        except Exception as err:
            # Handle corrupt storage gracefully - start fresh rather than crash
            _LOGGER.error(
                "%s Error loading face encodings, starting fresh: %s",
                LOG_PREFIX, err
            )
            self._encodings = {}

    async def async_save(self) -> None:
        """Save face encodings to persistent storage.
        
        Converts numpy arrays to lists for JSON serialization.
        """
        try:
            # Convert numpy arrays to lists for JSON serialization
            faces_data = {
                name: encoding.tolist()
                for name, encoding in self._encodings.items()
            }
            
            await self._store.async_save({"faces": faces_data})
            _LOGGER.debug(
                "%s Saved %d face encoding(s) to storage",
                LOG_PREFIX, len(self._encodings)
            )

        except Exception as err:
            _LOGGER.error("%s Failed to save face encodings: %s", LOG_PREFIX, err)
            raise

    def add_encoding(self, name: str, encoding: np.ndarray) -> None:
        """Add or update a face encoding in memory.
        
        Args:
            name: Identifier for the face (e.g., person's name).
            encoding: 128-dimensional face encoding from face_recognition.
        """
        self._encodings[name] = encoding

    def remove_encoding(self, name: str) -> bool:
        """Remove a face encoding from memory.
        
        Args:
            name: Identifier of the face to remove.
            
        Returns:
            True if the face was found and removed, False otherwise.
        """
        if name in self._encodings:
            del self._encodings[name]
            return True
        return False

    def get_all_encodings(self) -> dict[str, np.ndarray]:
        """Get all stored face encodings.
        
        Returns:
            Dictionary mapping names to their face encodings.
        """
        return self._encodings.copy()

    def get_encoding(self, name: str) -> np.ndarray | None:
        """Get a specific face encoding by name.
        
        Args:
            name: Identifier of the face to retrieve.
            
        Returns:
            The face encoding array, or None if not found.
        """
        return self._encodings.get(name)

    def get_names(self) -> list[str]:
        """Get list of all stored face names.
        
        Returns:
            List of all face identifiers.
        """
        return list(self._encodings.keys())

    @property
    def count(self) -> int:
        """Get the number of stored face encodings."""
        return len(self._encodings)
