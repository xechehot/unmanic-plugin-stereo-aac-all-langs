# Changelog

## 0.0.1

- Initial release.
- Adds stereo AAC clone for every audio language (including untagged streams).
- Idempotent: groups already containing an AAC stereo track are skipped.
- `default_language` setting controls which AAC clone receives the default disposition.
- Optional `channels` and `codec_name` source filters for backward compatibility.
- Based on `add_extra_stereo_audio` 0.0.13 by Josh Sunnex, yajrendrag.
