import logging
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MLConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ml"
    verbose_name = "Machine Learning"

    def ready(self):
        # Startup check: verify primary joblib artifact is intact and readable
        if any(cmd in sys.argv for cmd in ["makemigrations", "migrate", "collectstatic", "help"]):
            return
        try:
            from pathlib import Path

            import joblib
            from django.conf import settings

            from .services import check_model_compatibility

            model_path = getattr(settings, "ML_MODEL_PATH", None) or (settings.BASE_DIR / "ml_models" / "ieee_cis_rf.joblib")
            p = Path(model_path)
            if p.exists():
                bundle = joblib.load(str(p))
                check_model_compatibility(bundle, raise_exception=False)
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("ML startup check warning: %s", exc)
