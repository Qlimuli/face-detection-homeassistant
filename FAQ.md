# Frequently Asked Questions (FAQ)

## General Questions

### What is Local Face Secure?

Local Face Secure is a Home Assistant custom component that performs face recognition entirely locally on your Home Assistant server. It uses the `face_recognition` library (powered by dlib) to detect, encode, and match faces from camera images.

### Is it really 100% local?

Yes! All processing happens on your Home Assistant server:
- No cloud services
- No external API calls
- No data sent anywhere
- Face encodings stored locally

### What cameras are supported?

Any camera integrated with Home Assistant that supports snapshots. Common examples:
- Generic IP cameras (RTSP, MJPEG)
- USB webcams
- Ring doorbells
- Unifi cameras
- Frigate camera
- MotionEye
- And many others

### How accurate is it?

The underlying dlib face recognition model is very accurate (99.38% on the LFW benchmark). However, real-world accuracy depends on:
- Camera quality
- Lighting conditions
- Face angle
- Image resolution

In good conditions: 95%+ accuracy for known faces.

---

## Privacy & Security

### Can face encodings be reversed to images?

No. Face encodings are mathematical representations (128 numbers) that cannot be converted back to images. Think of them like secure hashes - they can verify identity but can't recreate the original.

### Where are face encodings stored?

In `/config/.storage/local_face_secure.faces` as JSON. This file:
- Is only accessible on your HA server
- Has standard HA permissions
- Can be backed up with your HA config
- Contains no images, only mathematical encodings

### Is this secure enough for authentication?

**No!** Face recognition should be a convenience layer, not primary security:
- Use it to trigger notifications
- Use it with additional verification for actions
- Don't rely on it alone for critical security (locks, alarms)
- Always have backup access methods

### What about deepfakes or photos?

This component does basic 2D face recognition and cannot detect:
- Photos of photos
- Deepfakes
- 3D masks
- Video playback

For security applications, add:
- Liveness detection (separate component/camera feature)
- Multi-factor authentication
- Time-of-day restrictions
- Confidence thresholds

### Should I inform people they're being monitored?

**Yes!** In many jurisdictions, it's legally required to:
- Post signs about video surveillance
- Inform visitors about facial recognition
- Comply with local privacy laws (GDPR, etc.)

Consult local laws regarding surveillance and biometric data.

---

## Technical Questions

### How does face recognition work?

1. **Detection**: Finds faces in image
2. **Alignment**: Normalizes face orientation
3. **Encoding**: Extracts 128 numerical features
4. **Comparison**: Measures distance between encodings
5. **Matching**: If distance < threshold, it's a match

### What's a face encoding?

A 128-dimensional vector (list of 128 numbers) representing unique facial features. Example:
```python
[0.123, -0.456, 0.789, ...]  # 128 numbers total
```

These numbers mathematically describe:
- Face shape
- Eye spacing
- Nose profile
- Facial proportions
- And 120+ other features

### What's the confidence score?

Confidence = (1 - distance) × 100%

- Distance 0.0 = 100% confidence (perfect match)
- Distance 0.4 = 60% confidence (good match)
- Distance 0.6 = 40% confidence (threshold)
- Distance >0.6 = No match

**Guidelines:**
- >90% = Excellent match
- 85-90% = Good match
- 75-85% = Acceptable match
- <75% = Questionable, review

### Why is there a tolerance of 0.6?

The default tolerance of 0.6 balances:
- **Lower (0.4)**: More strict, fewer false positives, more false negatives
- **Higher (0.8)**: More lenient, fewer false negatives, more false positives

0.6 is the recommended default from the face_recognition library based on testing.

### Can I change the tolerance?

Currently requires code modification. Edit `face_service.py`:
```python
DEFAULT_TOLERANCE = 0.6  # Change to 0.5 (strict) or 0.7 (lenient)
```

We may add this as a configurable option in future versions.

### How much CPU does it use?

**During recognition:** 
- 50-100% of one CPU core
- Duration: 1-5 seconds depending on system

**Idle:** 
- Negligible (<1%)

**Impact on HA:**
Operations run in executor thread pool, so HA event loop isn't blocked.

### How much memory?

- Base component: ~50MB
- Per face: ~1KB
- Temporary during processing: +20-50MB

Total for 50 faces: ~100MB

### How many faces can it handle?

**Tested up to:** 100 faces

**Theoretical limit:** 1000+, but:
- Comparison time increases linearly
- Each face adds ~1ms to comparison
- 1000 faces = +1 second recognition time

**Recommendation:** <100 faces for best performance

### Does it work with masks?

**Partial masks (chin masks):** Sometimes
**Full face masks:** No
**Surgical masks:** Rarely

Face recognition needs clear view of nose, eyes, and facial structure. Masks covering these reduce accuracy dramatically.

### Does it work in the dark?

Depends on camera:
- **IR night vision cameras:** Yes, if IR illuminates face
- **Normal cameras in darkness:** No
- **Low-light cameras:** Maybe, depends on lighting

