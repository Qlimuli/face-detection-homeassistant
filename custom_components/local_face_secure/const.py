"""Constants for the Local Face Secure integration."""

DOMAIN = "local_face_secure"

# Storage
STORAGE_KEY = f"{DOMAIN}.face_encodings"
STORAGE_VERSION = 1

# Services
SERVICE_TEACH_FACE = "teach_face"
SERVICE_SCAN_MATCH = "scan_match"
SERVICE_DELETE_FACE = "delete_face"
SERVICE_LIST_FACES = "list_faces"

# Service attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_NAME = "name"

# Events
EVENT_FACE_RECOGNIZED = f"{DOMAIN}.recognized"

# Event data keys
EVENT_DATA_NAME = "name"
EVENT_DATA_CONFIDENCE = "confidence"

# Face recognition settings
DEFAULT_TOLERANCE = 0.6  # Lower = stricter matching (0.0 - 1.0)
CONFIDENCE_SCALE = 100  # Scale factor for confidence percentage

# Logging prefix
LOG_PREFIX = f"[{DOMAIN}]"
