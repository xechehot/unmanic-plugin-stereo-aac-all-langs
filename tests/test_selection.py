"""
Unit tests for select_streams and pick_default_output_index.

Run without Unmanic installed:
    pip install python-iso639
    pytest tests/test_selection.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

from add_stereo_aac_all_languages.plugin import select_streams, pick_default_output_index


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _audio(codec_name, channels, *, language=None, title=None, disposition_default=False,
           unmanic_src=None):
    s = {
        "codec_type": "audio",
        "codec_name": codec_name,
        "channels": channels,
    }
    tags = {}
    if language:
        tags["language"] = language
    if title:
        tags["title"] = title
    if unmanic_src is not None:
        # Matroska returns custom keys uppercased.
        tags["UNMANIC_STEREO_SOURCE"] = unmanic_src
    if tags:
        s["tags"] = tags
    if disposition_default:
        s["disposition"] = {"default": 1}
    return s


# Dune Part Two — 11 audio streams.
# Stream #1 is the source default (Bravo Records eac3 rus).
# Stream #4 (index 3) is already aac 2ch → must NOT be selected.
DUNE_STREAMS = [
    _audio("eac3", 6, language="rus", title="Дубляж (Bravo Records)", disposition_default=True),
    _audio("ac3",  6, language="rus", title="Дубляж (Red Head Sound)"),
    _audio("ac3",  2, language="rus", title="Дубляж (Jaskier)"),
    _audio("aac",  2, language="rus", title="Дубляж (HDRezka Studio)"),  # already AAC stereo
    _audio("eac3", 6, language="rus", title="MVO (Lost Film)"),
    _audio("ac3",  6, language="rus", title="MVO (TVShows)"),
    _audio("ac3",  2, language="rus", title="MVO (Jaskier)"),
    _audio("eac3", 6, language="rus", title="AVO (Юрий Сербин)"),
    _audio("eac3", 6, language="rus", title="VO (Михаил Яроцкий)"),
    _audio("ac3",  6, language="ukr", title="Postmodern"),
    _audio("eac3", 6, language="eng", title="Original English Atmos"),
]

# Clones appended to DUNE_STREAMS to simulate an already-processed file.
# Each carries UNMANIC_STEREO_SOURCE equal to the source stream's title.
DUNE_CLONE_STREAMS = [
    _audio("aac", 2, language="rus", unmanic_src="Дубляж (Bravo Records)"),
    _audio("aac", 2, language="rus", unmanic_src="Дубляж (Red Head Sound)"),
    _audio("aac", 2, language="rus", unmanic_src="Дубляж (Jaskier)"),
    _audio("aac", 2, language="rus", unmanic_src="MVO (Lost Film)"),
    _audio("aac", 2, language="rus", unmanic_src="MVO (TVShows)"),
    _audio("aac", 2, language="rus", unmanic_src="MVO (Jaskier)"),
    _audio("aac", 2, language="rus", unmanic_src="AVO (Юрий Сербин)"),
    _audio("aac", 2, language="rus", unmanic_src="VO (Михаил Яроцкий)"),
    _audio("aac", 2, language="ukr", unmanic_src="Postmodern"),
    _audio("aac", 2, language="eng", unmanic_src="Original English Atmos"),
]


# ---------------------------------------------------------------------------
# Test 1: Dune fixture — 10 clones needed (all but index 3)
# ---------------------------------------------------------------------------

def test_dune_selects_10_streams():
    result = select_streams(DUNE_STREAMS)
    assert result == [0, 1, 2, 4, 5, 6, 7, 8, 9, 10], (
        "Expected indices of all non-AAC-stereo streams; index 3 (HDRezka aac 2ch) must be absent"
    )


def test_dune_excludes_existing_aac_stereo():
    result = select_streams(DUNE_STREAMS)
    assert 3 not in result, "Index 3 (HDRezka aac 2ch) must be excluded"


# ---------------------------------------------------------------------------
# Test 2: Idempotency — processed file returns no new selections
# ---------------------------------------------------------------------------

def test_idempotent_processed_file_returns_empty():
    processed_streams = DUNE_STREAMS + DUNE_CLONE_STREAMS
    result = select_streams(processed_streams)
    assert result == [], (
        "Re-running on already-processed file must return empty (all sources marked via "
        "UNMANIC_STEREO_SOURCE tags)"
    )


# ---------------------------------------------------------------------------
# Test 3: Stereo-but-not-AAC source is selected (codec matters, not channels)
# ---------------------------------------------------------------------------

def test_stereo_ac3_is_selected():
    streams = [
        _audio("ac3", 2, language="rus", title="Дубляж (Jaskier)"),
    ]
    result = select_streams(streams)
    assert result == [0], "ac3 2ch is not AAC stereo — it must be selected"


# ---------------------------------------------------------------------------
# Test 4: Commentary track skipped when skip_commentary=True
# ---------------------------------------------------------------------------

def test_commentary_skipped_when_flag_true():
    streams = [
        _audio("ac3", 6, language="eng", title="Director Commentary"),
    ]
    assert select_streams(streams, skip_commentary=True) == []


def test_commentary_not_skipped_when_flag_false():
    streams = [
        _audio("ac3", 6, language="eng", title="Director Commentary"),
    ]
    assert select_streams(streams, skip_commentary=False) == [0]


# ---------------------------------------------------------------------------
# Test 5: Untagged-language stream is selected (signature fallback, no crash)
# ---------------------------------------------------------------------------

def test_untagged_language_stream_selected():
    streams = [
        _audio("dts", 6),  # no language, no title
    ]
    result = select_streams(streams)
    assert result == [0]


def test_untagged_idempotent():
    """Untitled untagged stream: signature is und|dts|6|0; clone carries that marker."""
    streams = [
        _audio("dts", 6),
        _audio("aac", 2, unmanic_src="und|dts|6|0"),
    ]
    result = select_streams(streams)
    assert result == []


# ---------------------------------------------------------------------------
# Test 6: Default target — clone of the source-default track (Bravo rus)
# ---------------------------------------------------------------------------

def test_default_target_is_clone_of_source_default():
    selected = select_streams(DUNE_STREAMS)   # [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]
    original_audio_count = len(DUNE_STREAMS)  # 11

    chosen = pick_default_output_index(selected, original_audio_count, "rus", DUNE_STREAMS)

    # Stream 0 (Bravo Records) is first in selected (k=0) → output index = 11 + 0 = 11
    assert chosen == 11, (
        "Default should be the clone of the source-default track (Bravo Records, index 0), "
        "which maps to output audio index 11"
    )


# ---------------------------------------------------------------------------
# Test 7: Default fallback when no source stream has default disposition
# ---------------------------------------------------------------------------

def _strip_disposition(streams):
    """Return a copy of the stream list with all disposition.default cleared."""
    result = []
    for s in streams:
        s2 = dict(s)
        if "disposition" in s2:
            s2 = dict(s2)
            s2["disposition"] = {k: 0 for k in s2["disposition"]}
        result.append(s2)
    return result


def test_default_fallback_to_language_match():
    streams = _strip_disposition(DUNE_STREAMS)
    selected = select_streams(streams)
    original_audio_count = len(streams)

    # default_language=rus → first clone whose source is rus → index 0 → output = 11
    chosen = pick_default_output_index(selected, original_audio_count, "rus", streams)
    assert chosen == original_audio_count + 0


def test_default_fallback_to_first_clone_when_no_language_match():
    streams = _strip_disposition(DUNE_STREAMS)
    selected = select_streams(streams)
    original_audio_count = len(streams)

    # No French streams → falls back to first clone
    chosen = pick_default_output_index(selected, original_audio_count, "fra", streams)
    assert chosen == original_audio_count + 0


# ---------------------------------------------------------------------------
# Existing source-filter tests (unchanged semantics)
# ---------------------------------------------------------------------------

def test_channels_filter_restricts_source():
    streams = [
        _audio("ac3", 2, language="eng"),
    ]
    assert select_streams(streams, channels="6") == []


def test_codec_name_filter_restricts_source():
    streams = [
        _audio("ac3", 6, language="eng"),
    ]
    assert select_streams(streams, codec_name="dts") == []


def test_non_audio_streams_ignored():
    streams = [
        {"codec_type": "video",    "codec_name": "h264"},
        {"codec_type": "audio",    "codec_name": "eac3", "channels": 6,
         "tags": {"language": "rus", "title": "T1"}},
        {"codec_type": "subtitle", "codec_name": "subrip"},
        {"codec_type": "audio",    "codec_name": "ac3",  "channels": 6,
         "tags": {"language": "eng", "title": "T2"}},
    ]
    result = select_streams(streams)
    assert sorted(result) == [0, 1]


def test_iso639_1_default_language_normalizes():
    streams = [
        _audio("eac3", 6, language="rus", title="T1"),
        _audio("ac3",  6, language="eng", title="T2"),
    ]
    selected = select_streams(streams)
    chosen = pick_default_output_index(selected, 2, "ru", streams)
    assert chosen == 2  # rus is k=0 → 2 + 0 = 2


def test_iso639_1_stream_tag_normalizes():
    streams = [
        _audio("eac3", 6, language="ru",  title="T1"),
        _audio("ac3",  6, language="eng", title="T2"),
    ]
    selected = select_streams(streams)
    chosen = pick_default_output_index(selected, 2, "rus", streams)
    assert chosen == 2
