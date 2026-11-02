from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from accounts.models import CreatorCategoryAssignment
from categories.models import Category
from .models import Course, Module, Chapter, Topic
from .services import check_course_readiness
from .models import Question, ChapterQuiz, Course, Module, Chapter, Topic
from .models import MockTest, QuestionSet, CertificateRule
from accounts.models import AuditLog
from .models import Course, Module, Chapter, Topic, Question, ChapterQuiz, MockTest, QuestionSet, CertificateRule, CourseComment
from decimal import Decimal
from .models import PriceProposal, PriceDiscussionMessage
from django.db.models import Q, Max
from django.contrib.auth.decorators import login_required


# ────────────────────────────────────────────────────────────────────────────
# Inline Questions — shared helpers
# ────────────────────────────────────────────────────────────────────────────

SCOPE_TO_FIELD = {
    # scope_type  : Question FK to set when creating a question of this scope
    'chapter': 'chapter_quiz',     # parent is ChapterQuiz
    'module':  'final_question_set',  # parent is QuestionSet belonging to a MODULE mock test
    'final':   'final_question_set',  # parent is QuestionSet belonging to a FINAL mock test
}
SCOPE_TO_USAGE = {
    'chapter': Question.Usage.CHAPTER,
    'module':  Question.Usage.MODULE,
    'final':   Question.Usage.FINAL,
}


def _resolve_scope(course, scope_type, scope_id):
    """Return (parent_obj, fk_field_name) for the given scope.

    For 'chapter'   -> the parent is a ChapterQuiz
    For 'module'    -> the parent is a QuestionSet belonging to a MODULE MockTest
    For 'final'     -> the parent is a QuestionSet belonging to a FINAL  MockTest

    Raises PermissionDenied if the scope object does not belong to the course.
    """
    if scope_type not in SCOPE_TO_FIELD:
        raise PermissionDenied("Invalid scope type.")
    field = SCOPE_TO_FIELD[scope_type]

    if scope_type == 'chapter':
        obj = get_object_or_404(ChapterQuiz, pk=scope_id)
        if obj.chapter.module.course_id != course.id:
            raise PermissionDenied
    else:  # module or final -> QuestionSet
        desired_scope = MockTest.Scope.MODULE if scope_type == 'module' else MockTest.Scope.FINAL
        obj = get_object_or_404(QuestionSet, pk=scope_id, mock_test__course=course, mock_test__scope=desired_scope)
    return obj, field


def _can_edit_course(user, course):
    """Author in DRAFT/CHANGES_REQUESTED, or Admin/CM (read-only)."""
    if user == course.author:
        return course.status in ['DRAFT', 'CHANGES_REQUESTED']
    return user.role in ('ADMIN', 'CONTENT_MANAGER')


def _can_edit_strict(user, course):
    """Only the author, and only in DRAFT/CHANGES_REQUESTED."""
    return user == course.author and course.status in ['DRAFT', 'CHANGES_REQUESTED']


def _next_order(scope_obj, field):
    return (Question.objects.filter(**{field + '_id': scope_obj.id})
                .aggregate(m=Max('order'))['m'] or 0) + 1


def _validate_question_fields(post):
    """Common validation used by add and edit. Returns (data, errors)."""
    errors = []
    text = (post.get('text') or '').strip()
    option_a = (post.get('option_a') or '').strip()
    option_b = (post.get('option_b') or '').strip()
    option_c = (post.get('option_c') or '').strip()
    option_d = (post.get('option_d') or '').strip()
    correct_option = (post.get('correct_option') or '').strip().upper()
    difficulty = post.get('difficulty', 'EASY')
    explanation = (post.get('explanation') or '').strip()
    topic_id = (post.get('topic') or '').strip()

    if not text:
        errors.append('Question text is required.')
    if not option_a or not option_b:
        errors.append('Options A and B are required.')
    if not option_c or not option_d:
        errors.append('Options C and D are required.')
    if correct_option not in ('A', 'B', 'C', 'D'):
        errors.append('Valid correct option (A/B/C/D) is required.')
    if difficulty not in ('EASY', 'MEDIUM', 'HARD'):
        difficulty = 'EASY'

    return {
        'text': text, 'option_a': option_a, 'option_b': option_b,
        'option_c': option_c, 'option_d': option_d,
        'correct_option': correct_option, 'difficulty': difficulty,
        'explanation': explanation, 'topic_id': topic_id,
    }, errors


