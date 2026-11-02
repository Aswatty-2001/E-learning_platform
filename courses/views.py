from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.models import CreatorCategoryAssignment
from categories.models import Category
from .models import Course, Module, Chapter, Topic
from .services import check_course_readiness
from .models import Question, ChapterQuiz, Course, Module, Chapter, Topic
from django.views.decorators.http import require_POST
from .models import MockTest, QuestionSet, CertificateRule
from django.views.decorators.http import require_POST
from accounts.models import AuditLog
from .models import Course, Module, Chapter, Topic, Question, ChapterQuiz, MockTest, QuestionSet, CertificateRule, CourseComment
from decimal import Decimal
from .models import PriceProposal, PriceDiscussionMessage
from django.db.models import Q
from django.contrib.auth.decorators import login_required

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

@login_required
def question_bank(request, course_id):
    """View and add questions to the course question bank."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
    
    topics = course.topics.all().order_by('order')
    questions = course.questions.all().order_by('-id')
    
    return render(request, 'courses/question_bank.html', {
        'course': course,
        'topics': topics,
        'questions': questions
    })

@login_required
@require_POST
def add_question(request, course_id):
    """Add a new question to the bank."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
        
    topic_id = request.POST.get('topic', '').strip()
    text = request.POST.get('text', '').strip()
    option_a = request.POST.get('option_a', '').strip()
    option_b = request.POST.get('option_b', '').strip()
    option_c = request.POST.get('option_c', '').strip()
    option_d = request.POST.get('option_d', '').strip()
    correct_option = request.POST.get('correct_option', '').strip()
    explanation = request.POST.get('explanation', '').strip()
    difficulty = request.POST.get('difficulty', 'EASY')
    
    errors = []
    if not topic_id: errors.append('Topic is required.')
    if not text: errors.append('Question text is required.')
    if not option_a or not option_b or not option_c or not option_d: 
        errors.append('All 4 options are required.')
    if not correct_option or correct_option not in ['A','B','C','D']:
        errors.append('Valid correct option is required.')
        
    if errors:
        for err in errors:
            messages.error(request, err)
        return redirect('courses:question_bank', course_id=course_id)
        
    topic = Topic.objects.get(pk=topic_id, course=course)
    Question.objects.create(
        course=course, topic=topic, text=text,
        option_a=option_a, option_b=option_b, option_c=option_c, option_d=option_d,
        correct_option=correct_option, explanation=explanation, difficulty=difficulty
    )
    messages.success(request, 'Question added to the bank.')
    return redirect('courses:question_bank', course_id=course_id)

@login_required
def chapter_quiz(request, course_id, chapter_id):
    """Configure a chapter's quiz."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
        
    # Get or create the quiz
    quiz, created = ChapterQuiz.objects.get_or_create(chapter=chapter)
    
    # Get questions filtered by the chapter's topic (or all if no topic)
    if chapter.topic_tag:
        bank_questions = course.questions.filter(topic=chapter.topic_tag)
    else:
        bank_questions = course.questions.all()
        
    selected_ids = quiz.questions.values_list('id', flat=True)
    
    return render(request, 'courses/chapter_quiz.html', {
        'course': course,
        'chapter': chapter,
        'quiz': quiz,
        'bank_questions': bank_questions,
        'selected_ids': list(selected_ids)
    })

@login_required
@require_POST
def save_chapter_quiz(request, course_id, chapter_id):
    """Save the selected questions and settings for a chapter quiz."""
    course = get_object_or_404(Course, pk=course_id)
    chapter = get_object_or_404(Chapter, pk=chapter_id, module__course=course)
    
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
        
    quiz, created = ChapterQuiz.objects.get_or_create(chapter=chapter)
    
    passing_mark = request.POST.get('passing_mark', 60)
    shuffle = request.POST.get('shuffle') == 'on'
    selected_question_ids = request.POST.getlist('questions')
    
    quiz.passing_mark = passing_mark
    quiz.shuffle = shuffle
    quiz.save()
    
    # Update questions
    quiz.questions.clear()
    if selected_question_ids:
        questions = Question.objects.filter(id__in=selected_question_ids, course=course)
        quiz.questions.add(*questions)
        
    messages.success(request, f'Quiz for "{chapter.title}" saved.')
    return redirect('courses:chapter_quiz', course_id=course_id, chapter_id=chapter_id)

@login_required
def creator_courses(request):
    """List all courses created by the logged-in Content Creator."""
    if request.user.role != 'CONTENT_CREATOR':
        raise PermissionDenied
    
    courses = Course.objects.filter(author=request.user).order_by('-created_at')
    return render(request, 'courses/creator_courses.html', {'courses': courses})

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

@login_required
def creator_courses(request):
    """List all courses created by the logged-in Content Creator."""
    # Allow Admins and Content Managers to view for review, Creators to view their own
    if request.user.role not in ['CONTENT_CREATOR', 'ADMIN', 'CONTENT_MANAGER']:
        raise PermissionDenied
    
    if request.user.role == 'CONTENT_CREATOR':
        # Creators only see their own courses
        courses = Course.objects.filter(author=request.user).order_by('-created_at')
    else:
        # Admins and CMs see all courses (for review)
        courses = Course.objects.all().order_by('-created_at')
        
    return render(request, 'courses/creator_courses.html', {'courses': courses})




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
def final_mock_test(request, course_id):
    """Setup the 5 sets for the final mock test."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
        
    # Get or create the Final Mock Test object
    mock_test, created = MockTest.objects.get_or_create(
        course=course, scope='FINAL',
        defaults={'passing_mark': 70, 'time_limit_minutes': 60, 'questions_per_attempt': 20}
    )
    
    # Ensure 5 sets exist
    for i in range(1, 6):
        QuestionSet.objects.get_or_create(
            mock_test=mock_test, set_number=i,
            defaults={'title': f'Set {i}'}
        )
        
    sets = mock_test.sets.all().order_by('set_number')
    bank_questions = course.questions.all().order_by('topic__name')
    
    return render(request, 'courses/final_mock_test.html', {
        'course': course,
        'mock_test': mock_test,
        'sets': sets,
        'bank_questions': bank_questions
    })

