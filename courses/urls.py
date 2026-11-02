from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    path('my-courses/', views.creator_courses, name='creator_courses'),
    path('create/', views.create_course, name='create_course'),
    path('<uuid:course_id>/builder/', views.course_builder, name='course_builder'),
    path('<uuid:course_id>/builder/add-module/', views.add_module, name='add_module'),
    path('<uuid:course_id>/builder/<uuid:module_id>/add-chapter/', views.add_chapter, name='add_chapter'),
    path('<uuid:course_id>/builder/add-topic/', views.add_topic, name='add_topic'),
        path('<uuid:course_id>/question-bank/', views.question_bank, name='question_bank'),
    path('<uuid:course_id>/question-bank/add/', views.add_question, name='add_question'),
    path('<uuid:course_id>/builder/<uuid:chapter_id>/quiz/', views.chapter_quiz, name='chapter_quiz'),
    path('<uuid:course_id>/builder/<uuid:chapter_id>/quiz/save/', views.save_chapter_quiz, name='save_chapter_quiz'),
        path('<uuid:course_id>/settings/', views.course_settings, name='course_settings'),
    path('<uuid:course_id>/final-mock-test/', views.final_mock_test, name='final_mock_test'),
        path('<uuid:course_id>/final-mock-test/<int:set_id>/save/', views.save_mock_set, name='save_mock_set'),
    path('<uuid:course_id>/certificate-rules/', views.certificate_rules, name='certificate_rules'),
        path('<uuid:course_id>/submit/', views.submit_for_review, name='submit_for_review'),
    path('review-queue/', views.review_queue, name='review_queue'),
    path('<uuid:course_id>/review/', views.review_course, name='review_course'),
    path('<uuid:course_id>/approve/', views.approve_course, name='approve_course'),
    path('<uuid:course_id>/request-changes/', views.request_changes, name='request_changes'),
        path('<uuid:course_id>/pricing/', views.pricing_view, name='pricing_view'),
    path('<uuid:course_id>/publish/', views.publish_course, name='publish_course'),
        path('<uuid:course_id>/builder/<uuid:module_id>/mock-test/', views.module_mock_test, name='module_mock_test'),
          path('category/<slug:slug>/', views.course_catalogue, name='course_catalogue'),
              path('<uuid:course_id>/detail/', views.course_detail, name='course_detail'),
    path('<uuid:course_id>/learn/', views.course_learn, name='course_learn'),
    path('category/<slug:slug>/', views.course_catalogue, name='course_catalogue'),
]