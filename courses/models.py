import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from categories.models import Category

class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        IN_REVIEW = 'IN_REVIEW', 'In Review'
        CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes Requested'
        APPROVED = 'APPROVED', 'Approved'
        PRICE_PROPOSED = 'PRICE_PROPOSED', 'Price Proposed'
        PRICE_CONFIRMED = 'PRICE_CONFIRMED', 'Price Confirmed'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'

    class Level(models.TextChoices):
        BEGINNER = 'BEGINNER', 'Beginner'
        INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
        ADVANCED = 'ADVANCED', 'Advanced'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    description = models.TextField()
    objectives = models.TextField(blank=True, help_text="What will students learn?")
    prerequisites = models.TextField(blank=True, help_text="What should students know before starting?")
    
    thumbnail = models.ImageField(upload_to='course_thumbnails/', null=True, blank=True)
    main_category = models.ForeignKey(
        Category, on_delete=models.PROTECT, 
        related_name='main_courses', help_text="Main category"
    )
    subcategory = models.ForeignKey(
        Category, on_delete=models.PROTECT, 
        related_name='sub_courses', help_text="Subcategory assigned to the creator"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
        related_name='authored_courses'
    )
    
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)
    language = models.CharField(max_length=10, default='en')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    pricing = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Set by Admin")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class Topic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'name']

    def __str__(self):
        return f"{self.course.title} - {self.name}"

class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    requires_mock_pass = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Chapter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    video_url = models.URLField(blank=True, help_text="Link to video (YouTube/Vimeo)")
    duration_seconds = models.PositiveIntegerField(default=0)
    notes_pdf = models.FileField(upload_to='chapter_notes/', null=True, blank=True)
    
    topic_tag = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, related_name='chapters')
    is_free_preview = models.BooleanField(default=False)
    
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - {self.title}"

class Question(models.Model):
    """
    A multiple-choice question that belongs to exactly ONE of:
      * a chapter quiz       (ChapterQuiz)
      * a module mock test    (MockTest, scope=MODULE)
      * a final mock-test set (QuestionSet, belongs to the course-level FINAL MockTest)

    The previous shared course-level Question Bank has been removed. Questions
    are now created inline, directly inside the panel they belong to.
    """
    class Difficulty(models.TextChoices):
        EASY = 'EASY', 'Easy'
        MEDIUM = 'MEDIUM', 'Medium'
        HARD = 'HARD', 'Hard'

    class Usage(models.TextChoices):
        CHAPTER = 'CHAPTER', 'Chapter quiz'
        MODULE  = 'MODULE',  'Module mock test'
        FINAL   = 'FINAL',   'Final mock test set'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='questions',
        help_text="Kept for filtering / audit. The authoritative parent is the scope FK below.",
    )
    topic = models.ForeignKey(
        Topic, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='questions',
        help_text="Optional topic tag, used for analytics only.",
    )

    # ── New scoped parents — exactly ONE must be set (validated in clean()) ──
    chapter_quiz = models.ForeignKey(
        'ChapterQuiz', on_delete=models.CASCADE,
        null=True, blank=True, related_name='questions',
    )
    module_mock_test = models.ForeignKey(
        'MockTest', on_delete=models.CASCADE,
        null=True, blank=True, related_name='questions',
    )
    final_question_set = models.ForeignKey(
        'QuestionSet', on_delete=models.CASCADE,
        null=True, blank=True, related_name='questions',
    )

    usage = models.CharField(
        max_length=10, choices=Usage.choices, default=Usage.CHAPTER,
        help_text="Auto-derived from whichever scope FK is set, in save().",
    )

    text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255, blank=True, default='')
    option_d = models.CharField(max_length=255, blank=True, default='')
    correct_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    @property
    def parent(self):
        if self.chapter_quiz_id:    return self.chapter_quiz
        if self.module_mock_test_id: return self.module_mock_test
        if self.final_question_set_id: return self.final_question_set
        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        scopes = [self.chapter_quiz_id, self.module_mock_test_id, self.final_question_set_id]
        if len([s for s in scopes if s]) != 1:
            raise ValidationError("A question must belong to exactly one of: chapter quiz, module mock test, or final question set.")
        if self.chapter_quiz_id:      self.usage = self.Usage.CHAPTER
        elif self.module_mock_test_id: self.usage = self.Usage.MODULE
        elif self.final_question_set_id: self.usage = self.Usage.FINAL

    def save(self, *args, **kwargs):
        if self.chapter_quiz_id:      self.usage = self.Usage.CHAPTER
        elif self.module_mock_test_id: self.usage = self.Usage.MODULE
        elif self.final_question_set_id: self.usage = self.Usage.FINAL
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_usage_display()}] {self.text[:60]}"

class ChapterQuiz(models.Model):
    chapter = models.OneToOneField(Chapter, on_delete=models.CASCADE, related_name='quiz')
    passing_mark = models.PositiveIntegerField(default=60, help_text="Passing percentage")
    shuffle = models.BooleanField(default=True)
    # NOTE: the `questions` M2M is removed; questions now live as direct FKs on Question.
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

class MockTest(models.Model):
    class Scope(models.TextChoices):
        MODULE = 'MODULE', 'Module'
        FINAL = 'FINAL', 'Final'
    class AfterLastSet(models.TextChoices):
        RESTART = 'RESTART', 'Restart from Set 1'
        LOCK = 'LOCK', 'Lock until reset by Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='mock_tests')
    scope = models.CharField(max_length=10, choices=Scope.choices)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True, related_name='mock_tests')
    passing_mark = models.PositiveIntegerField(default=60)
    time_limit_minutes = models.PositiveIntegerField(default=60)
    questions_per_attempt = models.PositiveIntegerField(default=20)
    max_attempts_per_set = models.PositiveIntegerField(default=1)
    wait_hours_between_attempts = models.PositiveIntegerField(default=0)
    after_last_set = models.CharField(max_length=10, choices=AfterLastSet.choices, default=AfterLastSet.RESTART)

class QuestionSet(models.Model):
    mock_test = models.ForeignKey(MockTest, on_delete=models.CASCADE, related_name='sets')
    set_number = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=100, blank=True)
    # NOTE: the `questions` M2M is removed; questions now live as direct FKs on Question.
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ['mock_test', 'set_number']

class CertificateRule(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='certificate_rule')
    certificate_enabled = models.BooleanField(default=True)
    require_all_chapters_complete = models.BooleanField(default=True)
    chapter_quiz_required = models.BooleanField(default=True)
    chapter_quiz_passing_mark = models.PositiveIntegerField(default=60)
    module_mock_required = models.BooleanField(default=True)
    final_mock_passing_mark = models.PositiveIntegerField(default=70)
    max_final_attempts = models.PositiveIntegerField(null=True, blank=True, help_text="Blank means unlimited")
    certificate_title_text = models.CharField(max_length=100, default="Certificate of Completion")

class CourseComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='review_comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class PriceProposal(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='price_proposal')
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='price_proposals')
    created_at = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='confirmed_prices')
    confirmed_at = models.DateTimeField(null=True, blank=True)

class PriceDiscussionMessage(models.Model):
    proposal = models.ForeignKey(PriceProposal, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

