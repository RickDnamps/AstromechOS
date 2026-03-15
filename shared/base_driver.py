"""Interface commune pour tous les drivers hardware."""


class BaseDriver:
    def setup(self) -> bool:
        """Initialise le hardware. Retourne False si échec."""
        raise NotImplementedError

    def shutdown(self) -> None:
        """Arrêt propre du driver."""
        raise NotImplementedError

    def is_ready(self) -> bool:
        """Retourne True si le driver est opérationnel."""
        raise NotImplementedError
