from django.db.models import Q
from .models import Course, Module, Chapter, MockTest, QuestionSet, Question, CertificateRule

def check_course_readiness(course):
    missing = []
    
    if not course.thumbnail:
        missing.append("Course thumbnail is missing.")
    if not course.description or len(course.description) < 50:
        missing.append("Description is too short (min 50 chars).")
    
    modules = course.modules.all()
    if modules.count() < 1:
        missing.append("At least 1 module is required.")
        
    for module in modules:
        chapters = module.chapters.all()
        if chapters.count() < 2:
            missing.append(f"Module '{module.title}' needs at least 2 chapters.")
            
        for chapter in chapters:
            if not chapter.video_url:
                missing.append(f"Chapter '{chapter.title}' is missing a video URL.")
            if not chapter.topic_tag:
                missing.append(f"Chapter '{chapter.title}' is missing a topic tag.")
            if not hasattr(chapter, 'quiz') or chapter.quiz.questions.count() == 0:
                missing.append(f"Chapter '{chapter.title}' is missing quiz questions.")
                
        # Check Module Mock Test if it exists
        if module.mock_tests.exists():
            mock = module.mock_tests.first()
            if mock.sets.count() == 0 or mock.sets.first().questions.count() == 0:
                missing.append(f"Module '{module.title}' mock test has no questions.")
                
    # Check Final Mock Test (5 sets)
    try:
        final_test = course.mock_tests.get(scope='FINAL')
        sets = final_test.sets.all()
        if sets.count() != 5:
            missing.append(f"Final Mock Test must have exactly 5 sets (currently has {sets.count()}).")
        for s in sets:
            if s.questions.count() == 0:
                missing.append(f"Final Mock Test Set {s.set_number} has no questions.")
    except MockTest.DoesNotExist:
        missing.append("Final Mock Test is not created.")
        
    # Check Certificate Rules
    try:
        _ = course.certificate_rule
    except CertificateRule.DoesNotExist:
        missing.append("Completion and Certificate rules are not configured.")
        
    return {
        'is_ready': len(missing) == 0,
        'missing': missing
    }


def grade_attempt(attempt_answers, mock_test_questions):
    """
    attempt_answers: dict of {question_id: selected_option}
    mock_test_questions: QuerySet of Question objects
    Returns: score percentage, list of weak topics
    """
    correct_count = 0
    topic_scores = {}
    
    for q in mock_test_questions:
        selected = attempt_answers.get(str(q.id))
        if selected == q.correct_option:
            correct_count += 1
            topic_scores[q.topic.name] = topic_scores.get(q.topic.name, 0) + 1
        else:
            topic_scores[q.topic.name] = topic_scores.get(q.topic.name, 0)
            
    total_questions = mock_test_questions.count()
    score = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # Calculate weak topics (below 60%)
    weak_topics = []
    for topic, correct in topic_scores.items():
        topic_total = mock_test_questions.filter(topic__name=topic).count()
        if topic_total > 0 and (correct / topic_total) < 0.6:
            weak_topics.append(topic)
            
    return score, weak_topics

def next_set_for(student, mock_test):
    """
    Determines the next set number for the student.
    (Logic stub: needs Attempt model to track history)
    """
    # For now, return Set 1. In production, query Attempt model for last set used.
    return 1