# ────────────────────────────────────────────────────────────────────────────
# Review & approval workflow
# ────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def submit_for_review(request, course_id):
    """Creator submits the course for review."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    readiness = check_course_readiness(course)
    if not readiness['is_ready']:
        messages.error(request, 'Cannot submit. Please fix the missing items first.')
        return redirect('courses:course_builder', course_id=course_id)

    course.status = 'IN_REVIEW'
    course.save()

    AuditLog.objects.create(
        actor=request.user, action='SUBMIT_COURSE_FOR_REVIEW',
        target_object_id=course.id, ip_address=request.META.get('REMOTE_ADDR'),
    )

    messages.success(request, 'Course submitted for review! You will be notified when it is approved.')
    return redirect('courses:creator_courses')

@login_required
def review_queue(request):
    """Admin/CM view to see courses pending review."""
    if request.user.role not in ['ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    pending_courses = Course.objects.filter(status='IN_REVIEW').order_by('-updated_at')
    return render(request, 'courses/review_queue.html', {'pending_courses': pending_courses})

@login_required
def review_course(request, course_id):
    """Admin/CM reviews a specific course in detail."""
    if request.user.role not in ['ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    course = get_object_or_404(Course, pk=course_id)
    readiness = check_course_readiness(course)

    # Fetch all course data for a comprehensive review
    modules = course.modules.all().prefetch_related('chapters', 'chapters__quiz', 'chapters__quiz__questions')
    topics = course.topics.all()
    bank_questions = course.questions.all().select_related('topic')
    final_mock = course.mock_tests.filter(scope='FINAL').first()
    final_sets = final_mock.sets.all().prefetch_related('questions') if final_mock else []
    rules = course.certificate_rule if hasattr(course, 'certificate_rule') else None
    comments = course.review_comments.all().select_related('author')

    if request.method == 'POST':
        # Handle new comment submission
        comment_text = request.POST.get('comment_text', '').strip()
        if comment_text:
            CourseComment.objects.create(
                course=course, author=request.user, text=comment_text
            )
            messages.success(request, 'Comment added.')
            return redirect('courses:review_course', course_id=course_id)

    return render(request, 'courses/review_course.html', {
        'course': course,
        'readiness': readiness,
        'modules': modules,
        'topics': topics,
        'bank_questions': bank_questions,
        'final_mock': final_mock,
        'final_sets': final_sets,
        'rules': rules,
        'comments': comments
    })

@login_required
@require_POST
def approve_course(request, course_id):
    """Admin/CM approves the course."""
    if request.user.role not in ['ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    course = get_object_or_404(Course, pk=course_id)
    course.status = 'APPROVED'
    course.save()

    AuditLog.objects.create(
        actor=request.user, action='APPROVE_COURSE',
        target_object_id=course.id, ip_address=request.META.get('REMOTE_ADDR'),
    )

    messages.success(request, f'Course "{course.title}" approved! It is now ready for publishing.')
    return redirect('courses:review_queue')

@login_required
@require_POST
def request_changes(request, course_id):
    """Admin/CM requests changes to the course."""
    if request.user.role not in ['ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    course = get_object_or_404(Course, pk=course_id)
    feedback = request.POST.get('feedback', '').strip()

    course.status = 'CHANGES_REQUESTED'
    course.save()

    AuditLog.objects.create(
        actor=request.user, action='REQUEST_CHANGES_COURSE',
        target_object_id=course.id, changes={'feedback': feedback},
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    messages.success(request, f'Changes requested for "{course.title}".')
    return redirect('courses:review_queue')


# ────────────────────────────────────────────────────────────────────────────
# Chapter Quiz  — settings + inline questions
# (The old question_bank / add_question views have been REMOVED.)
# ────────────────────────────────────────────────────────────────────────────

@login_required
def chapter_quiz(request, course_id, chapter_id):
    """Configure a chapter's quiz — settings + inline questions list."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)

    if not _can_edit_course(request.user, course):
        raise PermissionDenied

    can_edit = _can_edit_strict(request.user, course)
    quiz, _ = ChapterQuiz.objects.get_or_create(chapter=chapter)
    questions = quiz.questions.all().order_by('order', 'id')
    topics = course.topics.all().order_by('order')

    return render(request, 'courses/chapter_quiz.html', {
        'course': course,
        'chapter': chapter,
        'quiz': quiz,
        'questions': questions,
        'topics': topics,
        'scope_type': 'chapter',
        'scope_id': str(quiz.id),
        'can_edit': can_edit,
    })

