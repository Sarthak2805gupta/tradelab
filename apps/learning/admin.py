from django.contrib import admin
from .models import Module, QuizQuestion, LearningProgress

admin.site.register(Module)
admin.site.register(QuizQuestion)
admin.site.register(LearningProgress)
