# unmanic-plugin-stereo-aac-all-langs

An [Unmanic](https://unmanic.app) plugin that adds a stereo AAC track for **every** audio language
in a file — including streams with no language tag — while leaving all originals untouched.

Fork of [`add_extra_stereo_audio`](https://github.com/Unmanic/unmanic-plugins/tree/official/source/add_extra_stereo_audio)
by Josh Sunnex and yajrendrag (GPL-3).

---

## Why

Jellyfin clients on Android and many TVs cannot DirectPlay AC3 / EAC3 / DTS audio.  
Without a compatible track the server must transcode, wasting CPU and reducing quality.

This plugin appends a stereo AAC clone per language so every client can DirectPlay without
removing the surround original.  The new AAC track is set as the **default audio** so clients
with no AAC support for the surround track pick it automatically.

---

## Differences from the original

| Feature | `add_extra_stereo_audio` | this plugin |
|---|---|---|
| Languages processed | one (configured) | **all**, in a single pass |
| Untagged streams | skipped | **included** (grouped as `und`) |
| Minimum channels | >4 | **none** — stereo AC3/DTS also re-encoded |
| Idempotent | per configured language | per language group |
| Default audio | optional | **always** set on the matching AAC clone |

---

## Settings

| Setting | Default | Description |
|---|---|---|
| `audio_bitrate` | `128k` | Bitrate for each created stereo AAC track |
| `default_language` | `rus` | Language of the AAC clone to mark as default audio; accepts ISO 639-1 (`ru`) or ISO 639-2 (`rus`) |
| `use_libfdk_aac` | `false` | Use `libfdk_aac` encoder; requires an FFmpeg build with libfdk support. Falls back to native `aac` if unchecked. |
| `skip_commentary` | `true` | Skip streams whose title contains "commentary" (case-insensitive) |
| `channels` | *(empty)* | Optional: restrict source streams to this exact channel count |
| `codec_name` | *(empty)* | Optional: restrict source streams to this codec |

---

## What the ffmpeg command looks like

For a file with `rus EAC3 5.1` + `eng AC3 5.1` and `default_language=rus`:

```
ffmpeg -hide_banner -loglevel info -i input.mkv -max_muxing_queue_size 9999 \
  -map 0 -c copy \
  -map 0:a:0 -c:a:2 aac -ac 2 -b:a:2 128k \
      -metadata:s:a:2 language=rus -metadata:s:a:2 "title=Russian (AAC Stereo)" \
  -map 0:a:1 -c:a:3 aac -ac 2 -b:a:3 128k \
      -metadata:s:a:3 language=eng -metadata:s:a:3 "title=English (AAC Stereo)" \
  -disposition:a -default -disposition:a:2 default \
  -y output.mkv
```

Re-running on `output.mkv` adds nothing (idempotent).

---

## Installation

### Local (development) install

1. Locate your Unmanic config directory — by default it is mounted at `/config` inside the
   Unmanic container, which maps to a directory on your host (e.g. `/opt/unmanic/config` or
   wherever you configured it in Docker Compose).

2. The plugin directory is:
   ```
   /config/plugins/
   ```
   Each plugin lives in a subdirectory named after its `id`.

3. Copy the plugin package there:
   ```bash
   cp -r source/add_stereo_aac_all_languages /config/plugins/
   ```
   Or, if running the container with a bind-mount:
   ```bash
   cp -r source/add_stereo_aac_all_languages /path/to/your/unmanic/config/plugins/
   ```

4. In the Unmanic web UI go to **Settings → Plugins** and click **Reload** (or restart Unmanic).
   The plugin `Add Stereo AAC for All Languages` should appear in the list.

5. Enable it in your library's plugin flow under **Settings → Libraries → [library] → Plugins**.

> **Tip:** After installing, run a manual scan or trigger a library test to verify the plugin
> identifies files correctly before letting it process everything.

### Verify the install path

The exact path can be confirmed from the Unmanic docs:
<https://docs.unmanic.app/docs/configuration/plugins/>

Typically the structure inside `/config` is:
```
/config/
  plugins/
    add_stereo_aac_all_languages/
      plugin.py
      info.json
      requirements.txt
      lib/
      ...
```

---

## Running the tests

```bash
python3 -m venv .venv
.venv/bin/pip install python-iso639 pytest
.venv/bin/python -m pytest tests/ -v
```

All 16 tests cover the selection and disposition logic without requiring Unmanic installed.

---

## License

GPL-3 — see [LICENSE](LICENSE).

Based on `add_extra_stereo_audio` © 2021 Josh Sunnex, yajrendrag.
