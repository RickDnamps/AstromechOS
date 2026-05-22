# master/lights/__init__.py
"""
Lights factory — loads the correct driver based on [lights] backend in config.

Usage in main.py:
    from master.lights import load_driver
    lights = load_driver(cfg)   # TeecesDriver or AstroPixelsDriver
"""

import configparser


def load_driver(cfg: configparser.ConfigParser):
    """
    Returns the configured lights driver instance.

    Config (main.cfg or local.cfg):
        [lights]
        backend = teeces          # or astropixels

    Raises ValueError if the backend is unknown.
    Fallback = teeces if the [lights] section is absent.
    """
    backend = cfg.get('lights', 'backend', fallback='teeces').strip().lower()

    if backend == 'teeces':
        from master.lights.teeces import TeecesDriver
        return TeecesDriver(cfg)

    if backend == 'astropixels':
        from master.lights.astropixels import AstroPixelsDriver
        return AstroPixelsDriver(cfg)

    raise ValueError(
        f"Unknown lights backend: {backend!r}. "
        f"Valid values: teeces, astropixels"
    )
