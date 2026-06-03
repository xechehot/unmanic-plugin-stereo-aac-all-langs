# unmanic-plugin-stereo-aac-all-langs

An [Unmanic](https://unmanic.app) plugin that adds an AAC stereo clone for **every**
non-AAC-stereo audio stream in a file — one per dub, one per language track — while leaving
all originals untouched.

Fork of [`add_extra_stereo_audio`](https://github.com/Unmanic/unmanic-plugins/tree/official/source/add_extra_stereo_audio)
by Josh Sunnex and yajrendrag (GPL-3).

---

## Why

Jellyfin clients on Android and many TVs cannot DirectPlay AC3 / EAC3 / DTS audio.
Without a compatible track the server must transcode, wasting CPU and reducing quality.

This plugin appends a stereo AAC clone **per stream** so every dub and every language can be
DirectPlayed without removing the surround originals.  
The new default audio is set on the clone of whichever track was already the default in the
source file, so clients with no AAC support for the surround track pick it automatically.

---

## Per-track cloning (Variant B)

Unlike approaches that create one clone per language group, this plugin clones **every**
individual non-AAC-stereo stream.

**Example — Dune Part Two (11 audio streams, 9 Russian dubs):**

| # | Source | Action |
|---|--------|--------|
| 1 | eac3 6ch rus "Дубляж (Bravo Records)" ★ default | → cloned as "Дубляж (Bravo Records) (AAC Stereo)" ★ new default |
| 2 | ac3  6ch rus "Дубляж (Red Head Sound)" | → cloned |
| 3 | ac3  2ch rus "Дубляж (Jaskier)" | → cloned |
| 4 | aac  2ch rus "Дубляж (HDRezka Studio)" | left alone (already AAC stereo) |
| 5–9 | … 5 more rus tracks | → cloned (×5) |
| 10 | ac3  6ch ukr "Postmodern" | → cloned |
| 11 | eac3 6ch eng "Original English Atmos" | → cloned |

Result: 10 new AAC stereo tracks appended, default on the Bravo Records clone.  
**Note:** this intentionally produces many tracks on multi-dub releases.

---

## Idempotency

Each created clone is tagged with `UNMANIC_STEREO_SOURCE=<signature>` in its stream metadata.
On re-runs the plugin reads these tags and skips any source whose clone already exists —
running on the same file twice is safe and adds nothing.

---

## Settings

| Setting | Default | Description |
|---|---|---|
| `audio_bitrate` | `128k` | Bitrate for each created stereo AAC track |
| `default_language` | `rus` | Fallback language for default-audio selection when the source has no default disposition; accepts ISO 639-1 (`ru`) or ISO 639-2 (`rus`) |
| `use_libfdk_aac` | `false` | Use `libfdk_aac` encoder; requires an FFmpeg build with libfdk support. Falls back to native `aac` if unchecked. |
| `skip_commentary` | `true` | Skip streams whose title contains "commentary" (case-insensitive) |
| `channels` | *(empty)* | Optional: restrict source streams to this exact channel count |
| `codec_name` | *(empty)* | Optional: restrict source streams to this codec |

---

## What the ffmpeg command looks like

For a file with `rus EAC3 5.1 "Дубляж"` + `eng AC3 5.1` and `default_language=rus`:

```
ffmpeg -hide_banner -loglevel info -i input.mkv -max_muxing_queue_size 9999 \
  -map 0 -c copy \
  -map 0:a:0 -c:a:2 aac -ac 2 -b:a:2 128k \
      -metadata:s:a:2 language=rus \
      -metadata:s:a:2 "title=Дубляж (AAC Stereo)" \
      -metadata:s:a:2 "UNMANIC_STEREO_SOURCE=Дубляж" \
  -map 0:a:1 -c:a:3 aac -ac 2 -b:a:3 128k \
      -metadata:s:a:3 language=eng \
      -metadata:s:a:3 "title=English (AAC Stereo)" \
      -metadata:s:a:3 "UNMANIC_STEREO_SOURCE=und|ac3|6|0" \
  -disposition:a 0 -disposition:s:a:2 default \
  -y output.mkv
```

Re-running on `output.mkv` detects the `UNMANIC_STEREO_SOURCE` tags and adds nothing.

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

All tests cover the selection and disposition logic without requiring Unmanic installed.

---

## License

GPL-3 — see [LICENSE](LICENSE).

Based on `add_extra_stereo_audio` © 2021 Josh Sunnex, yajrendrag.
