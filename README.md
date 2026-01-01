# Local Face Secure - Home Assistant Custom Component

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

A production-ready Home Assistant custom component for local face recognition using the `face_recognition` (dlib) library. All processing runs entirely inside Home Assistant with no external services required.

## Features

- 🔒 **100% Local** - All face recognition runs locally, no cloud services
- 🎯 **High Accuracy** - Uses dlib's state-of-the-art face recognition
- 💾 **Persistent Storage** - Face encodings survive restarts
- 🔄 **Async Architecture** - Non-blocking, event-loop safe implementation
- 📡 **Event-Driven** - Fires events when faces are recognized
- 🛡️ **Robust Error Handling** - Gracefully handles all edge cases

## Requirements

- Home Assistant 2023.1 or newer
- Camera entity in Home Assistant
- Sufficient CPU for face recognition (Raspberry Pi 4+ recommended)

## Installation

### Manual Installation

1. Download this repository
2. Copy the `local_face_secure` folder to your Home Assistant `custom_components` directory:
   ```
   /config/custom_components/local_face_secure/
   ```
3. Restart Home Assistant
4. Add the integration to your `configuration.yaml`:
   ```yaml
   local_face_secure:
   ```
5. Restart Home Assistant again

### Dependencies

The component automatically installs the required `face_recognition` library. On first load, this may take several minutes as it compiles dlib.

**Note for Raspberry Pi users**: You may need to install some system dependencies first:
```bash
sudo apt-get install build-essential cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev
```

## Configuration

Add to your `configuration.yaml`:

```yaml
local_face_secure:
```

That's it! No additional configuration needed.

## Usage

### Services

#### `local_face_secure.teach_face`

Teach the system a new face by capturing from a camera.

**Parameters:**
- `entity_id` (required): Camera entity to capture from
- `name` (required): Name to associate with the face

**Example:**
```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.front_door
  name: Stefan
```

**Important:**
- Ensure only ONE face is visible in the camera frame
- Face should be well-lit and clearly visible
- Person should look directly at the camera

#### `local_face_secure.scan_match`

Scan a camera image and match against known faces.

**Parameters:**
- `entity_id` (required): Camera entity to capture from

**Example:**
```yaml
service: local_face_secure.scan_match
data:
  entity_id: camera.front_door
```

**Behavior:**
- If a match is found, fires `local_face_secure.recognized` event
- If no match, no event is fired (check logs)
- Handles no face detected or multiple faces gracefully

#### `local_face_secure.delete_face`

Remove a face from the database.

**Parameters:**
- `name` (required): Name of the face to delete

**Example:**
```yaml
service: local_face_secure.delete_face
data:
  name: Stefan
```

#### `local_face_secure.list_faces`

List all known faces (supports response).

**Example:**
```yaml
service: local_face_secure.list_faces
response_variable: face_list
```

### Events

#### `local_face_secure.recognized`

Fired when a face is successfully matched.

**Event Data:**
```yaml
name: Stefan
confidence: 87.5
entity_id: camera.front_door
```

**Confidence:** Percentage from 0-100, where higher = better match

#### `local_face_secure.face_taught`

Fired when a new face is taught.

**Event Data:**
```yaml
name: Stefan
entity_id: camera.front_door
```

#### `local_face_secure.face_deleted`

Fired when a face is deleted.

**Event Data:**
```yaml
name: Stefan
```

## Automation Examples

### Notify when recognized

```yaml
automation:
  - alias: "Notify on Face Recognition"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: notify.mobile_app
        data:
          title: "Face Recognized"
          message: "{{ trigger.event.data.name }} detected ({{ trigger.event.data.confidence }}% confidence)"
```

### Unlock door for known faces

```yaml
automation:
  - alias: "Unlock Door for Stefan"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
      event_data:
        name: Stefan
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.confidence > 80 }}"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
```

### Scan on doorbell press