@login_required
@require_POST
def save_mock_set(request, course_id, set_id):
    """Save questions for a specific mock test set."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user != course.author or course.status not in ['DRAFT', 'CHANGES_REQUESTED']:
        raise PermissionDenied
        
    set_obj = get_object_or_404(QuestionSet, pk=set_id, mock_test__course=course)
    selected_question_ids = request.POST.getlist('questions')
    
    set_obj.questions.clear()
    if selected_question_ids:
        questions = Question.objects.filter(id__in=selected_question_ids, course=course)
        set_obj.questions.add(*questions)
        
    messages.success(request, f'Set {set_obj.set_number} updated with {len(selected_question_ids)} questions.')
    return redirect('courses:final_mock_test', course_id=course_id)

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

@login_required
def module_mock_test(request, course_id, module_id):
    """Setup the mock test for a specific module."""
    course = get_object_or_404(Course, pk=course_id)
    module = get_object_or_404(Module, pk=module_id, course=course)
    
    if request.user != course.author and request.user.role not in ('ADMIN', 'CONTENT_MANAGER'):
        raise PermissionDenied
        
    can_edit = (request.user == course.author) and course.status in ['DRAFT', 'CHANGES_REQUESTED']
    
    # Get or create the Module Mock Test
    mock_test, created = MockTest.objects.get_or_create(
        course=course, scope='MODULE', module=module,
        defaults={'passing_mark': 60, 'time_limit_minutes': 30, 'questions_per_attempt': 10}
    )
    
    # Ensure 1 set exists (max 5 allowed, but 1 is minimum)
    QuestionSet.objects.get_or_create(mock_test=mock_test, set_number=1, defaults={'title': 'Set 1'})
        
    sets = mock_test.sets.all().order_by('set_number')
    
    # Get questions filtered by topics used in this module's chapters
    module_topics = Topic.objects.filter(chapters__module=module).distinct()
    bank_questions = course.questions.filter(topic__in=module_topics).order_by('topic__name')
    
    if request.method == 'POST' and can_edit:
        # Update settings
        mock_test.passing_mark = request.POST.get('passing_mark', 60)
        mock_test.time_limit_minutes = request.POST.get('time_limit_minutes', 30)
        mock_test.questions_per_attempt = request.POST.get('questions_per_attempt', 10)
        mock_test.save()
        messages.success(request, 'Mock test settings saved.')
        return redirect('courses:module_mock_test', course_id=course_id, module_id=module_id)
        
    return render(request, 'courses/module_mock_test.html', {
        'course': course,
        'module': module,
        'mock_test': mock_test,
        'sets': sets,
        'bank_questions': bank_questions,
        'can_edit': can_edit
    })



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
    
    is_enrolled = False
    if request.user.is_authenticated and request.user.role == 'STUDENT':
        is_enrolled = True 
    
    return render(request, 'courses/course_detail.html', {
        'course': course,
        'modules': modules,
        'total_chapters': total_chapters,
        'is_enrolled': is_enrolled
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