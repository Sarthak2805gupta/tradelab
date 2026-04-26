from django.conf import settings
from django.db import models


class Module(models.Model):
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    summary = models.CharField(max_length=300)
    body_html = models.TextField()
    key_terms = models.JSONField(default=list)  # [{term, definition}]
    did_you_know = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="questions")
    question = models.CharField(max_length=400)
    choices = models.JSONField()  # ["A", "B", "C", "D"]
    correct_index = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.module.slug}: {self.question[:40]}"


class LearningProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_progress",
        null=True, blank=True,
    )
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    quiz_score = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "module")
