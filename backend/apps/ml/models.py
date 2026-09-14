from django.conf import settings
from django.db import models


class ThresholdConfig(models.Model):
    """
    Append-only log of fraud-score threshold changes.
    Never update a row — each change inserts a new record.
    Query the latest row per `name` to get the active threshold.
    """

    name       = models.CharField(max_length=64, db_index=True,
                                  help_text="Threshold identifier, e.g. 'flag_score' or 'block_score'")
    value      = models.FloatField(help_text="New threshold value (0–1)")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="threshold_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    rationale  = models.TextField(help_text="Required: reason for this change")

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Threshold Config"
        verbose_name_plural = "Threshold Configs"
        get_latest_by = "changed_at"

    def save(self, *args, **kwargs):
        # Enforce append-only: block any update to an existing row.
        if self.pk:
            raise ValueError("ThresholdConfig rows are immutable. Create a new row instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ThresholdConfig rows cannot be deleted.")

    def __str__(self):
        return "%s=%s @ %s by %s" % (
            self.name, self.value,
            self.changed_at.strftime("%Y-%m-%d %H:%M") if self.changed_at else "?",
            self.changed_by,
        )


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
    model_file  = models.FileField(upload_to="ml_models/")  # joblib-serialised model
    metrics     = models.JSONField(default=dict, blank=True) # eval metrics (precision, recall…)
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
    transaction_id = models.CharField(max_length=64, db_index=True)
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
