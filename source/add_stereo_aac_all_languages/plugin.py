#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Copyright (C) 2026

    This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
    Public License as published by the Free Software Foundation, version 3.

    This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
    implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License along with this program.
    If not, see <https://www.gnu.org/licenses/>.

    Based on add_extra_stereo_audio by Josh Sunnex <jsunnex@gmail.com> and yajrendrag,
    from https://github.com/Unmanic/unmanic-plugins (GPL-3).

    Changes from the original:
      - Creates an AAC stereo clone for EVERY non-AAC-stereo audio stream (Variant B / per-track).
      - All originals are kept; clones are appended at the end.
      - Idempotent: existing clones are detected via UNMANIC_STEREO_SOURCE stream metadata tags.
      - The default disposition is set on the clone of the source's own default track
        (or the first language-matching clone, or the first clone as last resort).

"""
import logging

import iso639

# Graceful fallback so tests can import without Unmanic installed.
try:
    from unmanic.libs.unplugins.settings import PluginSettings
except ImportError:
    PluginSettings = object

logger = logging.getLogger("Unmanic.Plugin.add_stereo_aac_all_languages")


class Settings(PluginSettings):
    settings = {
        "audio_bitrate":    "128k",
        "default_language": "rus",
        "use_libfdk_aac":   False,
        "skip_commentary":  True,
        "channels":         "",
        "codec_name":       "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "audio_bitrate": {
                "label": "Bitrate for each created stereo AAC track (e.g. 128k, 192k)",
            },
            "default_language": {
                "label": "Language of the AAC stereo track to mark as default (ISO 639-1 or 639-2, e.g. rus, en)",
            },
            "use_libfdk_aac": {
                "label": "Use libfdk_aac encoder (requires FFmpeg with libfdk_aac support); uses native aac otherwise",
            },
            "skip_commentary": {
                "label": "Skip streams whose title contains 'commentary' (case-insensitive)",
            },
            "channels": {
                "label": "(Optional) Restrict source streams to this channel count",
            },
            "codec_name": {
                "label": "(Optional) Restrict source streams to this codec name",
            },
        }


# ---------------------------------------------------------------------------
# Pure functions — no Unmanic or lib imports; safe to import in tests.
# ---------------------------------------------------------------------------

def _normalize_lang(lang_str):
    """Normalize a language code to ISO 639-3 part3, or None for 'und'/empty."""
    if not lang_str or lang_str == "und":
        return None
    try:
        if len(lang_str) == 2:
            return iso639.Language.from_part1(lang_str).part3
        return iso639.Language.from_part3(lang_str).part3
    except Exception:
        return lang_str.lower()


def _lang_display_name(lang_code):
    """Return a human-readable language name, or None if und/unknown."""
    if not lang_code or lang_code == "und":
        return None
    try:
        if len(lang_code) == 2:
            return iso639.Language.from_part1(lang_code).name
        return iso639.Language.from_part3(lang_code).name
    except Exception:
        return lang_code


def _compute_signature(stream, ordinal_counters):
    """
    Return a stable string signature for a source audio stream.

    Uses the title tag when present.  Falls back to lang|codec|channels|ordinal
    for untitled streams (best-effort — works reliably only when source order is stable).
    """
    title = stream.get("tags", {}).get("title", "")
    if title:
        return title
    lang = stream.get("tags", {}).get("language") or "und"
    codec = stream.get("codec_name", "")
    channels = str(stream.get("channels", ""))
    key = (lang, codec, channels)
    ordinal = ordinal_counters.get(key, 0)
    ordinal_counters[key] = ordinal + 1
    return "{}|{}|{}|{}".format(lang, codec, channels, ordinal)


def _build_cloned_signatures(audio_streams):
    """
    Return the set of source signatures already present as clones.

    Reads the UNMANIC_STEREO_SOURCE tag (case-insensitive) from every audio stream.
    Matroska uppercases custom tag keys, so ffprobe returns them uppercased regardless
    of how they were written.
    """
    cloned = set()
    for stream in audio_streams:
        tags = stream.get("tags", {})
        for key, val in tags.items():
            if key.upper() == "UNMANIC_STEREO_SOURCE":
                if val:
                    cloned.add(val)
                break
    return cloned


def select_streams(probe_streams, *, channels="", codec_name="", skip_commentary=True):
    """
    Return a list of audio-relative indices needing a stereo-AAC clone.

    Per-track semantics: every audio stream that is not already AAC stereo gets
    its own clone, subject to the optional source filters.  Idempotent: streams
    whose signatures are recorded in an existing UNMANIC_STEREO_SOURCE tag are skipped.
    """
    audio_streams = [s for s in probe_streams if s.get("codec_type") == "audio"]
    cloned_signatures = _build_cloned_signatures(audio_streams)

    # Pre-compute signatures for all audio streams (ordinal counter tracks
    # untitled streams with identical lang+codec+channels).
    ordinal_counters = {}
    source_sigs = [_compute_signature(s, ordinal_counters) for s in audio_streams]

    selected = []
    for audio_idx, stream in enumerate(audio_streams):
        # Rule 1: skip streams already in AAC stereo format.
        if stream.get("codec_name") == "aac" and stream.get("channels") == 2:
            continue

        # Rule 2: optional commentary skip.
        if skip_commentary:
            title = stream.get("tags", {}).get("title", "")
            if "commentary" in title.lower():
                continue

        # Rule 3: optional source-codec filter.
        if codec_name and stream.get("codec_name", "") != codec_name:
            continue

        # Rule 4: optional source-channels filter.
        if channels and str(stream.get("channels", "")) != str(channels):
            continue

        # Rule 5: idempotency — skip if a clone already exists for this source.
        if source_sigs[audio_idx] in cloned_signatures:
            continue

        selected.append(audio_idx)

    return selected


def pick_default_output_index(selected_indices, original_audio_count, default_language, probe_streams):
    """
    Return the output audio index that should receive the default disposition.

    Priority order:
    1. Clone of the source stream that had disposition.default == 1.
       If that stream was already AAC stereo (not cloned), use its own output index.
    2. First AAC stereo track (clone or existing) whose language matches default_language.
    3. First created clone.
    """
    audio_streams = [s for s in probe_streams if s.get("codec_type") == "audio"]

    # Priority 1: find the source-default stream.
    for audio_idx, stream in enumerate(audio_streams):
        if stream.get("disposition", {}).get("default") == 1:
            if audio_idx in selected_indices:
                k = list(selected_indices).index(audio_idx)
                return original_audio_count + k
            # Already AAC stereo — keep its own (pass-through) output audio index.
            if stream.get("codec_name") == "aac" and stream.get("channels") == 2:
                return audio_idx
            # Filtered out (commentary, codec, channels) — fall through to priority 2.
            break

    # Priority 2: first clone or existing AAC stereo whose language matches default_language.
    target = _normalize_lang(default_language)
    if target is not None:
        # Check clones first.
        for k, audio_idx in enumerate(selected_indices):
            stream = audio_streams[audio_idx]
            stream_lang = stream.get("tags", {}).get("language", "und")
            if _normalize_lang(stream_lang) == target:
                return original_audio_count + k
        # Then existing AAC stereo tracks (not cloned).
        for audio_idx, stream in enumerate(audio_streams):
            if stream.get("codec_name") == "aac" and stream.get("channels") == 2:
                stream_lang = stream.get("tags", {}).get("language", "und")
                if _normalize_lang(stream_lang) == target:
                    return audio_idx

    # Priority 3: first clone.
    return original_audio_count


# ---------------------------------------------------------------------------
# Unmanic hooks
# ---------------------------------------------------------------------------

def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue.

    :param data:
    :return:
    """
    from add_stereo_aac_all_languages.lib.ffmpeg import Probe

    probe = Probe.init_probe(data, logger, allowed_mimetypes=['audio', 'video'])
    if probe is None:
        return data

    probe_streams = probe.get_probe()["streams"]

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    selected = select_streams(
        probe_streams,
        channels=(settings.get_setting('channels') or ''),
        codec_name=(settings.get_setting('codec_name') or '').lower(),
        skip_commentary=settings.get_setting('skip_commentary'),
    )

    if selected:
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '%s' needs %d stereo AAC clone(s)", data.get('path'), len(selected))
    else:
        logger.debug("File '%s' — no streams need stereo AAC cloning", data.get('path'))

    return data


