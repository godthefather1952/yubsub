"""Best-effort, conservative MP3 metadata and cover-art enrichment for YUBSUB.

Only trusted provider URLs are fetched. Failed lookups never make an audio
download fail. A MusicBrainz recording must pass strict title/artist matching
before its album or year replaces anything from the source.
"""
import json
import re
import subprocess
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK

USER_AGENT = "YUBSUB/1.1 (+https://github.com/godthefather1952/yubsub)"
MUSICBRAINZ = "https://musicbrainz.org/ws/2/recording/"
MAX_IMAGE_BYTES = 4 * 1024 * 1024
_MB_LOCK = threading.Lock()
_MB_LAST = 0.0


def _text(value):
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(part) for part in value if part)
    return re.sub(r"\s+", " ", str(value or "")).strip()[:240]


def _normalized(value):
    value = unicodedata.normalize("NFKD", _text(value)).casefold()
    value = re.sub(r"\b(feat(?:uring)?|ft)\.?\s+.*$", "", value)
    return re.sub(r"[^\w]+", " ", value).strip()


def _similarity(a, b):
    return SequenceMatcher(None, _normalized(a), _normalized(b)).ratio()


def _clean_title(value):
    value = _text(value)
    return re.sub(
        r"\s*[\[(](?:official (?:music )?video|official audio|official lyric video|"
        r"lyrics?|lyric video|visuali[sz]er|audio)[\])]\s*$",
        "", value, flags=re.I,
    ).strip()


def _year(value):
    match = re.match(r"^(19\d\d|20\d\d|2100)", str(value or ""))
    return match.group(1) if match else None


def identify_source(entry, detail):
    """Use actual YouTube music metadata first; do not infer release year from upload date."""
    entry, detail = entry or {}, detail or {}
    title = _clean_title(detail.get("track") or entry.get("track")
                         or detail.get("title") or entry.get("title"))
    artist = _text(detail.get("artist") or entry.get("artist")
                   or detail.get("creator") or entry.get("creator"))
    channel = _text(detail.get("channel") or detail.get("uploader")
                    or entry.get("channel") or entry.get("uploader"))
    if not artist and " - " in title:
        probable_artist, probable_track = title.split(" - ", 1)
        if probable_artist and probable_track:
            artist, title = probable_artist, probable_track
    if not artist and channel.casefold().endswith(" - topic"):
        artist = channel[:-8].strip()
    if not artist and channel.casefold().endswith("vevo"):
        artist = channel[:-4].strip()
    album = _text(detail.get("album") or entry.get("album"))
    year = _year(detail.get("release_year") or detail.get("release_date")
                 or entry.get("release_year") or entry.get("release_date"))
    track_number = detail.get("track_number") or entry.get("track_number")
    try:
        track_number = str(int(track_number)) if track_number else None
    except (ValueError, TypeError):
        track_number = None
    return dict(title=_clean_title(title), artist=artist, album=album,
                year=year, genre=_text(detail.get("genre") or entry.get("genre")),
                track_number=track_number, match="youtube")


def _permitted(url, purpose):
    try:
        u = urlsplit(url)
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return False
        host = (u.hostname or "").lower()
        if purpose == "musicbrainz":
            return host == "musicbrainz.org"
        if purpose == "artwork":
            return (host == "coverartarchive.org" or host == "archive.org"
                    or host.endswith(".archive.org"))
        if purpose == "youtube":
            return host == "img.youtube.com" or host == "ytimg.com" or host.endswith(".ytimg.com")
    except (ValueError, AttributeError):
        pass
    return False


class _SafeRedirect(HTTPRedirectHandler):
    def __init__(self, purpose):
        self.purpose = purpose

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _permitted(newurl, self.purpose):
            raise ValueError("Refusing untrusted redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, purpose, limit):
    if not _permitted(url, purpose):
        return None
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"
                  if purpose == "musicbrainz" else "image/jpeg,image/png,image/webp"})
    with build_opener(_SafeRedirect(purpose)).open(req, timeout=7) as response:
        if not _permitted(response.geturl(), purpose):
            return None
        size = response.headers.get("Content-Length")
        if size and int(size) > limit:
            return None
        data = response.read(limit + 1)
        return data if len(data) <= limit else None


def _musicbrainz_search(title, artist):
    if not title or not artist:
        return []
    global _MB_LAST
    def quote(value):
        return re.sub(r'["\\]', " ", value)[:120]
    query = 'recording:"{}" AND artist:"{}"'.format(quote(title), quote(artist))
    url = MUSICBRAINZ + "?" + urlencode({"query": query, "fmt": "json", "limit": "10"})
    # One worker in the deployment; serialize concurrent job requests in this worker.
    with _MB_LOCK:
        wait = 1.15 - (time.monotonic() - _MB_LAST)
        if wait > 0:
            time.sleep(wait)
        _MB_LAST = time.monotonic()
        try:
            payload = _fetch(url, "musicbrainz", 512 * 1024)
            return json.loads(payload).get("recordings", []) if payload else []
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
            return []


def _artist_credit(recording):
    credit = recording.get("artist-credit") or []
    return " ".join(
        item if isinstance(item, str) else
        _text(item.get("name") or (item.get("artist") or {}).get("name"))
        for item in credit
    ).strip()


def _release_sort(release):
    group = release.get("release-group") or {}
    return (
        release.get("status") != "Official",
        group.get("primary-type") != "Album",
        release.get("date") or "9999",
        release.get("title") or "",
    )


