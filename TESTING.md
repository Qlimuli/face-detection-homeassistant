# Testing Guide for Local Face Secure

This guide provides comprehensive testing procedures for the Local Face Secure component.

## Quick Start Testing

### 1. Basic Installation Test

```bash
# Check component loaded successfully
tail -f /config/home-assistant.log | grep local_face_secure
```

Expected output:
```
INFO (MainThread) [custom_components.local_face_secure] Setting up Local Face Secure integration
INFO (MainThread) [custom_components.local_face_secure] Loaded 0 face encoding(s) from storage
INFO (MainThread) [custom_components.local_face_secure] Local Face Secure integration setup complete
```

### 2. Service Registration Test

In Home Assistant UI:
1. Go to **Developer Tools** → **Services**
2. Search for "local_face"
3. Verify these services appear:
   - `local_face_secure.teach_face`
   - `local_face_secure.scan_match`
   - `local_face_secure.delete_face`
   - `local_face_secure.list_faces`

### 3. Storage Test

```bash
# Check storage file created
ls -la /config/.storage/local_face_secure.faces
```

Expected: File exists with proper permissions

## Functional Testing

### Test 1: Teaching a Face

**Prerequisites:**
- Camera entity available (e.g., `camera.front_door`)
- Camera provides clear image
- One person visible in camera frame

**Steps:**

1. Position yourself in front of camera
2. Execute service call:
   ```yaml
   service: local_face_secure.teach_face
   data:
     entity_id: camera.front_door
     name: TestPerson
   ```

3. Check logs:
   ```
   INFO [...face_service] Teaching face for: TestPerson
   INFO [...face_service] Successfully encoded face with 128 features
   INFO [...storage] Saved face encoding for: TestPerson
   INFO [...face_service] Successfully taught face: TestPerson
   ```

4. Verify event fired:
   - Go to **Developer Tools** → **Events**
   - Listen to `local_face_secure.face_taught`
   - Event data should contain:
     ```json
     {
       "name": "TestPerson",
       "entity_id": "camera.front_door"
     }
     ```

5. Verify storage:
   ```bash
   cat /config/.storage/local_face_secure.faces
   ```
   Should contain JSON with "TestPerson" and 128-element encoding array

**Expected Result:** ✅ Face taught successfully, event fired, storage updated

### Test 2: Face Recognition (Match)

**Prerequisites:**
- Face already taught (Test 1 completed)
- Same person in camera frame

**Steps:**

1. Position same person in front of camera
2. Execute service call:
   ```yaml
   service: local_face_secure.scan_match
   data:
     entity_id: camera.front_door
   ```

3. Check logs:
   ```
   INFO [...face_service] Starting face recognition from camera: camera.front_door
   DEBUG [...face_service] Face distance for TestPerson: 0.XXXX
   INFO [...face_service] Face recognized: TestPerson (confidence: XX.X%)
   ```

4. Verify event fired:
   - Listen to `local_face_secure.recognized`
   - Event data should contain:
     ```json
     {
       "name": "TestPerson",
       "confidence": 87.5,
       "entity_id": "camera.front_door"
     }
     ```

**Expected Result:** ✅ Face matched, confidence > 80%, event fired

### Test 3: Face Recognition (No Match)

**Prerequisites:**
- Face database has entries
- Different person (not in database) in camera frame

**Steps:**

1. Position unknown person in camera
2. Execute scan_match service
3. Check logs:
   ```
   INFO [...face_service] No matching face found (best distance: 0.XXXX)
   ```

4. Verify NO event fired (recognized event should not appear)

**Expected Result:** ✅ No match found, no event fired

### Test 4: Error Handling - No Face

**Steps:**

1. Point camera at empty space (no faces)
2. Execute teach_face or scan_match
3. Check logs for error:
   ```
   WARNING [...face_service] No face detected in image
   ERROR [...] Failed to teach face: No face detected in image
   ```

**Expected Result:** ✅ Graceful error, no crash, clear error message

### Test 5: Error Handling - Multiple Faces

**Steps:**