def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        exec_command            - A command that Unmanic should execute. Can be empty.
        command_progress_parser - A function that Unmanic can use to parse the STDOUT of the command.
        file_in                 - The source file to be processed by the command.
        file_out                - The destination that the command should output.
        original_file_path      - The absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed.

    :param data:
    :return:
    """
    data['exec_command'] = []
    data['repeat'] = False

    abspath = data.get('file_in')
    outpath = data.get('file_out')

    from add_stereo_aac_all_languages.lib.ffmpeg import Probe, Parser

    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])
    if not probe_data.file(abspath):
        logger.debug("Probe failed for '%s'", abspath)
        return data

    probe_streams = probe_data.get_probe()["streams"]

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    audio_bitrate   = settings.get_setting('audio_bitrate') or '128k'
    default_language = (settings.get_setting('default_language') or '').lower()
    encoder          = 'libfdk_aac' if settings.get_setting('use_libfdk_aac') else 'aac'
    skip_commentary  = settings.get_setting('skip_commentary')
    channels         = settings.get_setting('channels') or ''
    codec_name       = (settings.get_setting('codec_name') or '').lower()

    selected = select_streams(
        probe_streams,
        channels=channels,
        codec_name=codec_name,
        skip_commentary=skip_commentary,
    )

    if not selected:
        logger.debug("No streams to encode in '%s'", abspath)
        return data

    original_audio_count = sum(1 for s in probe_streams if s.get("codec_type") == "audio")
    audio_streams = [s for s in probe_streams if s.get("codec_type") == "audio"]

    # Pre-compute signatures for all audio streams so we can tag each clone.
    sig_counters = {}
    source_sigs = [_compute_signature(s, sig_counters) for s in audio_streams]

    encoder_label = encoder.upper()

    ffmpeg_args = [
        '-hide_banner', '-loglevel', 'info',
        '-i', str(abspath),
        '-max_muxing_queue_size', '9999',
        '-map', '0', '-c', 'copy',
    ]

    for k, sel in enumerate(selected):
        out_a = original_audio_count + k
        stream = audio_streams[sel]
        lang = stream.get("tags", {}).get("language") or "und"
        source_title = stream.get("tags", {}).get("title", "")
        sig = source_sigs[sel]

        ffmpeg_args += [
            '-map', '0:a:{}'.format(sel),
            '-c:a:{}'.format(out_a), encoder,
            '-ac', '2',
            '-b:a:{}'.format(out_a), audio_bitrate,
        ]

        if lang != "und":
            ffmpeg_args += ['-metadata:s:a:{}'.format(out_a), 'language={}'.format(lang)]

        if source_title:
            clone_title = '{} ({} Stereo)'.format(source_title, encoder_label)
        else:
            lang_name = _lang_display_name(lang)
            if lang_name:
                clone_title = '{} ({} Stereo)'.format(lang_name, encoder_label)
            else:
                clone_title = 'Stereo ({})'.format(encoder_label)

        ffmpeg_args += [
            '-metadata:s:a:{}'.format(out_a), 'title={}'.format(clone_title),
            '-metadata:s:a:{}'.format(out_a), 'UNMANIC_STEREO_SOURCE={}'.format(sig),
        ]

    chosen_out_a = pick_default_output_index(selected, original_audio_count, default_language, probe_streams)
    ffmpeg_args += [
        '-disposition:a', '0',
        '-disposition:a:{}'.format(chosen_out_a), 'default',
    ]

    ffmpeg_args += ['-y', str(outpath)]

    logger.debug("ffmpeg args: %s", ffmpeg_args)

    data['exec_command'] = ['ffmpeg'] + ffmpeg_args

    parser = Parser(logger)
    parser.set_probe(probe_data)
    data['command_progress_parser'] = parser.parse_progress

    return data
