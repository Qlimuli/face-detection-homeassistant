# Troubleshooting Guide

This guide addresses common issues and their solutions for the Local Face Secure component.

## Table of Contents
1. [Installation Issues](#installation-issues)
2. [Face Detection Issues](#face-detection-issues)
3. [Recognition Issues](#recognition-issues)
4. [Performance Issues](#performance-issues)
5. [Error Messages](#error-messages)
6. [Debug Mode](#debug-mode)

---

## Installation Issues

### Problem: Component Not Loading

**Symptoms:**
- Services don't appear in Developer Tools
- No logs from local_face_secure
- Integration doesn't show up

**Diagnosis:**
```bash
# Check if files are in correct location
ls -la /config/custom_components/local_face_secure/

# Check Home Assistant logs
tail -100 /config/home-assistant.log | grep -i "local_face_secure\|error\|exception"
```

**Solutions:**

1. **Verify folder structure:**
   ```
   /config/custom_components/local_face_secure/
   ├── __init__.py
   ├── manifest.json
   ├── const.py
   ├── face_service.py
   ├── storage.py
   └── services.yaml
   ```

2. **Check configuration.yaml:**
   ```yaml
   local_face_secure:
   ```
   Must be at root level (not indented under another component)

3. **Restart Home Assistant TWICE:**
   - First restart: HA loads custom components
   - Second restart: Dependencies install and component initializes

4. **Check file permissions:**
   ```bash
   chmod -R 755 /config/custom_components/local_face_secure/
   ```

### Problem: face_recognition Library Won't Install

**Symptoms:**
- Installation hangs for >30 minutes
- Errors about cmake, dlib, or compilation
- Out of memory errors

**On Raspberry Pi:**
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev

# Check available RAM
free -h

# If low on RAM, increase swap:
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**On x86:**
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake
```

**Last Resort:**
Pre-compile dlib in a separate environment and copy wheel file.

---

## Face Detection Issues

### Problem: "No face detected in image"

**Common Causes:**

1. **Poor Lighting**
   - **Symptoms:** Shadows, dark image
   - **Solution:** Add lighting, use camera with better low-light performance
   - **Test:** Take manual snapshot and verify face is clearly visible

2. **Face Too Small**
   - **Symptoms:** Person too far from camera
   - **Solution:** Position person closer, adjust camera angle
   - **Rule of thumb:** Face should occupy at least 10% of image

3. **Face Angle**
   - **Symptoms:** Person looking away, extreme angle
   - **Solution:** Face camera directly, ±45° max angle

4. **Image Quality**
   - **Symptoms:** Blurry, low resolution
   - **Solution:** Use higher quality camera, ensure camera is in focus
   - **Minimum recommended:** 720p resolution

5. **Obstructions**
   - **Symptoms:** Sunglasses, mask, hat covering face
   - **Solution:** Remove obstructions for teaching/recognition

**Debugging Steps:**

```yaml
# Test 1: Verify camera works
service: camera.snapshot
data:
  entity_id: camera.front_door
  filename: /config/www/test_snapshot.jpg

# Then view at: http://YOUR_HA_IP:8123/local/test_snapshot.jpg
# Can you clearly see the face?
```

```yaml
# Test 2: Check camera state
# In Developer Tools → States, look for camera.front_door
# State should be "idle" or "recording", not "unavailable"
```

### Problem: "Multiple faces detected"

**Common Causes:**

1. **Background Photos/Screens**
   - TV showing faces
   - Photo frames
   - Computer screens
   - **Solution:** Turn off screens, remove from camera view

2. **Multiple People**
   - **Solution:** Ensure only one person in frame when teaching

3. **Reflections**
   - Mirrors reflecting faces
   - **Solution:** Adjust camera angle

**Workaround for Teaching:**
Position person very close to camera so their face dominates the frame.

---

## Recognition Issues

### Problem: Known Face Not Recognized

**Diagnosis:**

Check confidence scores in logs:
```bash
tail -f /config/home-assistant.log | grep "Face distance"
```

**Scenario 1: Distance ~0.3-0.6 (Should match but doesn't)**

**Causes:**
- Tolerance too strict (default: 0.6)
- Different lighting conditions
- Different angle than taught
- Aging/appearance change

**Solutions:**

1. **Teach from multiple angles:**
   ```yaml
   # Teach same person 3 times with different angles
   service: local_face_secure.teach_face
   data:
     entity_id: camera.front_door
     name: Stefan_front
   
   # Repeat with person at different angles
   # Then use Stefan_front, Stefan_left, Stefan_right
   ```

2. **Re-teach under current conditions:**
   - Same lighting as recognition
   - Same camera position

3. **Increase tolerance** (requires code modification):
   ```python
   # In face_service.py, change:
   DEFAULT_TOLERANCE = 0.6  # to 0.7 for more lenient matching
   ```

**Scenario 2: Distance >0.7 (Correctly not matching)**

This is working as designed. The person may be too different from taught encoding.

**Solution:**
Delete and re-teach the face under current conditions.

### Problem: Wrong Person Recognized (False Positive)

**Symptoms:**
- Unknown person recognized as known person
- Low confidence matches (<75%)

**Immediate Fix:**
Add confidence threshold to automations:
```yaml
automation:
  trigger:
    platform: event
    event_type: local_face_secure.recognized
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.confidence > 85 }}"
  action:
    # Your action here
```

**Long-term Solutions:**

1. **Teach more images of correct person:**
   - Teaches from different angles
   - Improves distinctiveness

2. **Delete and re-teach:**
   - Poor initial teaching can cause issues
   - Ensure good lighting and clear face

3. **Reduce tolerance** (code modification):
   ```python
   DEFAULT_TOLERANCE = 0.5  # More strict (default 0.6)
   ```

### Problem: Inconsistent Recognition

**Symptoms:**
- Sometimes recognizes, sometimes doesn't
- Same person, same camera, same position

**Causes:**

1. **Variable Lighting**
   - **Diagnosis:** Check if failures correlate with time of day
   - **Solution:** Add consistent lighting, teach under variable conditions

2. **Camera Auto-Adjust**
   - Auto-brightness, auto-focus changing image
   - **Solution:** Lock camera settings if possible

3. **Motion Blur**
   - Person moving when snapshot taken
   - **Solution:** Ask person to hold still, use faster shutter

4. **Borderline Distance**
   - Distance hovering around tolerance threshold (0.58-0.62)
   - **Solution:** Re-teach to improve confidence

**Debugging:**

Enable debug logging and check distance values:
```yaml
logger:
  logs:
    custom_components.local_face_secure.face_service: debug
```

Look for patterns in face distances.

---

## Performance Issues

### Problem: Slow Recognition (>10 seconds)

**Expected Times:**
- Raspberry Pi 4: 2-4 seconds
- Raspberry Pi 5: 1-2 seconds  
- x86 (i5): 0.5-1 second

**If significantly slower:**

1. **Check CPU Usage:**
   ```bash
   top
   # Look for high CPU usage from home-assistant
   ```

2. **Check System Load:**
   ```bash
   uptime
   # Load average should be < number of CPUs
   ```

3. **Reduce Scan Frequency:**
   ```yaml
   # Change from:
   trigger:
     platform: time_pattern
     seconds: "/5"
   
   # To:
   trigger:
     platform: time_pattern
     minutes: "/1"
   ```

4. **Check Image Size:**
   Large camera images slow processing
   ```yaml
   # If using high-res camera, reduce resolution in camera config
   ```

5. **Database Size:**
   - Check number of faces: `service: local_face_secure.list_faces`
   - >100 faces may slow comparison
   - Solution: Remove unused faces

### Problem: High Memory Usage

**Normal:** 50-100MB for component

**If seeing 500MB+ or growing:**

1. **Check for memory leak:**
   ```bash
   # Monitor over time
   watch -n 5 'ps aux | grep home-assistant | grep -v grep'
   ```

2. **Restart Home Assistant:**
   - Temporary fix while investigating

3. **Check logs for repeated errors:**
   - Repeated errors can cause memory buildup

4. **Report as bug** if confirmed memory leak

### Problem: Home Assistant Becomes Unresponsive

**Symptoms:**
- UI sluggish during face recognition
- Other automations delayed
- Dashboard slow to load

**Cause:** 
Event loop blocking (should NOT happen with this component)

**Diagnosis:**
```bash
# Check if face_recognition running in executor
tail -f /config/home-assistant.log | grep "executor"
```

**If blocking detected:**
This is a bug. The component should use `async_add_executor_job`.

**Temporary workaround:**
Reduce scan frequency drastically (every 5+ minutes).

**Report:** Open GitHub issue with logs.

---

## Error Messages

### "Invalid camera entity"

**Cause:** Camera entity doesn't exist or isn't a camera

**Fix:**
1. Verify camera entity ID:
   ```yaml
   # In Developer Tools → States
   # Search for your camera
   # Copy exact entity_id (e.g., camera.front_door)
   ```

2. Ensure camera is working:
   ```yaml
   service: camera.snapshot
   data:
     entity_id: camera.front_door
     filename: /config/test.jpg
   ```

### "Failed to capture camera snapshot"

**Causes:**

1. **Camera offline/unavailable**
   - Check camera state in Developer Tools → States
   - Should be "idle" or "recording", not "unavailable"

2. **Network issue**
   - Camera unreachable
   - Check network connectivity

3. **Camera doesn't support snapshots**
   - Some camera integrations don't support snapshots
   - Check camera integration documentation

4. **Authentication issue**
   - Camera credentials changed
   - Reconfigure camera integration

**Fix:**
```yaml
# Test camera directly
service: camera.snapshot
data:
  entity_id: camera.front_door
  filename: /config/www/test.jpg
```

If this fails, issue is with camera, not face recognition.

### "Face 'Stefan' already exists"

**Cause:** Trying to teach face with name that exists

**Fix:**

**Option 1: Delete existing**
```yaml
service: local_face_secure.delete_face
data:
  name: Stefan
```

**Option 2: Use different name**
```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.front_door
  name: Stefan_v2
```

### "Face 'Stefan' not found"

**Cause:** Trying to delete non-existent face

**Fix:**

List all faces:
```yaml
service: local_face_secure.list_faces
response_variable: faces
```

Check exact spelling (case-sensitive).

---

## Debug Mode

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.local_face_secure: debug
    custom_components.local_face_secure.face_service: debug
    custom_components.local_face_secure.storage: debug
```

Restart Home Assistant.

### View Logs

**Real-time:**
```bash
tail -f /config/home-assistant.log | grep local_face_secure
```

**Full log:**
```bash
cat /config/home-assistant.log | grep local_face_secure
```

**Last 100 lines:**
```bash
tail -100 /config/home-assistant.log | grep local_face_secure
```

### What to Look For

**Successful teaching:**
```
INFO [face_service] Teaching face for: Stefan
DEBUG [face_service] Successfully encoded face with 128 features
INFO [storage] Saved face encoding for: Stefan
```

**Successful recognition:**
```
DEBUG [face_service] Starting face recognition from camera: camera.front_door
DEBUG [face_service] Face distance for Stefan: 0.3421
INFO [face_service] Face recognized: Stefan (confidence: 65.8%)
```

**No match:**
```
DEBUG [face_service] Face distance for Stefan: 0.7845
DEBUG [face_service] Face distance for Maria: 0.6234
INFO [face_service] No matching face found (best distance: 0.6234)
```

### Verify Storage

**Check storage file:**
```bash
cat /config/.storage/local_face_secure.faces | python3 -m json.tool
```

**Expected format:**
```json
{
  "faces": {
    "Stefan": {
      "encoding": [0.123, -0.456, ...],  // 128 numbers
      "name": "Stefan"
    }
  }
}
```

### Manual Storage Reset

**If storage corrupted:**
```bash
# Backup first!
cp /config/.storage/local_face_secure.faces /config/.storage/local_face_secure.faces.backup

# Reset
echo '{"faces":{}}' > /config/.storage/local_face_secure.faces

# Restart Home Assistant
```

---

## Getting Help

If issues persist:

1. **Enable debug logging** (see above)
2. **Collect information:**
   - Home Assistant version
   - System (RPi 4, x86, etc.)
   - Camera integration used
   - Relevant logs
3. **Check existing issues** on GitHub
4. **Open new issue** with:
   - Detailed description
   - Steps to reproduce
   - Logs (remove personal info)
   - Configuration (remove sensitive data)

## Useful Commands

```bash
# Check component loaded
tail -100 /config/home-assistant.log | grep "Local Face Secure"

# Check face_recognition installed
ha core logs | grep face_recognition

# Check storage
ls -lah /config/.storage/local_face_secure.faces

# Test camera snapshot
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/camera_proxy/camera.front_door > test.jpg

# Check services registered
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/services | grep local_face_secure
```

---

## Performance Tuning

### For Raspberry Pi

```yaml
# Scan less frequently
automation:
  trigger:
    platform: time_pattern
    minutes: "/2"  # Every 2 minutes instead of constantly

# Use motion triggers instead of time-based
automation:
  trigger:
    platform: state
    entity_id: binary_sensor.motion
    to: "on"
```

### For Production Use

```yaml
# Add confidence thresholds
automation:
  trigger:
    platform: event
    event_type: local_face_secure.recognized
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.confidence > 90 }}"

# Add time restrictions
  condition:
    - condition: time
      after: "07:00:00"
      before: "22:00:00"

# Add cooldown to prevent spam
  mode: single
  max_exceeded: silent
```
