"""Constants for Simple Local Face Recognition."""
from typing import Final

DOMAIN: Final = "simple_local_face"

# Storage
STORAGE_KEY: Final = "simple_local_face_encodings"
STORAGE_VERSION: Final = 1

# Config keys
CONF_CAMERA_ENTITY: Final = "camera_entity"
CONF_TOLERANCE: Final = "tolerance"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_DETECT_UNKNOWN: Final = "detect_unknown"
CONF_MODEL: Final = "model"

# Defaults
DEFAULT_TOLERANCE: Final = 0.6
DEFAULT_SCAN_INTERVAL: Final = 10
DEFAULT_DETECT_UNKNOWN: Final = True
DEFAULT_MODEL: Final = "hog"

# Models
MODEL_HOG: Final = "hog"
MODEL_CNN: Final = "cnn"

# Service keys
SERVICE_TRAIN_FACE: Final = "train_face"
SERVICE_REMOVE_FACE: Final = "remove_face"
SERVICE_LIST_FACES: Final = "list_faces"
ATTR_PERSON_NAME: Final = "person_name"
ATTR_IMAGE_PATH: Final = "image_path"
ATTR_CAMERA_ENTITY: Final = "camera_entity"

# Events
EVENT_FACE_RECOGNIZED: Final = "face_recognized"
EVENT_FACE_DETECTED: Final = "face_detected"

# States
STATE_NO_FACE: Final = "no_face"
STATE_UNKNOWN: Final = "unknown"

# Attributes
ATTR_FACES: Final = "faces"
ATTR_TOTAL_FACES: Final = "total_faces"
ATTR_KNOWN_FACES: Final = "known_faces"
ATTR_UNKNOWN_FACES: Final = "unknown_faces"
ATTR_CONFIDENCE: Final = "confidence"
ATTR_LAST_DETECTION: Final = "last_detection"
ATTR_TRAINED_FACES: Final = "trained_faces"
