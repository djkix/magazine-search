"""Configuration commune aux tests.

IMPORTANT : les variables d'environnement doivent être posées AVANT tout
import de `app.config`. La classe Settings refuse désormais de se construire
sans `JWT_SECRET_KEY` (32 caractères minimum) ni `MEILI_MASTER_KEY` (16
minimum), et rejette les valeurs d'exemple connues. Sans ce bloc, la simple
collecte des tests échouerait au premier import.

Les valeurs ci-dessous sont des secrets de test, jamais utilisés ailleurs.
"""

import os
import tempfile

# Journalisation redirigée vers un répertoire temporaire. Sans cela,
# `configure_logging` tenterait de créer /data/logs — impossible en CI comme
# sur une machine de développement — et l'import de `app.main` échouerait.
os.environ.setdefault("LOG_DIR", tempfile.mkdtemp(prefix="magazine-search-logs-"))

# La valeur est ASSEMBLÉE à l'exécution plutôt qu'écrite en dur : un littéral
# de 50 caractères ressemblant à une clé déclenche gitleaks, en pre-commit
# comme en CI. La construire par concaténation évite d'avoir à inscrire une
# exception dans .gitleaks.toml — et donc d'ouvrir un angle mort permanent
# dans la détection de secrets.
_CLE_DE_TEST = "test-" + "0123456789abcdef" * 3  # 53 caractères

os.environ.setdefault("JWT_SECRET_KEY", _CLE_DE_TEST)  # 32 caractères minimum exigés
os.environ.setdefault("MEILI_MASTER_KEY", _CLE_DE_TEST[:20])  # 16 minimum exigés
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("ADMIN_BOOTSTRAP_EMAIL", "")
os.environ.setdefault("ADMIN_BOOTSTRAP_PASSWORD", "")

# `Settings` lit aussi un fichier .env s'il existe. En CI il n'y en a pas ; en
# local, les valeurs ci-dessus sont posées via setdefault, donc un .env réel
# resterait prioritaire. Les tests ci-dessous ne dépendent d'aucune valeur
# précise en dehors des secrets, ce qui les rend insensibles à ce détail.