@login_required
@require_POST
def save_chapter_quiz(request, course_id, chapter_id):
    """Save the settings (passing_mark, shuffle) for a chapter quiz."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)

    if not _can_edit_strict(request.user, course):
        raise PermissionDenied

    quiz, _ = ChapterQuiz.objects.get_or_create(chapter=chapter)
    quiz.passing_mark = request.POST.get('passing_mark', 60) or 60
    quiz.shuffle = request.POST.get('shuffle') == 'on'
    quiz.save()

    messages.success(request, f'Quiz settings for "{chapter.title}" saved.')
    return redirect('courses:chapter_quiz', course_id=course_id, chapter_id=chapter_id)


# ────────────────────────────────────────────────────────────────────────────
# Inline question CRUD — scoped to a chapter quiz / module mock / final set
# ────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def question_add_scoped(request, course_id, scope_type, scope_id):
    """Add a new question inline, scoped to a chapter quiz / module mock / final set."""
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied

    scope_obj, field = _resolve_scope(course, scope_type, scope_id)
    data, errors = _validate_question_fields(request.POST)

    if errors:
        for e in errors:
            messages.error(request, e)
    else:
        q = Question(
            course=course,
            text=data['text'],
            option_a=data['option_a'], option_b=data['option_b'],
            option_c=data['option_c'], option_d=data['option_d'],
            correct_option=data['correct_option'],
            explanation=data['explanation'],
            difficulty=data['difficulty'],
            order=_next_order(scope_obj, field),
        )
        setattr(q, field, scope_obj)
        if data['topic_id']:
            topic = course.topics.filter(id=data['topic_id']).first()
            if topic:
                q.topic = topic
        try:
            q.full_clean()
            q.save()
            messages.success(request, f'Question Q{q.order} added.')
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)

    if scope_type == 'chapter':
        return redirect('courses:chapter_quiz', course_id=course_id, chapter_id=scope_obj.chapter.id)
    elif scope_type == 'module':
        return redirect('courses:module_mock_test', course_id=course_id, module_id=scope_obj.mock_test.module_id)
    else:  # final
        return redirect('courses:final_mock_test', course_id=course_id)


@login_required
@require_POST
def question_edit_scoped(request, course_id, scope_type, scope_id, question_id):
    """Edit an existing inline question."""
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied

    scope_obj, field = _resolve_scope(course, scope_type, scope_id)
    q = get_object_or_404(Question, pk=question_id, course=course, **{field + '_id': scope_obj.id})

    data, errors = _validate_question_fields(request.POST)
    if errors:
        for e in errors:
            messages.error(request, e)
    else:
        q.text = data['text']
        q.option_a = data['option_a']
        q.option_b = data['option_b']
        q.option_c = data['option_c']
        q.option_d = data['option_d']
        q.correct_option = data['correct_option']
        q.explanation = data['explanation']
        q.difficulty = data['difficulty']
        if data['topic_id']:
            topic = course.topics.filter(id=data['topic_id']).first()
            q.topic = topic
        else:
            q.topic = None
        try:
            q.full_clean()
            q.save()
            messages.success(request, f'Question Q{q.order} updated.')
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)

    if scope_type == 'chapter':
        return redirect('courses:chapter_quiz', course_id=course_id, chapter_id=scope_obj.chapter.id)
    elif scope_type == 'module':
        return redirect('courses:module_mock_test', course_id=course_id, module_id=scope_obj.mock_test.module_id)
    else:
        return redirect('courses:final_mock_test', course_id=course_id)


@login_required
@require_POST
def question_delete_scoped(request, course_id, scope_type, scope_id, question_id):
    """Delete an inline question. Then renumber so Q1, Q2, … stays consistent."""
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied

    scope_obj, field = _resolve_scope(course, scope_type, scope_id)
    q = get_object_or_404(Question, pk=question_id, course=course, **{field + '_id': scope_obj.id})
    q.delete()
    # renumber the remaining rows
    for i, qq in enumerate(Question.objects.filter(**{field + '_id': scope_obj.id}).order_by('order', 'id'), start=1):
        if qq.order != i:
            qq.order = i
            qq.save(update_fields=['order'])
    messages.success(request, 'Question deleted.')

    if scope_type == 'chapter':
        return redirect('courses:chapter_quiz', course_id=course_id, chapter_id=scope_obj.chapter.id)
    elif scope_type == 'module':
        return redirect('courses:module_mock_test', course_id=course_id, module_id=scope_obj.mock_test.module_id)
    else:
        return redirect('courses:final_mock_test', course_id=course_id)


@login_required
@require_POST
def question_reorder_scoped(request, course_id, scope_type, scope_id):
    """AJAX endpoint: update the `order` field for a list of question ids."""
    import json
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied
    scope_obj, field = _resolve_scope(course, scope_type, scope_id)
    try:
        order = json.loads(request.body or '{}').get('order', [])
    except json.JSONDecodeError:
        return HttpResponseBadRequest('bad json')
    # Build a lookup keyed by the string form of each question id, since the
    # JSON request sends string IDs (UUIDs are not JSON-native).
    qs_map = {str(q.id): q for q in Question.objects.filter(**{field + '_id': scope_obj.id})}
    for idx, qid in enumerate(order, start=1):
        q = qs_map.get(str(qid))
        if q is not None and q.order != idx:
            q.order = idx
            q.save(update_fields=['order'])
    return JsonResponse({'ok': True})


# ────────────────────────────────────────────────────────────────────────────
# Course creation & builder
# ────────────────────────────────────────────────────────────────────────────

@login_required
def creator_courses(request):
    """List courses.
    - Content Creators: see only their own courses
    - Admins and Content Managers: see ALL courses (for review) + price proposals
    - Support / Student roles: not allowed here
    """
    if request.user.role not in ['CONTENT_CREATOR', 'ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    if request.user.role == 'CONTENT_CREATOR':
        # Creators only see their own courses
        courses = Course.objects.filter(author=request.user).order_by('-created_at')
    else:
        # Admins and CMs see ALL courses, with price proposal info prefetched
        courses = (
            Course.objects.all()
            .select_related('author', 'subcategory', 'main_category', 'price_proposal')
            .order_by('-updated_at')
        )

    return render(request, 'courses/creator_courses.html', {
        'courses': courses,
        'is_admin_or_cm': request.user.role in ('ADMIN', 'CONTENT_MANAGER'),
    })

@login_required
def create_course(request):
    """Step 1 of the course creation wizard: Basic Info & Category."""
    if request.user.role != 'CONTENT_CREATOR':
        raise PermissionDenied

    # Fetch categories assigned to this creator
    assignments = CreatorCategoryAssignment.objects.filter(
        creator_profile=request.user.content_creator_profile,
        category__is_active=True
    ).select_related('category', 'category__parent')

    assigned_subcategories = [a.category for a in assignments]

    # Group them by parent for the dropdown
    cat_groups = {}
    for sub in assigned_subcategories:
        parent_name = sub.parent.name if sub.parent else "Other"
        if parent_name not in cat_groups:
            cat_groups[parent_name] = []
        cat_groups[parent_name].append(sub)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subtitle = request.POST.get('subtitle', '').strip()
        description = request.POST.get('description', '').strip()
        level = request.POST.get('level', 'BEGINNER')
        language = request.POST.get('language', 'en')
        subcategory_id = request.POST.get('subcategory', '').strip()

        errors = []
        if not title:
            errors.append('Title is required.')
        if not description or len(description) < 50:
            errors.append('Description must be at least 50 characters.')
        if not subcategory_id:
            errors.append('Please select a subcategory.')

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'courses/create_course.html', {
                'cat_groups': cat_groups,
                'form_data': request.POST
            })

        # Verify subcategory is actually assigned to the creator
        try:
            subcategory = Category.objects.get(pk=subcategory_id, parent__isnull=False)
            if subcategory not in assigned_subcategories:
                raise PermissionDenied
        except Category.DoesNotExist:
            messages.error(request, 'Invalid subcategory selected.')
            return render(request, 'courses/create_course.html', {'cat_groups': cat_groups})

        # Create the course
        main_category = subcategory.parent
        course = Course(
            title=title,
            subtitle=subtitle,
            description=description,
            level=level,
            language=language,
            subcategory=subcategory,
            main_category=main_category,
            author=request.user,
            status='DRAFT'
        )
        course.save()
        messages.success(request, f'Course "{title}" created! You can now add modules and chapters.')
        return redirect('courses:course_builder', course_id=course.id)

    return render(request, 'courses/create_course.html', {'cat_groups': cat_groups})

@login_required
def course_builder(request, course_id):
    """Main Course Builder Wizard View"""
    course = get_object_or_404(Course, pk=course_id)

    # Permission check: only author can edit, or Admin/CM can view
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied

    is_owner = (request.user == course.author)
    can_edit = is_owner and course.status in ['DRAFT', 'CHANGES_REQUESTED']

    readiness = check_course_readiness(course)
    modules = course.modules.all().prefetch_related('chapters')
    topics = course.topics.all().order_by('order')

    return render(request, 'courses/course_builder.html', {
        'course': course,
        'modules': modules,
        'topics': topics,
        'readiness': readiness,
        'can_edit': can_edit,
        'is_owner': is_owner
    })

@login_required
@require_POST
def add_module(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'Module title is required.')
    else:
        order = course.modules.count() + 1
        Module.objects.create(course=course, title=title, order=order)
        messages.success(request, f'Module "{title}" added.')

    return redirect('courses:course_builder', course_id=course_id)

@login_required
@require_POST
def add_chapter(request, course_id, module_id):
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)

    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = request.POST.get('title', '').strip()
    video_url = request.POST.get('video_url', '').strip()
    topic_id = request.POST.get('topic_tag', '').strip()
    is_free_preview = request.POST.get('is_free_preview') == 'on'

    if not title:
        messages.error(request, 'Chapter title is required.')
    else:
        order = module.chapters.count() + 1
        topic = Topic.objects.get(pk=topic_id, course=course) if topic_id else None

        Chapter.objects.create(
            module=module,
            title=title,
            video_url=video_url,
            topic_tag=topic,
            is_free_preview=is_free_preview,
            order=order
        )
        messages.success(request, f'Chapter "{title}" added.')

    return redirect('courses:course_builder', course_id=course_id)

@login_required
@require_POST
def add_topic(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Topic name is required.')
    else:
        order = course.topics.count() + 1
        Topic.objects.create(course=course, name=name, order=order)
        messages.success(request, f'Topic "{name}" added.')

    return redirect('courses:course_builder', course_id=course_id)


# ────────────────────────────────────────────────────────────────────────────
# Course settings, certificate rules, pricing, publishing
# ────────────────────────────────────────────────────────────────────────────

@login_required
def course_settings(request, course_id):
    """Edit course thumbnail and basic details."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied

    if request.method == 'POST':
        if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
            raise PermissionDenied

        thumbnail = request.FILES.get('thumbnail')
        if thumbnail:
            course.thumbnail = thumbnail
            course.save()
            messages.success(request, 'Thumbnail updated successfully.')
        return redirect('courses:course_settings', course_id=course_id)

    return render(request, 'courses/course_settings.html', {'course': course})

