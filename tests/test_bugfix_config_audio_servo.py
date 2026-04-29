import configparser, os, tempfile, pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.config.config_loader import write_cfg_atomic


class TestWriteCfgAtomic:
    def test_writes_key_to_file(self, tmp_path):
        cfg = configparser.ConfigParser()
        cfg.add_section('vesc')
        cfg.set('vesc', 'power_scale', '0.8')
        dest = tmp_path / 'local.cfg'
        write_cfg_atomic(cfg, str(dest))
        readback = configparser.ConfigParser()
        readback.read(str(dest))
        assert readback.get('vesc', 'power_scale') == '0.8'

    def test_no_tmp_file_left_after_success(self, tmp_path):
        cfg = configparser.ConfigParser()
        cfg.add_section('x')
        dest = tmp_path / 'local.cfg'
        write_cfg_atomic(cfg, str(dest))
        assert not os.path.exists(str(dest) + '.tmp')

    def test_original_untouched_if_replace_fails(self, tmp_path, monkeypatch):
        original_content = '[vesc]\npower_scale = 1.0\n'
        dest = tmp_path / 'local.cfg'
        dest.write_text(original_content, encoding='utf-8')
        def boom(src, dst): raise OSError("disk full")
        monkeypatch.setattr(os, 'replace', boom)
        cfg = configparser.ConfigParser()
        cfg.add_section('vesc')
        cfg.set('vesc', 'power_scale', '0.5')
        with pytest.raises(OSError):
            write_cfg_atomic(cfg, str(dest))
        assert dest.read_text(encoding='utf-8') == original_content


import queue, threading, time
from unittest.mock import patch, MagicMock


class TestAudioQueueWorker:
    def _make_driver(self, tmp_path):
        import json
        sounds = tmp_path / 'sounds'
        sounds.mkdir()
        (sounds / 'Happy001.mp3').write_bytes(b'')
        index = {'categories': {'happy': ['Happy001']}}
        (sounds / 'sounds_index.json').write_text(json.dumps(index))
        from slave.drivers.audio_driver import AudioDriver
        d = AudioDriver(sounds_dir=str(sounds))
        d.setup()
        return d

    def test_launch_returns_immediately(self, tmp_path):
        d = self._make_driver(tmp_path)
        popen_started = threading.Event()

        def slow_popen(*args, **kwargs):
            popen_started.set()
            time.sleep(0.2)
            return MagicMock(poll=lambda: None)

        with patch('subprocess.Popen', side_effect=slow_popen):
            t0 = time.monotonic()
            d.play('Happy001', channel=0)
            elapsed = time.monotonic() - t0
            # _launch() must return in <20ms even if Popen blocks for 200ms
            assert elapsed < 0.02, f"_launch blocked for {elapsed*1000:.0f}ms"
            # Keep patch alive until worker fires so slow_popen is reachable
            assert popen_started.wait(timeout=1.0), "Popen never called"
        d.shutdown()

    def test_stop_drains_queued_items(self, tmp_path):
        d = self._make_driver(tmp_path)
        launched = []

        def tracking_popen(*args, **kwargs):
            launched.append(args[0][-1])  # last arg = path
            return MagicMock(poll=lambda: 0)

        with patch('subprocess.Popen', side_effect=tracking_popen):
            # Put items directly on queue (bypasses file-existence check)
            d._launch_q.put((0, '/fake/a.mp3', 32768))
            d._launch_q.put((0, '/fake/b.mp3', 32768))
            d.stop(0)
            time.sleep(0.3)

        # Items drained by stop() — neither should have launched
        assert '/fake/a.mp3' not in launched
        assert '/fake/b.mp3' not in launched
        d.shutdown()
