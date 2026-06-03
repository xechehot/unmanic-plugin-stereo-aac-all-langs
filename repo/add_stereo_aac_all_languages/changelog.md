# Changelog

## 0.0.2

- **Per-track cloning (Variant B):** creates an AAC stereo clone for every non-AAC-stereo
  audio stream instead of one clone per language group. On a typical multi-dub release this
  adds one compatible track per dub, so any dubbing can be selected and DirectPlayed on
  Android/TV without transcoding.
- **Marker-based idempotency:** each clone is tagged with `UNMANIC_STEREO_SOURCE=<signature>`.
  On re-runs the plugin reads these tags and skips sources that already have a clone, so
  processing the same file twice is safe and produces no duplicates.
- **Richer clone titles:** if the source stream has a title the clone is named
  `"<source title> (AAC Stereo)"` (e.g. `"Дубляж (Red Head Sound) (AAC Stereo)"`), making
  every dub identifiable in Jellyfin.
- **Default disposition by source default:** the AAC clone of whichever track was the default
  in the source file is set as the new default — no longer relying solely on `default_language`.
  Falls back to language match then first clone if the source default was already AAC stereo or
  was filtered out.

## 0.0.1

- Initial release.
- Adds stereo AAC clone for every audio language (including untagged streams).
- Idempotent: groups already containing an AAC stereo track are skipped.
- `default_language` setting controls which AAC clone receives the default disposition.
- Optional `channels` and `codec_name` source filters for backward compatibility.
- Based on `add_extra_stereo_audio` 0.0.13 by Josh Sunnex, yajrendrag.