1. Position 2+ people in camera frame
2. Execute teach_face
3. Check logs:
   ```
   WARNING [...face_service] Multiple faces detected: 2
   ERROR [...] Multiple faces detected. Please ensure only one person is in frame.
   ```

**Expected Result:** ✅ Graceful error, clear guidance

### Test 6: Deleting a Face

**Prerequisites:**
- Face exists in database

**Steps:**

1. Execute delete service:
   ```yaml
   service: local_face_secure.delete_face
   data:
     name: TestPerson
   ```

2. Check logs:
   ```
   INFO [...storage] Deleted face encoding for: TestPerson
   ```

3. Verify event:
   ```json
   {
     "name": "TestPerson"
   }
   ```

4. Verify storage updated:
   ```bash
   cat /config/.storage/local_face_secure.faces
   ```
   Should not contain "TestPerson"

**Expected Result:** ✅ Face deleted, storage updated, event fired

### Test 7: Listing Faces

**Steps:**

1. Teach 2-3 faces
2. Execute list service:
   ```yaml
   service: local_face_secure.list_faces
   response_variable: result
   ```

3. Check response contains all face names

**Expected Result:** ✅ All faces listed correctly

## Performance Testing

### Test 8: Recognition Speed

**Objective:** Measure face recognition latency

**Script:**
```yaml
script:
  test_recognition_speed:
    sequence:
      - service: homeassistant.update_entity
        target:
          entity_id: sensor.time
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

**Measurement:**
- Check logs for timestamps
- Typical: 1-3 seconds on Pi 4
- Typical: 0.5-1.5 seconds on x86

### Test 9: Concurrent Operations

**Objective:** Verify thread safety

**Steps:**

1. Execute multiple scan_match calls simultaneously:
   ```yaml
   # In Developer Tools, quickly execute 3 times
   service: local_face_secure.scan_match
   data:
     entity_id: camera.front_door
   ```

2. Monitor logs - should not crash
3. All operations should complete

**Expected Result:** ✅ No crashes, all operations complete

### Test 10: Storage Persistence

**Objective:** Verify data survives restart

**Steps:**

1. Teach a face
2. Restart Home Assistant:
   ```bash
   ha core restart
   ```
3. Check logs on startup:
   ```
   INFO [...storage] Loaded 1 face encoding(s) from storage
   ```
4. Execute scan_match - should still recognize

**Expected Result:** ✅ Face encodings persist across restarts

## Edge Case Testing

### Test 11: Invalid Camera Entity

**Steps:**
```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.nonexistent
  name: Test
```

**Expected:** ❌ Error "Invalid camera entity", no crash

### Test 12: Unavailable Camera

**Steps:**

1. Make camera unavailable (unplug or disable)
2. Execute scan_match

**Expected:** ❌ Error "Failed to capture camera snapshot", no crash

### Test 13: Duplicate Face Name

**Steps:**

1. Teach face "Stefan"
2. Teach same name again:
   ```yaml
   service: local_face_secure.teach_face
   data:
     entity_id: camera.front_door
     name: Stefan
   ```

**Expected:** ❌ Error "Face 'Stefan' already exists", no crash

### Test 14: Delete Non-existent Face

**Steps:**
```yaml
service: local_face_secure.delete_face
data:
  name: NonExistent
```

**Expected:** ❌ Error "Face 'NonExistent' not found", no crash

### Test 15: Corrupted Storage

**Steps:**

1. Stop Home Assistant
2. Edit storage file:
   ```bash
   echo "invalid json" > /config/.storage/local_face_secure.faces
   ```
3. Start Home Assistant
4. Check logs:
   ```
   ERROR [...storage] Error loading face data: ...
   INFO [...storage] No existing face data found, starting fresh
   ```

**Expected:** ✅ Recovers gracefully, starts with empty database

## Integration Testing

### Test 16: Automation Trigger

**Setup:**
```yaml
automation:
  - alias: Test Recognition Trigger
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: persistent_notification.create
        data:
          message: "Recognized: {{ trigger.event.data.name }}"