```yaml
automation:
  - alias: "Scan Face on Doorbell"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

### Periodic scanning

```yaml
automation:
  - alias: "Scan Front Door Every 5 Minutes"
    trigger:
      platform: time_pattern
      minutes: "/5"
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

## Architecture

### Event Loop Safety

All CPU-intensive operations (face detection, encoding, comparison) run in the executor thread pool using `hass.async_add_executor_job()`, ensuring the Home Assistant event loop never blocks.

### Persistent Storage

Face encodings are stored using Home Assistant's `Store` helper:
- Location: `.storage/local_face_secure.faces`
- Format: JSON
- Version: 1
- Automatic save on changes
- Loaded on startup

### Face Encodings

Each face is stored as a 128-dimensional encoding vector (list of floats). These encodings are:
- Unique to each person
- Robust to lighting and angle changes
- Small (only ~1KB per face)
- Fast to compare

### Matching Algorithm

Uses Euclidean distance for face comparison:
- Distance < 0.6 = Match (default tolerance)
- Lower distance = Higher confidence
- Confidence = (1 - distance) × 100%

## Troubleshooting

### No Face Detected

**Problem:** Service fails with "No face detected in image"

**Solutions:**
- Ensure good lighting
- Make sure face is clearly visible
- Check camera image quality
- Face should be relatively large in frame

### Multiple Faces Detected

**Problem:** Service fails with "Multiple faces detected"

**Solutions:**
- Ensure only one person is in camera view when teaching
- Remove background with faces (photos, screens)
- Adjust camera angle

### False Matches

**Problem:** Wrong person being recognized

**Solutions:**
- Teach more images of the correct person
- Delete and re-teach the face
- Increase tolerance (not currently configurable)
- Ensure good quality teaching images

### Installation Fails

**Problem:** `face_recognition` fails to install

**Solutions:**
- Install system dependencies (see Installation section)
- Check available memory (dlib compilation needs ~1GB RAM)
- Consider using a more powerful system
- Check Home Assistant logs for specific errors

### Component Not Loading

**Problem:** Integration doesn't appear after installation

**Solutions:**
- Check folder name is exactly `local_face_secure`
- Check all files are present
- Check Home Assistant logs for errors
- Restart Home Assistant twice

## Performance Notes

- **Face Teaching:** ~2-5 seconds per face
- **Face Recognition:** ~1-3 seconds per scan
- **Memory Usage:** ~50MB + (1KB per face)
- **CPU Usage:** High during recognition, idle otherwise

## Security Considerations

- Face encodings are NOT reversible to images
- All data stored locally in Home Assistant
- No network communication required
- Face encodings cannot be used to reconstruct faces
- Storage file has standard Home Assistant permissions

## Limitations

- Requires good lighting conditions
- Works best with frontal face views
- May struggle with significant aging or appearance changes
- Performance depends on system CPU
- Not suitable for authentication alone (should be combined with other methods)

## Development

### File Structure

```
local_face_secure/
├── __init__.py          # Component setup and service registration
├── const.py             # Constants and configuration
├── face_service.py      # Core face recognition logic
├── storage.py           # Persistent storage handler
├── services.yaml        # Service definitions for UI
├── manifest.json        # Component metadata
└── README.md            # This file
```

### Testing

Test the component:

1. Add to `configuration.yaml` and restart
2. Call `teach_face` service with test camera
3. Call `scan_match` service
4. Check logs for errors
5. Verify events are fired

## License

MIT License - See LICENSE file for details

## Credits

- Face recognition powered by [face_recognition](https://github.com/ageitgey/face_recognition) library
- Built on [dlib](http://dlib.net/) face recognition models
- Follows [Home Assistant](https://www.home-assistant.io/) architecture guidelines

## Support

For issues, feature requests, or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review Home Assistant logs
- Open an issue on GitHub

## Changelog

### 1.0.0 (2024-01-01)
- Initial release
- Core face recognition functionality
- Persistent storage
- Event system
- Full async architecture