Face recognition needs visible facial features. Complete darkness won't work regardless of camera.

---

## Usage Questions

### How do I teach multiple faces for one person?

**Option 1: Teach separately**
```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.front_door
  name: Stefan_front

service: local_face_secure.teach_face
data:
  entity_id: camera.front_door
  name: Stefan_side
```

Then handle in automations:
```yaml
condition:
  - condition: template
    value_template: >
      {{ trigger.event.data.name in ['Stefan_front', 'Stefan_side'] }}
```

**Option 2: Average encodings** (requires custom code)
Future feature possibility.

### Should I teach from multiple angles?

**Yes!** For best results:
1. Frontal face (directly at camera)
2. Slight left angle (~30°)
3. Slight right angle (~30°)

Save as `Name_front`, `Name_left`, `Name_right` and treat as same person in automations.

### How often should I re-teach faces?

**Reasons to re-teach:**
- Significant appearance change (haircut, beard, weight)
- Poor recognition accuracy
- Different lighting conditions
- Camera position changed

**Typical schedule:**
- Every 3-6 months for active users
- After major appearance changes
- When recognition accuracy drops

### Can I use multiple cameras?

**Yes!** Face encodings are camera-independent. A face taught from one camera will be recognized by any camera.

However, for best results:
- Similar lighting conditions across cameras
- Similar angles/perspectives
- Similar resolutions

### How do I back up face data?

Face data is in Home Assistant's storage:

**Method 1: HA Snapshot/Backup**
Includes `.storage` directory automatically.

**Method 2: Manual backup**
```bash
cp /config/.storage/local_face_secure.faces /backup/location/
```

**Method 3: Git (if using HA config git)**
Add to version control:
```bash
git add .storage/local_face_secure.faces
git commit -m "Update face data"
```

### Can I export/import faces to another HA instance?

**Yes!**

**Export:**
```bash
cp /config/.storage/local_face_secure.faces /share/face_backup.json
```

**Import on new instance:**
```bash
# After installing component
cp /share/face_backup.json /config/.storage/local_face_secure.faces
# Restart Home Assistant
```

### Can I use this for attendance tracking?

**Yes!** Example automation:
```yaml
automation:
  - alias: "Log Person Arrival"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: logbook.log
        data:
          name: "Arrival"
          message: "{{ trigger.event.data.name }} arrived"
      - service: google_sheets.append_sheet  # If using sheets integration
        data:
          worksheet: "Attendance"
          values:
            - ["{{ trigger.event.data.name }}", "{{ now() }}"]
```

---

## Comparison Questions

### How does this compare to Frigate?

**Frigate:**
- Object detection (person, car, etc.)
- Motion detection
- Recording
- Not face recognition

**Local Face Secure:**
- Face recognition (identify specific people)
- No recording
- No object detection

**Use together:**
- Frigate detects person → Triggers face recognition
- Best of both worlds

### How does this compare to Compreface?

**Compreface:**
- Separate Docker container
- REST API
- More features (age/gender detection)
- Higher resource usage

**Local Face Secure:**
- Native HA integration
- No separate containers
- Simpler, lighter
- Face recognition only

**Choose Compreface if:** You want advanced features, have resources
**Choose Local Face Secure if:** You want simplicity, HA-native, lighter

### How does this compare to Deepstack?

**Deepstack:**
- Multiple AI models (objects, faces, scene)
- Separate service
- More complex setup
- Commercial license for face recognition

**Local Face Secure:**
- Face recognition only
- No separate service
- Simpler setup
- Open source (MIT license)

### Can I use this with Doods/Deepstack/Frigate together?

**Yes!** They complement each other:

**Example workflow:**
1. Frigate detects person in zone
2. Triggers Local Face Secure to scan
3. Face recognized → Take action

```yaml
automation:
  - alias: "Scan Face on Person Detection"
    trigger:
      platform: event
      event_type: frigate.person_detected
      event_data:
        camera: front_door
    action:
      - service: local_face_secure.scan_match
        data:
          entity_id: camera.front_door
```

---

## Performance Questions

### Will this slow down my Home Assistant?

**Properly configured: No**

The component uses Home Assistant's executor thread pool for CPU-intensive work, preventing event loop blocking.

**However:**
- Very frequent scanning (every 5 seconds) may cause load
- Weak systems (RPi 3 or older) may struggle
- Running many other heavy integrations simultaneously may cumulate

**Best practices:**
- Scan on motion/doorbell triggers, not constantly
- Reasonable intervals (1+ minute if time-based)
- Monitor system resources

### What's the minimum recommended system?

**Minimum:**
- Raspberry Pi 4 (4GB)
- Or equivalent x86 system

**Works but slow:**
- Raspberry Pi 3B+ (expect 5-10 second scans)

**Not recommended:**
- Raspberry Pi 3 or older
- Raspberry Pi Zero

**Optimal:**
- Raspberry Pi 5
- Any modern x86 system (i5 or better)
- NUC, mini PC with HA

### How can I improve performance?

