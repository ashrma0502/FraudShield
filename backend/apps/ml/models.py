import uuid

from django.conf import settings
from django.db import models


class ThresholdConfig(models.Model):
    """Append-only log of fraud-score threshold changes."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="threshold_changes",
    )
    value      = models.FloatField()
    rationale  = models.CharField(max_length=512)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Threshold Config"
        verbose_name_plural = "Threshold Configs"

    def __str__(self):
        return "%.3f by %s" % (self.value, self.updated_by)


class MLModel(models.Model):
    """Registry entry for a trained ML model."""

    class Algorithm(models.TextChoices):
        RANDOM_FOREST       = "random_forest",       "Random Forest"
        LOGISTIC_REGRESSION = "logistic_regression", "Logistic Regression"
        GRADIENT_BOOSTING   = "gradient_boosting",   "Gradient Boosting"
        XGBOOST             = "xgboost",             "XGBoost"

    name        = models.CharField(max_length=128)
    version     = models.CharField(max_length=32)
    algorithm   = models.CharField(max_length=64, choices=Algorithm.choices)
    description = models.TextField(blank=True)
    model_file  = models.FileField(upload_to="ml_models/")
    metrics     = models.JSONField(default=dict, blank=True)
    is_active   = models.BooleanField(default=False)
    trained_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("name", "version")]
        verbose_name = "ML Model"
        verbose_name_plural = "ML Models"

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return "%s v%s (%s)" % (self.name, self.version, state)


class PredictionLog(models.Model):
    """Audit record of a single ML fraud prediction."""

    ml_model       = models.ForeignKey(MLModel, on_delete=models.SET_NULL, null=True, related_name="predictions")
    transaction_id = models.UUIDField(db_index=True)
    input_features = models.JSONField()
    fraud_score    = models.FloatField()
    is_fraud       = models.BooleanField()
    latency_ms     = models.IntegerField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Prediction Log"
        verbose_name_plural = "Prediction Logs"

    def __str__(self):
        return "Prediction for %s: %.3f" % (self.transaction_id, self.fraud_score)
