"""Aide commune aux tests : une fausse « config.py » le temps d'un test, sans réglages de la page."""
from types import SimpleNamespace

from sources import settings


def avec_config(test, **options):
    """Remplace config.py par ces options (et vide les réglages de la page) jusqu'à la fin du test."""
    ancienne, anciens = settings.config_actuelle(), settings.tout()
    settings.utiliser_config(SimpleNamespace(**options))
    settings.oublier()

    def remettre():
        settings.utiliser_config(ancienne)
        settings.oublier()
        settings._reglages.update(anciens)
    test.addCleanup(remettre)
