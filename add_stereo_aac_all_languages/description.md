# Add Stereo AAC for All Languages

Adds a stereo AAC clone for **every** audio language track in a file — including streams with no
language tag — while leaving all original tracks untouched.

Designed for Jellyfin users whose Android devices and TVs cannot DirectPlay AC3/EAC3/DTS.
Adding a parallel AAC stereo track eliminates transcoding without removing the surround original.
The new AAC track is set as the default audio so clients pick it automatically.

**Key differences from `add_extra_stereo_audio`:**

- Processes all languages in a single pass instead of one configured language.
- Handles streams with no language tag (grouped as `und`).
- No minimum channel count requirement — a stereo AC3/DTS track also fails DirectPlay and is
  re-encoded.
- Idempotent: re-running on an already-processed file does nothing.
- The AAC stereo track matching `default_language` is marked as the default audio.
