"""Storage handler for face encodings."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class FaceStorage:
    """Handle persistent storage of face encodings."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the face storage."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: Dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load face data from storage."""
        try:
            data = await self._store.async_load()
            if data is not None:
                self._data = data
                _LOGGER.info(
                    "Loaded %d face encoding(s) from storage",
                    len(self._data.get("faces", {}))
                )
            else:
                self._data = {"faces": {}}
                _LOGGER.info("No existing face data found, starting fresh")
        except Exception as err:
            _LOGGER.error("Error loading face data: %s", err)
            self._data = {"faces": {}}

    async def async_save(self) -> None:
        """Save face data to storage."""
        try:
            await self._store.async_save(self._data)
            _LOGGER.debug("Face data saved successfully")
        except Exception as err:
            _LOGGER.error("Error saving face data: %s", err)

    async def async_save_face(
        self, name: str, encoding: List[float], overwrite: bool = False
    ) -> None:
        """
        Save a face encoding.
        
        Args:
            name: Person's name
            encoding: Face encoding as a list of floats
            overwrite: Whether to overwrite existing encoding
            
        Raises:
            ValueError: If face exists and overwrite is False
        """
        if not overwrite and name in self._data["faces"]:
            raise ValueError(f"Face '{name}' already exists")

        self._data["faces"][name] = {
            "encoding": encoding,
            "name": name,
        }
        await self.async_save()
        _LOGGER.info("Saved face encoding for: %s", name)

    async def async_delete_face(self, name: str) -> None:
        """
        Delete a face encoding.
        
        Args:
            name: Person's name
            
        Raises:
            KeyError: If face doesn't exist
        """
        if name not in self._data["faces"]:
            raise KeyError(f"Face '{name}' not found")

        del self._data["faces"][name]
        await self.async_save()
        _LOGGER.info("Deleted face encoding for: %s", name)

    def get_all_faces(self) -> Dict[str, Dict[str, Any]]:
        """Get all stored face encodings."""
        return self._data.get("faces", {})

    def get_face(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific face encoding."""
        return self._data.get("faces", {}).get(name)

    def list_face_names(self) -> List[str]:
        """Get list of all face names."""
        return list(self._data.get("faces", {}).keys())
