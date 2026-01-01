# Quick Start Guide

Get Local Face Secure running in 5 minutes!

## Prerequisites

- ✅ Home Assistant 2023.1+
- ✅ Camera entity configured
- ✅ SSH or File Editor access to HA

## Installation

### Step 1: Copy Files

Copy the `local_face_secure` folder to:
```
/config/custom_components/local_face_secure/
```

### Step 2: Add to Configuration

Edit `/config/configuration.yaml` and add:
```yaml
local_face_secure:
```

### Step 3: Restart Home Assistant

**Important:** Restart **TWICE**
- First restart: Loads component
- Second restart: Installs dependencies (takes 5-10 min)

### Step 4: Verify

Go to **Developer Tools** → **Services**

Search for: `local_face_secure`

You should see:
- ✅ local_face_secure.teach_face
- ✅ local_face_secure.scan_match
- ✅ local_face_secure.delete_face
- ✅ local_face_secure.list_faces

## First Use

### 1. Teach Your First Face

In **Developer Tools** → **Services**:

```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.front_door  # Your camera
  name: YourName
```

**Tips:**
- Face camera directly
- Good lighting
- Only one person in frame
- Face clearly visible

### 2. Test Recognition

```yaml
service: local_face_secure.scan_match
data:
  entity_id: camera.front_door
```

Check **Developer Tools** → **Events**

Listen for: `local_face_secure.recognized`

You should see:
```json
{
  "name": "YourName",
  "confidence": 87.5,
  "entity_id": "camera.front_door"
}
```

### 3. Create Your First Automation

```yaml
automation:
  - alias: "Welcome Home"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: notify.mobile_app
        data:
          title: "Welcome Home!"
          message: "{{ trigger.event.data.name }} detected"
```

## Common First-Time Issues

### "No services found"
→ Restart Home Assistant again (dependencies installing)

### "No face detected"
→ Improve lighting, get closer to camera

### "Multiple faces detected"  
→ Ensure only one person in frame

### Installation hangs
→ Normal! Dependencies take 5-10 minutes to install
→ On Raspberry Pi, may take up to 20 minutes

## Next Steps

1. ✅ Teach multiple faces
2. ✅ Add confidence thresholds to automations
3. ✅ Integrate with doorbell/motion sensors
4. ✅ Set up notifications with camera snapshots

## Getting Help

- 📖 Full docs: [README.md](README.md)
- 🔧 Problems: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- ❓ Questions: [FAQ.md](FAQ.md)
- 🧪 Testing: [TESTING.md](TESTING.md)

## Example Automations

### Doorbell → Face Recognition
```yaml
automation:
  - alias: "Scan on Doorbell"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

### Notify with Confidence
```yaml
automation:
  - alias: "Notify with Confidence"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.confidence > 85 }}"
    action:
      - service: notify.mobile_app
        data:
          message: >
            {{ trigger.event.data.name }} at door
            ({{ trigger.event.data.confidence }}% sure)
```

### Turn On Lights for Known Faces
```yaml
automation:
  - alias: "Lights for Known People"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    condition:
      - condition: sun
        after: sunset
    action:
      - service: light.turn_on
        target:
          entity_id: light.porch
```

## Performance Tips

✅ **Good:** Trigger on doorbell/motion
```yaml
trigger:
  platform: state
  entity_id: binary_sensor.motion
  to: "on"
```

❌ **Bad:** Scan every 5 seconds
```yaml
trigger:
  platform: time_pattern
  seconds: "/5"
```

## Debug Mode

If something's not working:

```yaml
logger:
  logs:
    custom_components.local_face_secure: debug
```

Then check logs:
```bash
tail -f /config/home-assistant.log | grep local_face_secure
```

## Support

Need help? Check in order:
1. This Quick Start
2. [FAQ.md](FAQ.md)
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
4. GitHub Issues

Happy face recognizing! 🎉
