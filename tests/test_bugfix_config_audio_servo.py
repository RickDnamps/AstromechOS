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
