# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""save_settings()/save_splitter_state() must merge into the existing
settings file rather than overwrite it wholesale -- otherwise saving one
clobbers whatever the other already persisted."""
from rixsviewer.model import user_settings


def _point_settings_file_at(monkeypatch, tmp_path):
    settings_dir = tmp_path / ".rixsviewer"
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", settings_dir / "settings.json")


def test_load_settings_returns_empty_dict_when_file_missing(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)

    assert user_settings.load_settings() == {}


def test_save_settings_round_trips_spec_filename_and_tiff_folder(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)

    user_settings.save_settings("/some/spec/file", "/some/tiff/folder")

    assert user_settings.load_settings() == {
        "spec_filename": "/some/spec/file",
        "tiff_folder": "/some/tiff/folder",
    }


def test_save_splitter_state_round_trips(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)

    user_settings.save_splitter_state({"splitter": "abc123"})

    assert user_settings.load_settings() == {"splitter_state": {"splitter": "abc123"}}


def test_save_settings_does_not_clobber_previously_saved_splitter_state(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)
    user_settings.save_splitter_state({"splitter": "abc123"})

    user_settings.save_settings("/some/spec/file", "/some/tiff/folder")

    saved = user_settings.load_settings()
    assert saved["splitter_state"] == {"splitter": "abc123"}
    assert saved["spec_filename"] == "/some/spec/file"


def test_save_splitter_state_does_not_clobber_previously_saved_spec_settings(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)
    user_settings.save_settings("/some/spec/file", "/some/tiff/folder")

    user_settings.save_splitter_state({"splitter": "abc123"})

    saved = user_settings.load_settings()
    assert saved["spec_filename"] == "/some/spec/file"
    assert saved["splitter_state"] == {"splitter": "abc123"}


def test_save_window_geometry_round_trips(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)

    user_settings.save_window_geometry("abc123")

    assert user_settings.load_settings() == {"window_geometry": "abc123"}


def test_save_window_geometry_does_not_clobber_previously_saved_splitter_state(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)
    user_settings.save_splitter_state({"splitter": "abc123"})

    user_settings.save_window_geometry("xyz789")

    saved = user_settings.load_settings()
    assert saved["splitter_state"] == {"splitter": "abc123"}
    assert saved["window_geometry"] == "xyz789"


def test_save_settings_does_not_clobber_previously_saved_window_geometry(monkeypatch, tmp_path):
    _point_settings_file_at(monkeypatch, tmp_path)
    user_settings.save_window_geometry("xyz789")

    user_settings.save_settings("/some/spec/file", "/some/tiff/folder")

    saved = user_settings.load_settings()
    assert saved["window_geometry"] == "xyz789"
    assert saved["spec_filename"] == "/some/spec/file"