@login_required
def certificate_rules(request, course_id):
    """Configure completion and certificate rules."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied

    rule, created = CertificateRule.objects.get_or_create(course=course)

    if request.method == 'POST':
        if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
            raise PermissionDenied

        rule.certificate_enabled = request.POST.get('certificate_enabled') == 'on'
        rule.require_all_chapters_complete = request.POST.get('require_all_chapters_complete') == 'on'
        rule.chapter_quiz_required = request.POST.get('chapter_quiz_required') == 'on'
        rule.chapter_quiz_passing_mark = request.POST.get('chapter_quiz_passing_mark', 60)
        rule.final_mock_passing_mark = request.POST.get('final_mock_passing_mark', 70)
        max_attempts = request.POST.get('max_final_attempts', '')
        rule.max_final_attempts = int(max_attempts) if max_attempts else None
        rule.certificate_title_text = request.POST.get('certificate_title_text', 'Certificate of Completion')
        rule.save()

        messages.success(request, 'Certificate rules saved.')
        return redirect('courses:certificate_rules', course_id=course_id)

    return render(request, 'courses/certificate_rules.html', {'course': course, 'rule': rule})

@login_required
def pricing_view(request, course_id):
    """View and manage the price proposal."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author and request.user.role not in ['ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied

    proposal = getattr(course, 'price_proposal', None)
    messages_list = proposal.messages.all() if proposal else []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'propose' and request.user == course.author and course.status == 'APPROVED':
            price = request.POST.get('price')
            if price:
                proposal = PriceProposal.objects.create(
                    course=course, proposed_price=Decimal(price), proposed_by=request.user
                )
                course.status = 'PRICE_PROPOSED'
                course.save()
                messages.success(request, 'Price proposal submitted!')

        elif action == 'discuss':
            text = request.POST.get('message_text')
            if text and proposal:
                PriceDiscussionMessage.objects.create(proposal=proposal, author=request.user, text=text)
                messages.success(request, 'Message sent.')

        elif action == 'confirm' and request.user.role in ['ADMIN', 'CONTENT_MANAGER'] and course.status == 'PRICE_PROPOSED':
            proposal.is_confirmed = True
            proposal.confirmed_by = request.user
            proposal.confirmed_at = timezone.now()
            proposal.save()

            course.pricing = proposal.proposed_price
            course.status = 'PRICE_CONFIRMED'
            course.save()
            messages.success(request, 'Price confirmed! Creator can now publish.')

        elif action == 'edit_price' and course.status == 'PRICE_PROPOSED':
            new_price = request.POST.get('price')
            if new_price and proposal:
                proposal.proposed_price = Decimal(new_price)
                proposal.save()
                messages.success(request, 'Price updated successfully!')

        return redirect('courses:pricing_view', course_id=course_id)

    return render(request, 'courses/pricing.html', {
        'course': course, 'proposal': proposal, 'messages_list': messages_list
    })

