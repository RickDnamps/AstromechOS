# master/lights/__init__.py
"""
Factory lights — charge le bon driver selon [lights] backend dans config.

Usage dans main.py :
    from master.lights import load_driver
    lights = load_driver(cfg)   # TeecesDriver ou AstroPixelsDriver
"""

import configparser


def load_driver(cfg: configparser.ConfigParser):
    """
    Retourne l'instance du driver lights configuré.

    Config (main.cfg ou local.cfg) :
        [lights]
        backend = teeces          # ou astropixels

    Lève ValueError si le backend est inconnu.
    Fallback = teeces si la section [lights] est absente.
    """
    backend = cfg.get('lights', 'backend', fallback='teeces').strip().lower()

    if backend == 'teeces':
        from master.lights.teeces import TeecesDriver
        return TeecesDriver(cfg)

    if backend == 'astropixels':
        from master.lights.astropixels import AstroPixelsDriver
        return AstroPixelsDriver(cfg)

    raise ValueError(
        f"Backend lights inconnu: {backend!r}. "
        f"Valeurs valides: teeces, astropixels"
    )
