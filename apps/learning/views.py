from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from .models import Module, LearningProgress


def _progress_map(request):
    if not request.user.is_authenticated:
        return {}
    return {p.module_id: p for p in LearningProgress.objects.filter(user=request.user)}


def index(request):
    import re
    modules = Module.objects.all()
    progress = _progress_map(request)
    items = []
    total_terms = 0
    total_quiz = 0
    next_module = None
    for m in modules:
        p = progress.get(m.id)
        completed = bool(p and p.completed)
        score = p.quiz_score if p else 0
        words = len(re.sub(r"<[^>]+>", " ", m.body_html or "").split())
        read_min = max(3, round(words / 200))
        items.append({
            "module": m,
            "completed": completed,
            "score": score,
            "read_min": read_min,
        })
        total_terms += len(m.key_terms or [])
        total_quiz += score
        if next_module is None and not completed:
            next_module = m
    completed_n = sum(1 for i in items if i["completed"])
    pct = int(completed_n / len(items) * 100) if items else 0

    # Badges — derived from existing data, no new models needed.
    perfect_quizzes = sum(1 for i in items if i["score"] == 3)
    badges = [
        {"id": "first-step", "icon": "🌱", "label": "First Step",     "hint": "Complete your first module",          "earned": completed_n >= 1},
        {"id": "half-way",   "icon": "⚡",  "label": "Halfway",        "hint": "Complete 5 of 10 modules",            "earned": completed_n >= 5},
        {"id": "full-house", "icon": "🏆", "label": "Full House",     "hint": "Finish every module",                  "earned": completed_n >= len(items) and len(items) > 0},
        {"id": "sharp",      "icon": "🎯", "label": "Sharp Shooter",  "hint": "Score 3/3 on three quizzes",            "earned": perfect_quizzes >= 3},
        {"id": "perfection", "icon": "💎", "label": "Perfectionist",  "hint": "Score 3/3 on every quiz",               "earned": perfect_quizzes >= len(items) and len(items) > 0},
        {"id": "terms",      "icon": "📚", "label": "Term Master",    "hint": "Accumulate 30+ key terms seen",         "earned": total_terms >= 30},
    ]

    return render(request, "learning/index.html", {
        "items": items,
        "overall_pct": pct,
        "done_n": completed_n,
        "total_terms": total_terms,
        "total_quiz": total_quiz,
        "next_module": next_module,
        "badges": badges,
        "earned_count": sum(1 for b in badges if b["earned"]),
    })


def module_detail(request, slug: str):
    module = get_object_or_404(Module, slug=slug)
    questions = list(module.questions.all())
    progress = None
    if request.user.is_authenticated:
        progress, _ = LearningProgress.objects.get_or_create(
            user=request.user, module=module
        )
    return render(request, "learning/module.html", {
        "module": module,
        "questions": questions,
        "progress": progress,
    })


@require_http_methods(["POST"])
def submit_quiz(request, slug: str):
    module = get_object_or_404(Module, slug=slug)
    questions = list(module.questions.all())
    correct = 0
    for q in questions:
        ans = request.POST.get(f"q{q.id}")
        if ans is not None and int(ans) == q.correct_index:
            correct += 1
    if request.user.is_authenticated:
        prog, _ = LearningProgress.objects.get_or_create(user=request.user, module=module)
        prog.quiz_score = max(prog.quiz_score, correct)
        prog.completed = True
        prog.save()
    return render(request, "learning/module.html", {
        "module": module,
        "questions": questions,
        "progress": None,
        "result": {"correct": correct, "total": len(questions)},
    })
