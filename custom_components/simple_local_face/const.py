"""Constants for Simple Local Face Recognition."""

DOMAIN = "simple_local_face"

# Storage
STORAGE_DIR = ".storage"
STORAGE_FILE = "simple_local_face_encodings.json"

# Configuration keys
CONF_TOLERANCE = "tolerance"
CONF_SOURCE = "source"
CONF_NAME = "name"

# Defaults
DEFAULT_TOLERANCE = 0.6
DEFAULT_NAME = "Simple Local Face"

# Services
SERVICE_TRAIN_FACE = "train_face"
SERVICE_REMOVE_FACE = "remove_face"
SERVICE_CLEAR_FACES = "clear_faces"

# Service attributes
ATTR_IMAGE_PATH = "image_path"
ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_PERSON_NAME = "person_name"

# Events
EVENT_FACE_RECOGNIZED = "face_recognized"
EVENT_FACE_DETECTED = "face_detected"
EVENT_FACE_TRAINED = "face_trained"

# States
STATE_IDLE = "idle"
STATE_SCANNING = "scanning"
STATE_DETECTED = "detected"
STATE_NO_FACE = "no_face"
STATE_UNKNOWN = "unknown"