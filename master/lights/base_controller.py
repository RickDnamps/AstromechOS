# master/lights/base_controller.py
"""
Interface abstraite commune à tous les drivers lights.

Tous les drivers (TeecesDriver, AstroPixelsDriver, …) héritent de cette
classe et implémentent les méthodes marquées @abstractmethod.

Les méthodes non-abstraites sont des alias de rétro-compatibilité pour les
appelants qui utilisaient encore l'ancienne API TeecesController.
"""

from abc import ABC, abstractmethod
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver


class BaseLightsController(BaseDriver, ABC):
    """Interface canonique pour tous les drivers lights R2-D2."""

    # Catalogue d'animations — numérotation T-code commune à tous les drivers
    ANIMATIONS: dict[int, str] = {
        1:  'Random',
        2:  'Flash',
        3:  'Alarm',
        4:  'Short Circuit',
        5:  'Scream',
        6:  'Leia Message',
        7:  'I Heart U',
        8:  'Panel Sweep',
        9:  'Pulse Monitor',
        10: 'Star Wars Scroll',
        11: 'Imperial March',
        12: 'Disco (timed)',
        13: 'Disco',
        14: 'Rebel Symbol',
        15: 'Knight Rider',
        16: 'Test White',
        17: 'Red On',
        18: 'Green On',
        19: 'Lightsaber',
        20: 'Off',
        21: 'VU Meter (timed)',
        92: 'VU Meter',
    }

    # ------------------------------------------------------------------
    # Interface canonique (à implémenter dans chaque driver)
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> bool:
        """Ouvre le port série. Retourne False si échec."""

    @abstractmethod
    def shutdown(self) -> None:
        """Arrêt propre — éteint les LEDs et ferme le port."""

    @abstractmethod
    def is_ready(self) -> bool:
        """True si le port est ouvert et opérationnel."""

    @abstractmethod
    def random_mode(self) -> bool:
        """Mode animations aléatoires (mode normal R2)."""

    @abstractmethod
    def leia(self) -> bool:
        """Mode hologramme Leia."""

    @abstractmethod
    def off(self) -> bool:
        """Éteint toutes les LEDs."""

    @abstractmethod
    def text(self, message: str, target: str = "both") -> bool:
        """Texte défilant sur les logics. target: 'fld' | 'rld' | 'both'"""

    @abstractmethod
    def animation(self, code: int) -> bool:
        """Déclenche une animation par T-code (voir ANIMATIONS)."""

    @abstractmethod
    def psi(self, state: int) -> bool:
        """Contrôle les PSI. 0=off, 1=random, 2-8=couleurs."""

    @abstractmethod
    def raw(self, cmd: str) -> bool:
        """Envoie une commande brute (protocole natif du driver)."""

    @abstractmethod
    def system_error(self, message: str = "") -> bool:
        """Alerte visuelle erreur système."""

    @abstractmethod
    def system_ok(self, message: str = "") -> bool:
        """Confirmation visuelle succès (vert 3s puis retour random)."""

    @abstractmethod
    def slave_offline(self) -> bool:
        """Alerte visuelle Slave hors ligne."""

    @abstractmethod
    def uart_error(self) -> bool:
        """Alerte visuelle erreur UART."""

    @abstractmethod
    def show_version(self, version: str) -> bool:
        """Affiche la version sur les logics."""

    @abstractmethod
    def alert_error(self, code: str = "") -> bool:
        """Affiche un code d'erreur sur les logics."""

    # ------------------------------------------------------------------
    # Aliases de rétro-compatibilité (non-abstraits — hérités gratuitement)
    # ------------------------------------------------------------------

    def all_off(self) -> bool:
        return self.off()

    def leia_mode(self) -> bool:
        return self.leia()

    def psi_mode(self, mode: int) -> bool:
        return self.psi(mode)

    def psi_random(self) -> bool:
        return self.psi(1)

    def fld_text(self, message: str) -> bool:
        return self.text(message, "fld")

    def rld_text(self, message: str) -> bool:
        return self.text(message, "rld")

    def send_raw(self, cmd: str) -> bool:
        return self.raw(cmd)

    def alert_master_offline(self) -> bool:
        return self.slave_offline()