@login_required
@require_POST
def publish_course(request, course_id):
    """Creator publishes the course after price is confirmed."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status != 'PRICE_CONFIRMED':
        raise PermissionDenied

    course.status = 'PUBLISHED'
    course.published_at = timezone.now()
    course.save()

    AuditLog.objects.create(
        actor=request.user, action='PUBLISH_COURSE',
        target_object_id=course.id, ip_address=request.META.get('REMOTE_ADDR'),
    )

    messages.success(request, f'Congratulations! "{course.title}" is now live.')
    return redirect('courses:creator_courses')


# ────────────────────────────────────────────────────────────────────────────
# Final Mock Test — 5 sets, each with inline questions
# ────────────────────────────────────────────────────────────────────────────

@login_required
def final_mock_test(request, course_id):
    """Setup the 5 sets for the final mock test, with inline questions per set."""
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_course(request.user, course):
        raise PermissionDenied

    can_edit = _can_edit_strict(request.user, course)

    mock_test, _ = MockTest.objects.get_or_create(
        course=course, scope='FINAL',
        defaults={'passing_mark': 70, 'time_limit_minutes': 60, 'questions_per_attempt': 20},
    )
    # Ensure 5 sets exist
    for i in range(1, 6):
        QuestionSet.objects.get_or_create(
            mock_test=mock_test, set_number=i, defaults={'title': f'Set {i}'},
        )
    sets = mock_test.sets.all().order_by('set_number').prefetch_related('questions')
    topics = course.topics.all().order_by('order')

    # expose each set's questions to the template (already a related queryset, but
    # we materialize for the inline UI)
    set_data = []
    for s in sets:
        set_data.append({
            'set': s,
            'questions': list(s.questions.all().order_by('order', 'id')),
        })

    return render(request, 'courses/final_mock_test.html', {
        'course': course,
        'mock_test': mock_test,
        'set_data': set_data,
        'topics': topics,
        'can_edit': can_edit,
    })


@login_required
@require_POST
def save_mock_test_settings(request, course_id):
    """Save the top-level mock-test settings (passing_mark, time, q-per-attempt).
    Used by the Final Mock Test settings form.
    """
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied
    mt_id = request.POST.get('mock_test_id')
    mt = get_object_or_404(MockTest, pk=mt_id, course=course, scope='FINAL')
    mt.passing_mark = request.POST.get('passing_mark', 70) or 70
    mt.time_limit_minutes = request.POST.get('time_limit_minutes', 60) or 60
    mt.questions_per_attempt = request.POST.get('questions_per_attempt', 20) or 20
    mt.save()
    messages.success(request, 'Final Mock Test settings saved.')
    return redirect('courses:final_mock_test', course_id=course_id)


# kept for backward compatibility with old templates / form posts; no longer
# does anything because questions are now managed inline per set.
@login_required
@require_POST
def save_mock_set(request, course_id, set_id):
    course = get_object_or_404(Course, pk=course_id)
    if not _can_edit_strict(request.user, course):
        raise PermissionDenied
    set_obj = get_object_or_404(QuestionSet, pk=set_id, mock_test__course=course)
    # Old form used `questions` checkboxes from a shared bank. With the new inline
    # model there's nothing to save here — redirect back.
    messages.info(request, f'Set {set_obj.set_number} is now managed inline.')
    if set_obj.mock_test.scope == 'FINAL':
        return redirect('courses:final_mock_test', course_id=course_id)
    return redirect('courses:module_mock_test', course_id=course_id, module_id=set_obj.mock_test.module_id)


# ────────────────────────────────────────────────────────────────────────────
# Module Mock Test — settings + inline questions per set
# ────────────────────────────────────────────────────────────────────────────

@login_required
def module_mock_test(request, course_id, module_id):
    """Setup the mock test for a specific module — settings + inline questions."""
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)

    if not _can_edit_course(request.user, course):
        raise PermissionDenied

    can_edit = _can_edit_strict(request.user, course)

    mock_test, _ = MockTest.objects.get_or_create(
        course=course, scope='MODULE', module=module,
        defaults={'passing_mark': 60, 'time_limit_minutes': 30, 'questions_per_attempt': 10},
    )
    # Ensure 1 set exists (max 5 allowed, but 1 is minimum)
    QuestionSet.objects.get_or_create(mock_test=mock_test, set_number=1, defaults={'title': 'Set 1'})
    sets = mock_test.sets.all().order_by('set_number').prefetch_related('questions')
    topics = course.topics.all().order_by('order')

    if request.method == 'POST' and can_edit:
        mt_id = request.POST.get('mock_test_id')
        if mt_id == str(mock_test.id):
            mock_test.passing_mark = request.POST.get('passing_mark', 60) or 60
            mock_test.time_limit_minutes = request.POST.get('time_limit_minutes', 30) or 30
            mock_test.questions_per_attempt = request.POST.get('questions_per_attempt', 10) or 10
            mock_test.save()
            messages.success(request, 'Mock test settings saved.')
            return redirect('courses:module_mock_test', course_id=course_id, module_id=module_id)

    # expose each set's questions to the template (already a related queryset, but
    # we materialize for the inline UI)
    set_data = []
    for s in sets:
        set_data.append({
            'set': s,
            'questions': list(s.questions.all().order_by('order', 'id')),
        })

    return render(request, 'courses/module_mock_test.html', {
        'course': course,
        'module': module,
        'mock_test': mock_test,
        'set_data': set_data,
        'topics': topics,
        'can_edit': can_edit,
        'scope_type': 'module',
        'scope_id': str(mock_test.id),
    })


# ────────────────────────────────────────────────────────────────────────────
# Public / student views
# ────────────────────────────────────────────────────────────────────────────

def course_catalogue(request, slug):
    """Public page showing all published courses in a category."""
    category = get_object_or_404(Category, slug=slug, is_active=True)

    # If it's a main category, get all courses in its subcategories
    # If it's a subcategory, get courses directly in that subcategory
    if category.parent is None:
        # Main category
        courses = Course.objects.filter(
            main_category=category, status='PUBLISHED'
        ).order_by('-updated_at')
    else:
        # Subcategory
        courses = Course.objects.filter(
            subcategory=category, status='PUBLISHED'
        ).order_by('-updated_at')

    subcategories = category.children.filter(is_active=True)

    return render(request, 'courses/course_catalogue.html', {
        'category': category,
        'subcategories': subcategories,
        'courses': courses
    })

def course_detail(request, course_id):
    """Public course detail page showing course info and curriculum."""
    course = get_object_or_404(Course, pk=course_id, status='PUBLISHED')

    modules = course.modules.all().prefetch_related('chapters')
    total_chapters = sum(m.chapters.count() for m in modules)
    total_duration = sum(c.duration_seconds for m in modules for c in m.chapters.all())

    # Check if student is enrolled (placeholder for later)
    is_enrolled = False
    if request.user.is_authenticated and request.user.role == 'STUDENT':
        is_enrolled = True  # Placeholder - will check Enrollment model later

    return render(request, 'courses/course_detail.html', {
        'course': course,
        'modules': modules,
        'total_chapters': total_chapters,
        'total_duration': total_duration,
        'is_enrolled': is_enrolled
    })

@login_required
def course_learn(request, course_id):
    """Student learning page - watch videos and access content."""
    course = get_object_or_404(Course, pk=course_id, status='PUBLISHED')

    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can access the learning portal.')
        return redirect('courses:course_detail', course_id=course_id)

    modules = course.modules.all().prefetch_related('chapters')

    # Get the first chapter as default
    first_chapter = None
    for module in modules:
        if module.chapters.exists():
            first_chapter = module.chapters.first()
            break

    return render(request, 'courses/course_learn.html', {
        'course': course,
        'modules': modules,
        'first_chapter': first_chapter
    })

@login_required
@require_POST
def edit_chapter(request, course_id, chapter_id):
    """Edit an existing chapter's title / video / topic / free-preview flag."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = request.POST.get('title', '').strip()
    video_url = request.POST.get('video_url', '').strip()
    topic_id = request.POST.get('topic_tag', '').strip()
    is_free_preview = request.POST.get('is_free_preview') == 'on'

    if not title:
        messages.error(request, 'Chapter title is required.')
    else:
        chapter.title = title
        chapter.video_url = video_url
        chapter.is_free_preview = is_free_preview
        if topic_id:
            chapter.topic_tag = Topic.objects.filter(pk=topic_id, course=course).first()
        else:
            chapter.topic_tag = None
        chapter.save()
        messages.success(request, f'Chapter "{title}" updated.')

    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def delete_chapter(request, course_id, chapter_id):
    """Delete a chapter from a module."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = chapter.title
    chapter.delete()
    messages.success(request, f'Chapter "{title}" deleted.')
    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def edit_module(request, course_id, module_id):
    """Edit a module's title."""
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'Module title is required.')
    else:
        module.title = title
        module.save()
        messages.success(request, f'Module renamed to "{title}".')

    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def delete_module(request, course_id, module_id):
    """Delete a module and all its chapters."""
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied

    title = module.title
    module.delete()
    messages.success(request, f'Module "{title}" deleted (and all its chapters).')
    return redirect('courses:course_builder', course_id=course_id)

