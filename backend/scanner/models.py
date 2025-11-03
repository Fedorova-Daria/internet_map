import uuid
from django.db import models
from django.contrib.postgres.fields import JSONField  # Django <= 3.1; для newer use models.JSONField


class ScanSession(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    target = models.CharField(max_length=200)  # e.g. 192.0.2.0/24 or example.com
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    settings = models.JSONField(default=dict, blank=True)  # concurrency, max_depth, prefix etc.
    stats = models.JSONField(default=dict, blank=True)     # counters updated by workers
    meta = models.JSONField(default=dict, blank=True)      # arbitrary info

    class Meta:
        db_table = "network_scan_session"
        ordering = ("-created_at",)

    def mark_running(self):
        from django.utils import timezone
        self.status = self.STATUS_RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_done(self):
        from django.utils import timezone
        self.status = self.STATUS_DONE
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])

    def mark_failed(self):
        from django.utils import timezone
        self.status = self.STATUS_FAILED
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])

