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
# Fixtures
# ---------------------------------------------------------------------------

def _audio(codec_name, channels, channel_layout=None, language=None, title=None):
    s = {"codec_type": "audio", "codec_name": codec_name, "channels": channels}
    if channel_layout:
        s["channel_layout"] = channel_layout
    tags = {}
    if language:
        tags["language"] = language
    if title:
        tags["title"] = title
    if tags:
        s["tags"] = tags
    return s


# ---------------------------------------------------------------------------
# Test 1: two languages, neither covered → both selected
# ---------------------------------------------------------------------------

def test_two_languages_both_selected():
    streams = [
        _audio("eac3", 6, "5.1",    language="rus"),
        _audio("ac3",  6, "5.1",    language="eng"),
    ]
    result = select_streams(streams)
    assert sorted(result) == [0, 1]


# ---------------------------------------------------------------------------
# Test 2: idempotency — already has AAC stereo for both → nothing selected
# ---------------------------------------------------------------------------

def test_idempotent_both_already_covered():
    streams = [
        _audio("eac3", 6, "5.1",    language="rus"),
        _audio("ac3",  6, "5.1",    language="eng"),
        _audio("aac",  2, "stereo", language="rus"),
        _audio("aac",  2, "stereo", language="eng"),
    ]
    result = select_streams(streams)
    assert result == []


# ---------------------------------------------------------------------------
# Test 3: untagged stream (no language field) → "und" group selected
# ---------------------------------------------------------------------------

def test_untagged_stream_selected():
    streams = [
        _audio("dts", 6, "5.1"),  # no language tag
    ]
    result = select_streams(streams)
    assert result == [0]


# ---------------------------------------------------------------------------
# Test 4: commentary track with skip_commentary=True → not selected
# ---------------------------------------------------------------------------

def test_commentary_skipped():
    streams = [
        _audio("ac3", 6, "5.1", language="eng", title="Commentary"),
    ]
    result = select_streams(streams, skip_commentary=True)
    assert result == []


def test_commentary_not_skipped_when_flag_false():
    streams = [
        _audio("ac3", 6, "5.1", language="eng", title="Commentary"),
    ]
    result = select_streams(streams, skip_commentary=False)
    assert result == [0]


# ---------------------------------------------------------------------------
# Test 5: rus already has AAC stereo, eng only AC3 → only eng selected
# ---------------------------------------------------------------------------

def test_covered_language_excluded():
    streams = [
        _audio("eac3", 6, "5.1",    language="rus"),
        _audio("aac",  2, "stereo", language="rus"),
        _audio("ac3",  6, "5.1",    language="eng"),
    ]
    result = select_streams(streams)
    assert result == [2]


# ---------------------------------------------------------------------------
# Test 6: stereo AC3 (not AAC) → selected (codec matters, not channels)
# ---------------------------------------------------------------------------

def test_stereo_non_aac_is_selected():
    streams = [
        _audio("ac3", 2, "stereo", language="eng"),
    ]
    result = select_streams(streams)
    assert result == [0]


# ---------------------------------------------------------------------------
# Test 7: group with multiple channel counts → highest-channel stream chosen
# ---------------------------------------------------------------------------

def test_highest_channel_stream_chosen():
    streams = [
        _audio("ac3",    2, "stereo", language="eng"),
        _audio("dts",    6, "5.1",   language="eng"),
        _audio("truehd", 8, "7.1",   language="eng"),
    ]
    result = select_streams(streams)
    assert result == [2]  # truehd 7.1 has the most channels


# ---------------------------------------------------------------------------
# Test 8: default disposition chooses the rus clone
# ---------------------------------------------------------------------------

def test_default_output_index_matches_default_language():
    streams = [
        _audio("eac3", 6, "5.1", language="rus"),
        _audio("ac3",  6, "5.1", language="eng"),
    ]
    selected = select_streams(streams)            # [0, 1] — rus first
    original_audio_count = 2

    chosen = pick_default_output_index(selected, original_audio_count, "rus", streams)
    # rus is k=0  →  out_a = 2 + 0 = 2
    assert chosen == 2


def test_default_output_index_fallback_when_no_match():
    streams = [
        _audio("ac3", 6, "5.1", language="eng"),
    ]
    selected = select_streams(streams)            # [0]
    original_audio_count = 1

    # default_language "rus" is not present; fall back to first clone
    chosen = pick_default_output_index(selected, original_audio_count, "rus", streams)
    assert chosen == 1  # original_audio_count + 0


def test_default_output_index_accepts_iso639_1():
    """ISO 639-1 two-letter code in default_language normalizes correctly."""
    streams = [
        _audio("eac3", 6, "5.1", language="rus"),
        _audio("ac3",  6, "5.1", language="eng"),
    ]
    selected = select_streams(streams)
    original_audio_count = 2

    # "ru" is the ISO 639-1 code for Russian; should resolve to the rus stream
    chosen = pick_default_output_index(selected, original_audio_count, "ru", streams)
    assert chosen == 2


def test_default_output_index_accepts_iso639_1_stream_tag():
    """Stream language tag stored as ISO 639-1 still matches correctly."""
    streams = [
        _audio("eac3", 6, "5.1", language="ru"),   # tag is 2-letter
        _audio("ac3",  6, "5.1", language="eng"),
    ]
    selected = select_streams(streams)
    original_audio_count = 2

    chosen = pick_default_output_index(selected, original_audio_count, "rus", streams)
    assert chosen == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_und_group_idempotent():
    """Untagged AAC stereo → und group already covered, nothing selected."""
    streams = [
        _audio("dts", 6, "5.1"),                    # no language
        _audio("aac", 2, "stereo"),                  # covers "und"
    ]
    result = select_streams(streams)
    assert result == []


def test_channels_filter_restricts_source():
    """With channels="6", a 2-channel AC3 stream in an otherwise uncovered group is excluded."""
    streams = [
        _audio("ac3", 2, "stereo", language="eng"),  # only stream in group, but channels!=6
    ]
    result = select_streams(streams, channels="6")
    assert result == []


def test_codec_name_filter_restricts_source():
    """With codec_name="dts", an AC3 stream in an uncovered group is excluded."""
    streams = [
        _audio("ac3", 6, "5.1", language="eng"),
    ]
    result = select_streams(streams, codec_name="dts")
    assert result == []


def test_non_audio_streams_ignored():
    """Video and subtitle streams are not counted in audio-relative indexing."""
    streams = [
        {"codec_type": "video",    "codec_name": "h264"},
        {"codec_type": "audio",    "codec_name": "eac3", "channels": 6, "channel_layout": "5.1",
         "tags": {"language": "rus"}},
        {"codec_type": "subtitle", "codec_name": "subrip"},
        {"codec_type": "audio",    "codec_name": "ac3", "channels": 6, "channel_layout": "5.1",
         "tags": {"language": "eng"}},
    ]
    result = select_streams(streams)
    # Audio-relative: rus=0, eng=1
    assert sorted(result) == [0, 1]