def _musicbrainz_match(title, artist):
    matches = []
    for rec in _musicbrainz_search(title, artist):
        found_artist = _artist_credit(rec)
        title_sim = _similarity(title, rec.get("title"))
        artist_sim = _similarity(artist, found_artist)
        # Do not label radio edits/remixes/live versions as the studio recording.
        if title_sim < 0.93 or artist_sim < 0.88:
            continue
        matches.append((title_sim * 0.65 + artist_sim * 0.35, rec, found_artist))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    _, rec, found_artist = matches[0]
    releases = [r for r in rec.get("releases", []) if isinstance(r, dict)]
    official = [r for r in releases if r.get("status") == "Official"]
    releases = sorted(official or releases, key=_release_sort)
    chosen = releases[0] if releases else {}
    dates = [_year(r.get("date")) for r in (official or releases)]
    dates = [date for date in dates if date]
    release_ids = [
        r["id"] for r in releases[:3]
        if re.fullmatch(r"[0-9a-fA-F-]{36}", str(r.get("id", "")))
    ]
    return dict(
        title=_text(rec.get("title")), artist=_text(found_artist),
        album=_text(chosen.get("title")), year=min(dates) if dates else None,
        release_ids=release_ids,
    )


def _image_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", data
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", data
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        try:
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                 "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
                input=data, capture_output=True, timeout=8, check=True,
            ).stdout
            if out.startswith(b"\xff\xd8\xff") and len(out) <= MAX_IMAGE_BYTES:
                return "image/jpeg", out
        except (OSError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
    return None


def _cover_art(release_ids):
    for release_id in release_ids:
        url = "https://coverartarchive.org/release/{}/front-250".format(release_id)
        try:
            data = _fetch(url, "artwork", MAX_IMAGE_BYTES)
            result = _image_type(data) if data else None
            if result:
                return result, "coverartarchive"
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
    return None, None


def _youtube_art(detail):
    urls = []
    if detail.get("thumbnail"):
        urls.append(detail["thumbnail"])
    for image in reversed(detail.get("thumbnails") or []):
        if isinstance(image, dict) and image.get("url"):
            urls.append(image["url"])
    for url in urls[:3]:
        try:
            data = _fetch(url, "youtube", MAX_IMAGE_BYTES)
            result = _image_type(data) if data else None
            if result:
                return result, "youtube"
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
    return None, None


def tag_mp3(path, entry=None, detail=None):
    """Tag one completed MP3; callers should catch errors and retain original audio."""
    path = Path(path)
    detail = detail or {}
    tags_data = identify_source(entry, detail)
    matched = _musicbrainz_match(tags_data["title"], tags_data["artist"])
    if matched:
        # Only a confidently matched recording may supply album/year.
        tags_data.update({key: matched[key] for key in ("title", "artist", "album", "year")
                          if matched.get(key)})
        tags_data["match"] = "musicbrainz"
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    values = (
        ("TIT2", TIT2, tags_data["title"]),
        ("TPE1", TPE1, tags_data["artist"]),
        ("TALB", TALB, tags_data["album"]),
        ("TDRC", TDRC, tags_data["year"]),
        ("TCON", TCON, tags_data["genre"]),
        ("TRCK", TRCK, tags_data["track_number"]),
    )
    for frame_name, factory, value in values:
        # yt-dlp's FFmpegMetadata may have set upload date as TDRC, or a
        # channel name as album/artist. Clear those before writing trusted data.
        tags.delall(frame_name)
        if value:
            tags.add(factory(encoding=3, text=[str(value)]))
    if tags_data["album"] and tags_data["artist"]:
        tags.delall("TPE2")
        tags.add(TPE2(encoding=3, text=[tags_data["artist"]]))

    image, art_source = _cover_art(matched.get("release_ids", [])) if matched else (None, None)
    if not image:
        image, art_source = _youtube_art(detail)
    if image:
        mime, data = image
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))
    tags.save(path, v2_version=3)
    tags_data["art_source"] = art_source
    return tags_data


def tag_flac(path, entry=None, detail=None):
    """Write native FLAC Vorbis comments and embedded artwork."""
    from mutagen.flac import FLAC, Picture

    path = Path(path)
    detail = detail or {}
    tags_data = identify_source(entry, detail)
    matched = _musicbrainz_match(tags_data["title"], tags_data["artist"])
    if matched:
        tags_data.update({key: matched[key] for key in ("title", "artist", "album", "year")
                          if matched.get(key)})
        tags_data["match"] = "musicbrainz"

    audio = FLAC(path)
    mapping = {
        "title": "title", "artist": "artist", "album": "album",
        "date": "year", "genre": "genre", "tracknumber": "track_number",
    }
    for frame, field in mapping.items():
        if frame in audio:
            del audio[frame]
        if tags_data.get(field):
            audio[frame] = [str(tags_data[field])]
    if "albumartist" in audio:
        del audio["albumartist"]
    if tags_data["artist"] and tags_data["album"]:
        audio["albumartist"] = [tags_data["artist"]]

    image, art_source = _cover_art(matched.get("release_ids", [])) if matched else (None, None)
    if not image:
        image, art_source = _youtube_art(detail)
    if image:
        mime, payload = image
        picture = Picture()
        picture.type = 3
        picture.mime = mime
        picture.desc = "Cover"
        picture.data = payload
        audio.clear_pictures()
        audio.add_picture(picture)
    audio.save()
    tags_data["art_source"] = art_source
    return tags_data


def tag_audio(path, audio_format, entry=None, detail=None):
    """Best-effort type-dispatched tag writer for existing audio files."""
    if audio_format == "mp3":
        return tag_mp3(path, entry, detail)
    if audio_format == "flac":
        return tag_flac(path, entry, detail)
    raise ValueError("Unsupported audio format for tagging")
