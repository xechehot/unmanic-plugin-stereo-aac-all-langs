# Add Stereo AAC for All Languages

Adds an AAC stereo clone for **every** non-AAC-stereo audio stream in a file — one per dub,
per language, per track — while leaving all originals untouched.

Designed for Jellyfin users whose Android devices and TVs cannot DirectPlay AC3/EAC3/DTS.
Adding a parallel AAC stereo track per dub eliminates transcoding for any dubbing choice,
without removing the surround originals.

**Per-track cloning (Variant B):** unlike approaches that create one clone per language, this
plugin clones every individual stream. A file with nine Russian dubs gets nine Russian AAC
clones — each labelled with the original track's name — so any of them can be selected and
DirectPlayed. Note: this can add many tracks on multi-dub releases; that is intentional.

**Idempotent:** each clone is tagged internally with `UNMANIC_STEREO_SOURCE`. Re-running on an
already-processed file detects the tags and adds nothing.

**Smart default selection:** the default audio disposition is placed on the clone of whichever
track was already the default in the source file, so the user's preferred dubbing is selected
automatically by clients. Falls back to the first matching-language clone, then the first clone.
