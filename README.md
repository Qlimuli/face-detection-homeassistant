# Local Face Secure - Home Assistant Custom Component

A production-ready custom component for Home Assistant that implements **local face recognition** using the `face_recognition` (dlib) library. All processing runs entirely within Home Assistant - no external Docker containers required.

## Features

- ✅ **100% Local Processing** - No cloud services or external dependencies
- ✅ **Persistent Storage** - Face encodings saved to disk and survive restarts
- ✅ **Non-Blocking** - All CPU-intensive operations run in executor threads
- ✅ **Event-Driven** - Fires events for recognized faces, teaching, and errors
- ✅ **Multiple Faces** - Store and match against unlimited face encodings

## Requirements

- Home Assistant 2023.1 or later
- Camera integration (any camera entity)
- Python packages: `face_recognition`, `dlib`, `numpy`, `Pillow`

### Installing dlib (Required)

The `face_recognition` library depends on `dlib`, which requires compilation:

```bash
# Debian/Ubuntu
sudo apt-get install build-essential cmake libopenblas-dev liblapack-dev

# Then install via pip (this takes a while)
pip install dlib face_recognition
```

## Installation

1. Copy the `custom_components/local_face_secure` folder to your Home Assistant `config/custom_components/` directory.

2. Add to your `configuration.yaml`:

```yaml
local_face_secure:
  tolerance: 0.6  # Optional (default: 0.6)
```

3. Restart Home Assistant.

## Services

### `local_face_secure.teach_face`

Capture a face from a camera and learn it.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `entity_id` | Yes | Camera entity ID |
| `name` | Yes | Name for this face |

### `local_face_secure.scan_match`

Scan a camera and match against known faces.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `entity_id` | Yes | Camera entity ID |
| `tolerance` | No | Match strictness (0.1-1.0, default: 0.6) |

### `local_face_secure.delete_face`

Remove a learned face.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Name of the face to delete |

### `local_face_secure.list_faces`

List all known faces (fires `local_face_secure.faces_listed` event).

## Events

| Event | Data | Description |
|-------|------|-------------|
| `local_face_secure.recognized` | `name`, `confidence`, `distance`, `entity_id` | Face matched |
| `local_face_secure.taught` | `name`, `entity_id`, `message` | Face learned |
| `local_face_secure.no_face_found` | `entity_id`, `reason`, `faces_detected` | No match |

## Example Automation

```yaml
automation:
  - alias: "Welcome Home"
    trigger:
      - platform: event
        event_type: local_face_secure.recognized
    action:
      - service: tts.speak
        data:
          message: "Welcome home, {{ trigger.event.data.name }}!"
```

## Troubleshooting

- **"No face detected"**: Ensure good lighting and the face is clearly visible
- **"Could not compute encoding"**: Image quality may be too low
- **High CPU usage**: Normal during processing; uses executor threads to prevent blocking

## License

MIT License
