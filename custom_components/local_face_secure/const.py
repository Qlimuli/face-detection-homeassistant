"""Constants for the Local Face Secure integration."""

DOMAIN = "local_face_secure"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.faces"

# Services
SERVICE_TEACH_FACE = "teach_face"
SERVICE_SCAN_MATCH = "scan_match"
SERVICE_DELETE_FACE = "delete_face"
SERVICE_LIST_FACES = "list_faces"

# Service attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_NAME = "name"
ATTR_CONFIDENCE = "confidence"

# Events
EVENT_FACE_RECOGNIZED = f"{DOMAIN}.recognized"
EVENT_FACE_TAUGHT = f"{DOMAIN}.face_taught"
EVENT_FACE_DELETED = f"{DOMAIN}.face_deleted"

# Face recognition settings
DEFAULT_TOLERANCE = 0.6  # Lower = more strict matching
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 100.0

# Error messages
ERROR_NO_FACE_DETECTED = "No face detected in image"
ERROR_MULTIPLE_FACES = "Multiple faces detected, please ensure only one face is visible"
ERROR_CAMERA_UNAVAILABLE = "Camera entity is unavailable"
ERROR_SNAPSHOT_FAILED = "Failed to capture camera snapshot"
ERROR_FACE_EXISTS = "Face with this name already exists"
ERROR_FACE_NOT_FOUND = "Face not found"
ERROR_INVALID_CAMERA = "Invalid camera entity"
