"""Helpers for enriching song recommendations with Spotify metadata."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Dict

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 60 * 60 * 6
_NEGATIVE_CACHE_TTL_SECONDS = 60 * 15
_public_track_cache: dict[str, tuple[float, Dict[str, str]]] = {}
_spotify_track_cache: dict[str, tuple[float, Dict[str, str]]] = {}
_enriched_song_cache: dict[str, tuple[float, Dict[str, str]]] = {}
_cache_lock = threading.Lock()


def _cache_get(cache: dict[str, tuple[float, Dict[str, str]]], key: str) -> Dict[str, str] | None:
    now = time.time()
    with _cache_lock:
        entry = cache.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at <= now:
            cache.pop(key, None)
            return None
        return dict(payload)


def _cache_set(
    cache: dict[str, tuple[float, Dict[str, str]]],
    key: str,
    payload: Dict[str, str],
    ttl_seconds: int,
) -> Dict[str, str]:
    with _cache_lock:
        cache[key] = (time.time() + ttl_seconds, dict(payload))
    return payload


def spotify_search_url(name: str, artist: str = "") -> str:
    query = " ".join(part for part in [name, artist] if part).strip()
    return f"https://open.spotify.com/search/{urllib.parse.quote(query)}"


def _lookup_public_track(name: str, artist: str = "") -> Dict[str, str]:
    query = " ".join(part for part in [name, artist] if part).strip()
    if not query:
        return {"cover_url": "", "preview_url": "", "album": "", "artist": ""}
    cache_key = query.casefold()
    cached = _cache_get(_public_track_cache, cache_key)
    if cached is not None:
        return cached
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": query, "entity": "song", "limit": 1}
    )
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Public artwork lookup failed for %s / %s: %s", name, artist, exc)
        return _cache_set(
            _public_track_cache,
            cache_key,
            {"cover_url": "", "preview_url": "", "album": "", "artist": ""},
            _NEGATIVE_CACHE_TTL_SECONDS,
        )

    results = body.get("results", [])
    if not results:
        return _cache_set(
            _public_track_cache,
            cache_key,
            {"cover_url": "", "preview_url": "", "album": "", "artist": ""},
            _NEGATIVE_CACHE_TTL_SECONDS,
        )
    item = results[0]
    return _cache_set(
        _public_track_cache,
        cache_key,
        {
        "cover_url": item.get("artworkUrl100", "").replace("100x100bb", "512x512bb"),
        "preview_url": item.get("previewUrl", ""),
        "album": item.get("collectionName", ""),
        "artist": item.get("artistName", ""),
        },
        _CACHE_TTL_SECONDS,
    )


class SpotifyClient:
    def __init__(self) -> None:
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        self._access_token = ""
        self._expires_at = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> str:
        if not self.enabled:
            return ""
        now = time.time()
        if self._access_token and now < self._expires_at - 60:
            return self._access_token

        payload = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        basic_auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("utf-8")
        request = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=payload,
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))

        self._access_token = body.get("access_token", "")
        expires_in = int(body.get("expires_in", 3600) or 3600)
        self._expires_at = now + expires_in
        return self._access_token

    def search_track(self, name: str, artist: str = "", album: str = "") -> Dict[str, str]:
        cache_key = " | ".join(part.strip().casefold() for part in [name, artist, album])
        cached = _cache_get(_spotify_track_cache, cache_key)
        if cached is not None:
            return cached
        fallback = {
            "spotify_url": spotify_search_url(name, artist),
            "cover_url": "",
            "album": album,
            "artist": artist,
        }
        token = self._get_access_token()
        if not token:
            return fallback

        query_parts = []
        if name:
            query_parts.append(f'track:"{name}"')
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'album:"{album}"')
        query = " ".join(query_parts) or " ".join(part for part in [name, artist, album] if part)
        url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
            {"q": query, "type": "track", "limit": 3, "market": "US"}
        )
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Spotify track search failed for %s / %s: %s", name, artist, exc)
            return _cache_set(_spotify_track_cache, cache_key, fallback, _NEGATIVE_CACHE_TTL_SECONDS)

        items = body.get("tracks", {}).get("items", [])
        if not items:
            return _cache_set(_spotify_track_cache, cache_key, fallback, _NEGATIVE_CACHE_TTL_SECONDS)

        track = items[0]
        images = track.get("album", {}).get("images", [])
        artists = ", ".join(item.get("name", "") for item in track.get("artists", []))
        return _cache_set(
            _spotify_track_cache,
            cache_key,
            {
            "spotify_url": track.get("external_urls", {}).get("spotify", fallback["spotify_url"]),
            "cover_url": images[0]["url"] if images else "",
            "album": track.get("album", {}).get("name", album),
            "artist": artists or artist,
            "preview_url": track.get("preview_url") or "",
            "spotify_track_id": track.get("id", ""),
            },
            _CACHE_TTL_SECONDS,
        )


_spotify_client = SpotifyClient()


def enrich_song(song: Dict[str, str]) -> Dict[str, str]:
    cache_key = " | ".join(
        part.strip().casefold()
        for part in [song.get("name", ""), song.get("artist", ""), song.get("album", "")]
    )
    cached = _cache_get(_enriched_song_cache, cache_key)
    if cached is not None:
        return {**song, **cached}

    track = _spotify_client.search_track(
        song.get("name", ""),
        song.get("artist", ""),
        song.get("album", ""),
    )
    enriched = dict(song)
    public_track = _lookup_public_track(song.get("name", ""), song.get("artist", ""))
    enriched["spotify_url"] = track.get("spotify_url") or song.get("spotify_url") or spotify_search_url(
        song.get("name", ""),
        song.get("artist", ""),
    )
    enriched["cover_url"] = track.get("cover_url") or public_track.get("cover_url") or song.get("cover_url", "")
    enriched["album"] = track.get("album") or public_track.get("album") or song.get("album", "")
    enriched["artist"] = track.get("artist") or public_track.get("artist") or song.get("artist", "")
    if track.get("preview_url"):
        enriched["preview_url"] = track["preview_url"]
    elif public_track.get("preview_url"):
        enriched["preview_url"] = public_track["preview_url"]
    if track.get("spotify_track_id"):
        enriched["spotify_track_id"] = track["spotify_track_id"]
    metadata_only = {
        "spotify_url": enriched.get("spotify_url", ""),
        "cover_url": enriched.get("cover_url", ""),
        "album": enriched.get("album", ""),
        "artist": enriched.get("artist", ""),
        "preview_url": enriched.get("preview_url", ""),
        "spotify_track_id": enriched.get("spotify_track_id", ""),
    }
    _cache_set(
        _enriched_song_cache,
        cache_key,
        metadata_only,
        _CACHE_TTL_SECONDS,
    )
    return enriched