1. **Trigger-based vs. polling:**
   ```yaml
   # Good: Event-driven
   trigger:
     platform: state
     entity_id: binary_sensor.doorbell
     to: "on"
   
   # Bad: Constant polling
   trigger:
     platform: time_pattern
     seconds: "/5"
   ```

2. **Reduce scan frequency**
3. **Fewer faces in database** (remove unused)
4. **Lower camera resolution** (720p sufficient)
5. **Upgrade hardware** if all else fails

### Does it work on Home Assistant OS (HassOS)?

**Yes!** Fully supported on:
- Home Assistant OS (HassOS)
- Home Assistant Container
- Home Assistant Core
- Home Assistant Supervised

The component is Python-based and works anywhere Home Assistant runs.

---

## Automation Questions

### How do I unlock door only for specific people?

```yaml
automation:
  - alias: "Unlock for Family"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    condition:
      # Only trusted people
      - condition: template
        value_template: >
          {{ trigger.event.data.name in ['Stefan', 'Maria', 'Kids'] }}
      # High confidence required
      - condition: template
        value_template: "{{ trigger.event.data.confidence > 90 }}"
      # Daytime only
      - condition: sun
        after: sunrise
        before: sunset
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
      - service: notify.mobile_app
        data:
          message: "Door unlocked for {{ trigger.event.data.name }}"
```

### How do I get notified with photo?

```yaml
automation:
  - alias: "Notify with Snapshot"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: notify.mobile_app
        data:
          title: "{{ trigger.event.data.name }} at door"
          message: "Confidence: {{ trigger.event.data.confidence }}%"
          data:
            image: "/api/camera_proxy/{{ trigger.event.data.entity_id }}"
```

### How do I log all recognitions to a Google Sheet?

Requires Google Sheets integration, then:
```yaml
automation:
  - alias: "Log to Sheet"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    action:
      - service: google_sheets.append_sheet
        data:
          worksheet: "Face Log"
          values:
            - - "{{ trigger.event.data.name }}"
              - "{{ trigger.event.data.confidence }}"
              - "{{ now().strftime('%Y-%m-%d %H:%M:%S') }}"
              - "{{ trigger.event.data.entity_id }}"
```

### How do I prevent false alarms?

```yaml
automation:
  - alias: "Careful Unlock"
    trigger:
      platform: event
      event_type: local_face_secure.recognized
    condition:
      # Require very high confidence
      - condition: template
        value_template: "{{ trigger.event.data.confidence > 95 }}"
      # Only during expected times
      - condition: time
        after: "06:00:00"
        before: "23:00:00"
      # Rate limit (once per 5 minutes)
    mode: single
    max_exceeded: silent
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
      # Wait 5 minutes before allowing again
      - delay:
          minutes: 5
```

---

## Troubleshooting Quick Answers

### Why aren't services showing up?

Restart Home Assistant **twice** after installation.

### Why is recognition so slow?

Normal on Raspberry Pi (2-4 seconds). If >10 seconds, check CPU usage and reduce scan frequency.

### Why is confidence so low?

Re-teach face under current lighting/angle conditions.

### Why does it recognize wrong person?

- Lower tolerance for stricter matching
- Re-teach with better quality images
- Add confidence threshold in automations

### How do I reset everything?

```bash
# Stop HA
ha core stop

# Remove storage
rm /config/.storage/local_face_secure.faces

# Start HA
ha core start
```

---

## Future Plans

### Planned Features (Community Wishlist)

- [ ] Configurable tolerance via UI
- [ ] Multiple encodings per person (automatic handling)
- [ ] Age/gender detection
- [ ] Emotion recognition
- [ ] Face landmarks/analysis
- [ ] Integration with Frigate/Doods
- [ ] Config flow (UI configuration)
- [ ] Face quality scoring
- [ ] Liveness detection
- [ ] Better handling of appearance changes

### Contributing

Want to contribute? See the GitHub repository for:
- Issue tracking
- Feature requests
- Pull requests
- Development guidelines

---

## Getting Help

**Before asking:**
1. Check this FAQ
2. Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Enable debug logging and check logs
4. Search existing GitHub issues

**When asking for help:**
1. Home Assistant version
2. System specs (RPi 4, x86, etc.)
3. Error messages/logs
4. What you've tried
5. Expected vs. actual behavior

**Where to ask:**
- GitHub Issues (bugs/features)
- Home Assistant Community Forum
- Home Assistant Discord

---

## Quick Reference

**Install:**
```bash
cp -r local_face_secure /config/custom_components/
# Add local_face_secure: to configuration.yaml
# Restart HA twice
```

**Teach:**
```yaml
service: local_face_secure.teach_face
data:
  entity_id: camera.front_door
  name: Stefan
```

**Recognize:**
```yaml
service: local_face_secure.scan_match
data:
  entity_id: camera.front_door
```

**Delete:**
```yaml
service: local_face_secure.delete_face
data:
  name: Stefan
```

**List:**
```yaml
service: local_face_secure.list_faces
```

**Event:**
```yaml
trigger:
  platform: event
  event_type: local_face_secure.recognized
```
