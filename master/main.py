"""
R2-D2 Master — Point d'entrée.
Tourne sur Raspberry Pi 4B (dôme).

Séquence de boot:
1. Lecture config
2. Init logging
3. git pull si wlan1 disponible
4. Démarrage UARTController + TeecesController + DeployController
5. Démarrage API Flask (Phase 4 — placeholder minimal ici)
"""

import logging
import configparser
import signal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from master.uart_controller import UARTController
from master.teeces_controller import TeecesController
from master.deploy_controller import DeployController
from master.config.config_loader import load, is_auto_pull_enabled

VERSION_FILE = "/home/artoo/r2d2/VERSION"


def setup_logging(level_str: str) -> None:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def try_git_pull(cfg: configparser.ConfigParser) -> bool:
    """Tentative de git pull au boot si wlan1 connecté et auto_pull activé."""
    import subprocess
    if not is_auto_pull_enabled(cfg):
        logging.info("auto_pull_on_boot désactivé — git pull ignoré")
        return False
    iface = cfg.get('network', 'internet_interface')
    repo = cfg.get('master', 'repo_path')

    try:
        result = subprocess.run(
            ["ip", "addr", "show", iface],
            capture_output=True, text=True, timeout=5
        )
        if "inet " not in result.stdout:
            logging.info(f"{iface} non disponible — git pull ignoré")
            return False
    except Exception:
        return False

    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo,
            timeout=30,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo, capture_output=True, text=True
            )
            logging.info("git pull réussi au démarrage")
            return True
        else:
            logging.warning(f"git pull échoué: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        logging.warning("git pull timeout — démarrage sans update")
        return False
    except Exception as e:
        logging.error(f"git pull erreur: {e}")
        return False


def main() -> None:
    cfg = load()
    setup_logging(cfg.get('master', 'log_level', fallback='INFO'))
    log = logging.getLogger(__name__)
    log.info("=== R2-D2 Master démarrage ===")

    # Boot: tentative git pull
    try_git_pull(cfg)

    # Init composants
    uart = UARTController(cfg)
    teeces = TeecesController(cfg)
    deploy = DeployController(cfg, uart, teeces)

    # Callbacks UART entrants
    def on_heartbeat_ack(value: str) -> None:
        log.debug(f"Heartbeat ACK Slave: {value}")

    def on_telemetry(value: str) -> None:
        log.info(f"Télémétrie Slave: {value}")

    def on_version(value: str) -> None:
        log.info(f"Version Slave: {value}")

    uart.register_callback('H', on_heartbeat_ack)
    uart.register_callback('T', on_telemetry)
    uart.register_callback('V', on_version)

    # Démarrage hardware
    if not uart.setup():
        log.error("UART init échoué — arrêt")
        sys.exit(1)

    if not teeces.setup():
        log.warning("Teeces32 init échoué — mode dégradé (LEDs indisponibles)")

    uart.start()
    teeces.random_mode()
    deploy.start()

    log.info("Master opérationnel")

    # Gestion arrêt propre
    def shutdown(sig, frame):
        log.info("Signal arrêt reçu")
        deploy.stop()
        uart.stop()
        teeces.shutdown()
        log.info("Master arrêté proprement")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Maintien du processus
    signal.pause()


if __name__ == "__main__":
    main()