@login_required
@require_POST
def edit_chapter(request, course_id, chapter_id):
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
    title = request.POST.get('title', '').strip()
    video_url = request.POST.get('video_url', '').strip()
    topic_id = request.POST.get('topic_tag', '').strip()
    is_free_preview = request.POST.get('is_free_preview') == 'on'
    if not title:
        messages.error(request, 'Chapter title is required.')
    else:
        chapter.title = title
        chapter.video_url = video_url
        chapter.is_free_preview = is_free_preview
        chapter.topic_tag = Topic.objects.filter(pk=topic_id, course=course).first() if topic_id else None
        chapter.save()
        messages.success(request, f'Chapter "{title}" updated.')
    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def delete_chapter(request, course_id, chapter_id):
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
    title = chapter.title
    chapter.delete()
    messages.success(request, f'Chapter "{title}" deleted.')
    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def edit_module(request, course_id, module_id):
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
    title = request.POST.get('title', '').strip()
    if not title:
        messages.error(request, 'Module title is required.')
    else:
        module.title = title
        module.save()
        messages.success(request, f'Module renamed to "{title}".')
    return redirect('courses:course_builder', course_id=course_id)


@login_required
@require_POST
def delete_module(request, course_id, module_id):
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
    title = module.title
    module.delete()
    messages.success(request, f'Module "{title}" deleted (and all its chapters).')
    return redirect('courses:course_builder', course_id=course_id)