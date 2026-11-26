"""Offline metadata-tagging regression tests. Providers are always stubbed."""
from mutagen.id3 import ID3, TDRC
import music_metadata as mm


def test_source_fields_and_official_video_cleanup():
    result = mm.identify_source(
        {"title": "Untrusted List Title"},
        {"title": "Example Artist - Example Song (Official Audio)",
         "channel": "Example Artist - Topic", "upload_date": "20250101"},
    )
    assert result["artist"] == "Example Artist"
    assert result["title"] == "Example Song"
    assert result["year"] is None  # Upload date is NOT the release date.


def test_explicit_music_fields_take_precedence():
    result = mm.identify_source(
        {"title": "Bad Video Label"},
        {"track": "Real Song", "artist": "Real Artist", "album": "Real Album",
         "release_year": 2021, "track_number": 4},
    )
    assert (result["title"], result["artist"], result["album"], result["year"],
            result["track_number"]) == ("Real Song", "Real Artist", "Real Album", "2021", "4")


def test_musicbrainz_selection_rejects_alternate_versions(monkeypatch):
    monkeypatch.setattr(mm, "_musicbrainz_search", lambda *_: [
        {"title": "Example Song (Live)", "artist-credit": [{"name": "Example Artist"}],
         "releases": [{"id": "00000000-0000-0000-0000-000000000001",
                       "title": "Live EP", "status": "Official", "date": "2021-01-01"}]},
        {"title": "Example Song", "artist-credit": [{"name": "Example Artist"}],
         "releases": [
             {"id": "00000000-0000-0000-0000-000000000002", "title": "Greatest Hits",
              "status": "Official", "date": "2024-01-01",
              "release-group": {"primary-type": "Compilation"}},
             {"id": "00000000-0000-0000-0000-000000000003", "title": "Studio Album",
              "status": "Official", "date": "2022-01-01",
              "release-group": {"primary-type": "Album"}},
         ]},
    ])
    result = mm._musicbrainz_match("Example Song", "Example Artist")
    assert result["album"] == "Studio Album"
    assert result["year"] == "2022"
    assert result["release_ids"][0].endswith("0003")


def test_musicbrainz_no_wrong_artist_match(monkeypatch):
    monkeypatch.setattr(mm, "_musicbrainz_search", lambda *_: [
        {"title": "Same Title", "artist-credit": [{"name": "Different Singer"}],
         "releases": []}
    ])
    assert mm._musicbrainz_match("Same Title", "Original Artist") is None


def test_only_trusted_image_domains():
    assert mm._permitted("https://coverartarchive.org/release/id/front-250", "artwork")
    assert mm._permitted("https://ia802004.us.archive.org/abc", "artwork")
    assert mm._permitted("https://i.ytimg.com/vi/abc/hqdefault.jpg", "youtube")
    assert not mm._permitted("http://i.ytimg.com/vi/abc/hqdefault.jpg", "youtube")
    assert not mm._permitted("https://ytimg.com.attacker.test/vi/a.jpg", "youtube")
    assert not mm._permitted("https://127.0.0.1/private", "artwork")


def test_mp3_id3_tags_and_cover(monkeypatch, tmp_path):
    song = tmp_path / "track.mp3"
    song.write_bytes(b"\x00" * 32)
    monkeypatch.setattr(mm, "_musicbrainz_match", lambda *_: {
        "title": "Example Song", "artist": "Example Artist",
        "album": "Studio Album", "year": "2020",
        "release_ids": ["00000000-0000-0000-0000-000000000003"],
    })
    monkeypatch.setattr(mm, "_cover_art", lambda *_: (
        ("image/jpeg", b"\xff\xd8\xff" + b"fakejpeg"), "coverartarchive",
    ))
    result = mm.tag_mp3(song, {"title": "Example Artist - Example Song"})
    tags = ID3(song)
    assert str(tags["TIT2"]) == "Example Song"
    assert str(tags["TPE1"]) == "Example Artist"
    assert str(tags["TALB"]) == "Studio Album"
    assert str(tags["TDRC"]) == "2020"
    assert tags.getall("APIC")[0].data.startswith(b"\xff\xd8\xff")
    assert result["art_source"] == "coverartarchive"


def test_fallback_without_provider(monkeypatch, tmp_path):
    song = tmp_path / "fallback.mp3"
    song.write_bytes(b"\x00" * 32)
    inherited = ID3()
    inherited.add(TDRC(encoding=3, text=["2025"]))  # YouTube upload date.
    inherited.save(song)
    monkeypatch.setattr(mm, "_musicbrainz_match", lambda *_: None)
    monkeypatch.setattr(mm, "_youtube_art", lambda *_: (None, None))
    result = mm.tag_mp3(song, {"title": "Uploader - Example Song"})
    tags = ID3(song)
    assert str(tags["TIT2"]) == "Example Song"
    assert str(tags["TPE1"]) == "Uploader"
    assert not tags.getall("TALB")
    assert not tags.getall("TDRC")
    assert result["match"] == "youtube"


def test_flac_native_tags_and_embedded_art(monkeypatch):
    """Exercise FLAC's Vorbis comments/Picture without downloading audio."""
    import mutagen.flac
    class FakeFLAC(dict):
        def __init__(self):
            super().__init__()
            self.pictures = []
            self.saved = False
        def clear_pictures(self):
            self.pictures.clear()
        def add_picture(self, picture):
            self.pictures.append(picture)
        def save(self):
            self.saved = True
    tags = FakeFLAC()
    monkeypatch.setattr(mutagen.flac, "FLAC", lambda _: tags)
    monkeypatch.setattr(mm, "_musicbrainz_match", lambda *_: {
        "title": "Example Song", "artist": "Example Artist",
        "album": "Example Album", "year": "2022", "release_ids": ["id"],
    })
    monkeypatch.setattr(mm, "_cover_art", lambda *_: (
        ("image/jpeg", b"\\xff\\xd8\\xff" + b"testimage"), "coverartarchive",
    ))
    result = mm.tag_audio("unused.flac", "flac", {
        "title": "Example Artist - Example Song",
    })
    assert tags["title"] == ["Example Song"]
    assert tags["artist"] == ["Example Artist"]
    assert tags["album"] == ["Example Album"]
    assert tags["date"] == ["2022"]
    assert len(tags.pictures) == 1
    assert tags.pictures[0].mime == "image/jpeg"
    assert tags.saved is True
    assert result["art_source"] == "coverartarchive"
