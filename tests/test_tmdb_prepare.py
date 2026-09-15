import io
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

import tmdb_prepare as prepare


class ClassificationTests(unittest.TestCase):
    def test_series_markers(self):
        names = [
            "Example.Show.S01E02.1080p.mkv",
            "Example.Show.1x02.WEB-DL.mkv",
            "Example.Show.S01.Complete.mkv",
            "Example.Show.Season.2.mkv",
            "Example.Show.Stagione.3.mkv",
            "Example.Show.Complete.Series.mkv",
            "Example.Show.Serie.Completa.mkv",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(prepare.has_series_marker(name))

    def test_auto_series_marker_uses_tv_search_and_fallback(self):
        calls = []

        def no_result(title, year, media):
            calls.append((title, year, media))
            return None, None

        result = prepare.classify_torrent(
            "Example.Show.S01E02.1080p.mkv", "auto", no_result)

        self.assertEqual(result.media, "tv")
        self.assertEqual(result.folder_name, "Example Show")
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(calls, [("Example Show", None, "tv")])

    def test_auto_movie_from_multi_search(self):
        calls = []

        def movie_result(title, year):
            calls.append((title, year))
            return "movie", "Titolo ufficiale", "2025"

        result = prepare.classify_torrent(
            "Movie.Title.2025.2160p.mkv", "auto",
            multi_search=movie_result)

        self.assertEqual(result.media, "movie")
        self.assertEqual(result.folder_name, "Titolo ufficiale (2025)")
        self.assertEqual(result.source, "TMDB-AUTO")
        self.assertEqual(calls, [("Movie Title", "2025")])

    def test_auto_series_without_marker_from_multi_search(self):
        result = prepare.classify_torrent(
            "Series.Name.1080p.mkv", "auto",
            multi_search=lambda title, year: ("tv", "Nome ufficiale", "2024"))

        self.assertEqual(result.media, "tv")
        self.assertEqual(result.folder_name, "Nome ufficiale")

    def test_auto_unknown_stays_unclassified(self):
        result = prepare.classify_torrent(
            "Unknown.Release.mkv", "auto",
            multi_search=lambda title, year: (None, None, None))
        self.assertIsNone(result)

    def test_manual_path_remains_authoritative(self):
        result = prepare.classify_torrent(
            "Show.S01E02.mkv", "movie",
            specific_search=lambda title, year, media: (None, None))
        self.assertEqual(result.media, "movie")

    def test_multi_result_filters_people_and_prefers_year(self):
        results = [
            {"media_type": "person", "name": "Movie Title"},
            {
                "media_type": "tv", "name": "Movie Title",
                "first_air_date": "2020-01-01",
            },
            {
                "media_type": "movie", "title": "Movie Title",
                "release_date": "2025-05-10",
            },
        ]
        selected = prepare.select_tmdb_multi_result(results, "2025")
        self.assertEqual(selected["media_type"], "movie")


class RoutingTests(unittest.TestCase):
    def test_explicit_auto_and_external_paths(self):
        with mock.patch.multiple(
                prepare,
                INBOX_DIR="/media",
                FILM_DIR="/media/FILM",
                SERIE_DIR="/media/SERIE"):
            self.assertEqual(prepare.route_for_path("/media/FILM"), "movie")
            self.assertEqual(
                prepare.route_for_path("/media/FILM/Existing"), "movie")
            self.assertEqual(prepare.route_for_path("/media/SERIE"), "tv")
            self.assertEqual(prepare.route_for_path("/media"), "auto")
            self.assertEqual(prepare.route_for_path("/media/MUSICA"), "skip")
            self.assertEqual(prepare.route_for_path("/other"), "skip")


class QbittorrentApiTests(unittest.TestCase):
    def test_requests_include_referer_and_form_content_type(self):
        with mock.patch.object(prepare, "QB_URL", "http://localhost:9999"):
            get_request = prepare.build_qb_request("/api/v2/app/version")
            post_request = prepare.build_qb_request(
                "/api/v2/torrents/stop", {"hashes": "abc"})

        self.assertEqual(get_request.get_header("Referer"), "http://localhost:9999")
        self.assertEqual(post_request.get_header("Referer"), "http://localhost:9999")
        self.assertEqual(
            post_request.get_header("Content-type"),
            "application/x-www-form-urlencoded")
        self.assertEqual(get_request.get_method(), "GET")
        self.assertEqual(post_request.get_method(), "POST")

    def test_version_specific_pause_and_start_endpoints(self):
        with mock.patch.object(prepare, "qb_post") as post:
            prepare.qb_pause("abc", "v5.2.3")
            prepare.qb_start("abc", "v5.2.3")
            prepare.qb_pause("abc", "v4.6.7")
            prepare.qb_start("abc", "v4.6.7")

        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            [
                "/api/v2/torrents/stop",
                "/api/v2/torrents/start",
                "/api/v2/torrents/pause",
                "/api/v2/torrents/resume",
            ])

    def test_torrent_lookup_uses_hash_filter(self):
        calls = []

        def fake_get(path):
            calls.append(path)
            return [{"hash": "abcdef", "name": "Example"}]

        with mock.patch.object(prepare, "qb_get_json", side_effect=fake_get):
            torrent = prepare.get_torrent_by_hash("ABCDEF")

        self.assertEqual(torrent["name"], "Example")
        self.assertEqual(calls, ["/api/v2/torrents/info?hashes=ABCDEF"])

    def test_set_location_errors_never_start_torrent(self):
        for status in (400, 403, 409):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                destination = os.path.join(tmp, "destination")
                error = urllib.error.HTTPError(
                    "http://localhost/api/v2/torrents/setLocation",
                    status, "failure", {}, io.BytesIO(b"failure"))
                with mock.patch.object(
                        prepare, "qb_post", side_effect=error), \
                        mock.patch.object(prepare, "qb_start") as start:
                    success = prepare.relocate_torrent(
                        "abc", destination, "v5.2.3")
                self.assertFalse(success)
                start.assert_not_called()

    def test_successful_relocation_starts_torrent(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = os.path.join(tmp, "destination")
            with mock.patch.object(prepare, "qb_post") as post, \
                    mock.patch.object(prepare, "qb_start") as start:
                success = prepare.relocate_torrent(
                    "abc", destination, "v5.2.3")

        self.assertTrue(success)
        post.assert_called_once_with(
            "/api/v2/torrents/setLocation",
            {"hashes": "abc", "location": destination})
        start.assert_called_once_with("abc", "v5.2.3")

    def test_unknown_inbox_torrent_is_paused_and_not_relocated(self):
        torrent = {
            "hash": "abc",
            "name": "Unknown.Release.mkv",
            "save_path": "/media",
        }
        with mock.patch.multiple(
                prepare,
                TMDB_TOKEN="dummy-read-token",
                qb_login=mock.DEFAULT,
                qb_versions=mock.DEFAULT,
                get_torrent_by_hash=mock.DEFAULT,
                route_for_path=mock.DEFAULT,
                qb_pause=mock.DEFAULT,
                cleanup_empty_folders=mock.DEFAULT,
                classify_torrent=mock.DEFAULT,
                relocate_torrent=mock.DEFAULT) as patched:
            patched["qb_versions"].return_value = ("v5.2.3", "2.15.0")
            patched["get_torrent_by_hash"].return_value = torrent
            patched["route_for_path"].return_value = "auto"
            patched["classify_torrent"].return_value = None

            status = prepare.main(["--hash", "abc"])

        self.assertEqual(status, 0)
        patched["qb_pause"].assert_called_once_with("abc", "v5.2.3")
        patched["relocate_torrent"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
