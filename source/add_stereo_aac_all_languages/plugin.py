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
      - Processes ALL audio languages in a single pass (not a single configured language).
      - Includes streams with no language tag (grouped as "und").
      - Does not require >4 channels; any non-AAC-stereo stream is re-encoded.
      - Idempotent: groups already containing an AAC stereo track are skipped.
      - The new AAC stereo track matching default_language is set as the default audio.

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
        "audio_bitrate":   "128k",
        "default_language": "rus",
        "use_libfdk_aac":  False,
        "skip_commentary": True,
        "channels":        "",
        "codec_name":      "",
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


def select_streams(probe_streams, *, channels="", codec_name="", skip_commentary=True):
    """
    Return a list of audio-relative indices needing a stereo-AAC clone.

    One index per uncovered language group (key "und" for untagged streams).
    Idempotent: groups already containing an AAC stereo track are skipped.
    """
    # Collect audio streams in source order with their audio-relative index.
    audio_streams = []
    for stream in probe_streams:
        if stream.get("codec_type") == "audio":
            audio_streams.append(stream)

    # Group by language, filtering commentary tracks before grouping so they
    # don't count toward "already covered" coverage either.
    groups = {}  # lang -> [(audio_idx, stream), ...]
    for audio_idx, stream in enumerate(audio_streams):
        if skip_commentary:
            title = stream.get("tags", {}).get("title", "")
            if "commentary" in title.lower():
                continue
        lang = stream.get("tags", {}).get("language") or "und"
        if lang not in groups:
            groups[lang] = []
        groups[lang].append((audio_idx, stream))

    selected = []
    for lang, streams_in_group in groups.items():
        # Already covered: group contains at least one AAC stereo stream.
        already_covered = any(
            s.get("codec_name") == "aac"
            and s.get("channels") == 2
            and s.get("channel_layout", "stereo") == "stereo"
            for _, s in streams_in_group
        )
        if already_covered:
            continue

        # Apply optional source filters.
        eligible = [
            (idx, s) for idx, s in streams_in_group
            if (not channels or str(s.get("channels", "")) == str(channels))
            and (not codec_name or s.get("codec_name", "") == codec_name)
        ]
        if not eligible:
            continue

        # Highest channel count wins; first occurrence breaks ties (max() is stable).
        best_idx, _ = max(eligible, key=lambda x: x[1].get("channels", 0))
        selected.append(best_idx)

    return selected


def pick_default_output_index(selected_indices, original_audio_count, default_language, probe_streams):
    """
    Return the output audio index (original_audio_count + k) that should receive
    the default disposition.  Falls back to the first clone if no match found.
    """
    audio_streams = [s for s in probe_streams if s.get("codec_type") == "audio"]
    target = _normalize_lang(default_language)

    if target is not None:
        for k, audio_idx in enumerate(selected_indices):
            stream = audio_streams[audio_idx]
            stream_lang = stream.get("tags", {}).get("language", "und")
            if _normalize_lang(stream_lang) == target:
                return original_audio_count + k

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

    audio_bitrate = settings.get_setting('audio_bitrate') or '128k'
    default_language = (settings.get_setting('default_language') or '').lower()
    encoder = 'libfdk_aac' if settings.get_setting('use_libfdk_aac') else 'aac'
    skip_commentary = settings.get_setting('skip_commentary')
    channels = settings.get_setting('channels') or ''
    codec_name = (settings.get_setting('codec_name') or '').lower()

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

        ffmpeg_args += [
            '-map', '0:a:{}'.format(sel),
            '-c:a:{}'.format(out_a), encoder,
            '-ac', '2',
            '-b:a:{}'.format(out_a), audio_bitrate,
        ]

        if lang != "und":
            ffmpeg_args += ['-metadata:s:a:{}'.format(out_a), 'language={}'.format(lang)]
            try:
                if len(lang) == 2:
                    lang_obj = iso639.Language.from_part1(lang)
                elif len(lang) == 3:
                    lang_obj = iso639.Language.from_part3(lang)
                else:
                    lang_obj = None
                lang_name = lang_obj.name if lang_obj else lang
            except Exception:
                lang_name = lang
            title = '{} ({} Stereo)'.format(lang_name, encoder.upper())
        else:
            title = 'Stereo ({})'.format(encoder.upper())

        ffmpeg_args += ['-metadata:s:a:{}'.format(out_a), 'title={}'.format(title)]

    chosen_out_a = pick_default_output_index(selected, original_audio_count, default_language, probe_streams)
    ffmpeg_args += [
        '-disposition:a', '-default',
        '-disposition:a:{}'.format(chosen_out_a), 'default',
    ]

    ffmpeg_args += ['-y', str(outpath)]

    logger.debug("ffmpeg args: %s", ffmpeg_args)

    data['exec_command'] = ['ffmpeg'] + ffmpeg_args

    parser = Parser(logger)
    parser.set_probe(probe_data)
    data['command_progress_parser'] = parser.parse_progress

    return data