```

**Steps:**
1. Add automation
2. Execute scan_match with known face
3. Check for notification

**Expected Result:** ✅ Automation triggers, notification appears

### Test 17: Multiple Cameras

**Prerequisites:**
- 2+ camera entities available

**Steps:**

1. Teach from camera 1
2. Scan from camera 2
3. Should still recognize (encoding is camera-independent)

**Expected Result:** ✅ Recognition works across cameras

## Stress Testing

### Test 18: Many Faces

**Objective:** Test with large database

**Steps:**

1. Teach 50+ different faces
2. Execute scan_match
3. Monitor memory usage
4. Check recognition accuracy

**Expected:**
- Memory increases linearly (~1KB per face)
- Recognition time stays consistent
- Accuracy remains high

### Test 19: Rapid Scanning

**Objective:** Test sustained load

**Setup:**
```yaml
automation:
  - alias: Rapid Scan Test
    trigger:
      platform: time_pattern
      seconds: "/5"
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

**Steps:**

1. Run for 1 hour
2. Monitor:
   - CPU usage
   - Memory usage
   - Log for errors
   - System responsiveness

**Expected:**
- CPU peaks during scans, idles between
- No memory leaks
- No errors
- HA remains responsive

## Real-World Scenarios

### Test 20: Doorbell Integration

**Setup:**
```yaml
automation:
  - alias: Doorbell Face Recognition
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
      - delay:
          seconds: 3
      - service: notify.mobile_app
        data:
          message: "Someone at the door"
```

**Test:**
1. Press doorbell
2. Verify scan executes
3. Check notification

### Test 21: Door Unlock

**Setup:**
```yaml
automation:
  - alias: Auto Unlock for Known Face
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.confidence > 90 }}"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
```

**Test:**
1. Stand in front of camera
2. Execute scan_match
3. Verify door unlocks (only if confidence > 90%)

## Debugging Tips

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.local_face_secure: debug
```

### Check Storage

```bash
# Pretty print storage
python3 -m json.tool /config/.storage/local_face_secure.faces
```

### Monitor in Real-Time

```bash
# Watch logs
tail -f /config/home-assistant.log | grep local_face_secure
```

### Test Camera Snapshot

```yaml
# Verify camera works
service: camera.snapshot
data:
  entity_id: camera.front_door
  filename: /config/test_snapshot.jpg
```

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "No face detected" | Poor lighting | Improve lighting |
| Low confidence | Different angle | Teach from multiple angles |
| Slow recognition | Weak CPU | Reduce scan frequency |
| Installation fails | Missing dependencies | Install system packages |
| Services not appearing | Wrong folder structure | Check `/config/custom_components/local_face_secure/` |

## Test Checklist

- [ ] Component loads without errors
- [ ] All 4 services registered
- [ ] Storage file created
- [ ] Can teach a face successfully
- [ ] Face recognition works (match)
- [ ] Face recognition works (no match)
- [ ] Error handling (no face)
- [ ] Error handling (multiple faces)
- [ ] Can delete face
- [ ] Can list faces
- [ ] Events fire correctly
- [ ] Data persists across restart
- [ ] Automations trigger correctly
- [ ] No memory leaks
- [ ] No event loop blocking
- [ ] Thread-safe operation

## Reporting Issues

When reporting issues, include:

1. Home Assistant version
2. System info (Pi 4, x86, etc.)
3. Relevant logs (enable debug logging)
4. Storage file contents (remove encodings for privacy)
5. Camera entity details
6. Steps to reproduce

## Performance Benchmarks

Expected performance on different systems:

| System | Teach Time | Scan Time | Memory |
|--------|-----------|-----------|---------|
| RPi 4 (4GB) | 3-5s | 2-4s | 50-100MB |
| RPi 5 (8GB) | 2-3s | 1-2s | 50-100MB |
| x86 (i5) | 1-2s | 0.5-1s | 50-100MB |
| x86 (i7) | 0.5-1s | 0.3-0.5s | 50-100MB |

*Times include camera snapshot + face detection + encoding*
