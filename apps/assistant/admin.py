from django.contrib import admin
from .models import Question, AnswerSource


class AnswerSourceInline(admin.TabularInline):
    model = AnswerSource
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question", "owner", "is_grounded", "created_at")
    list_filter = ("is_grounded", "created_at")
    inlines = [AnswerSourceInline]
