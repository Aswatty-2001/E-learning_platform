from django.urls import path
from . import views

app_name = "categories"

urlpatterns = [
    path("manage/", views.menu_management, name="menu_management"),
    path("manage/parent/add/", views.parent_add_view, name="parent_add"),
    path("manage/sub/add/", views.sub_add_view, name="sub_add"),
    path("manage/<int:pk>/edit/", views.category_edit_view, name="category_edit"),
    path("manage/<int:pk>/toggle/", views.category_toggle, name="category_toggle"),
    path("manage/<int:pk>/move/<str:direction>/", views.category_move, name="category_move"),
    path("category/<slug:slug>/", views.category_page, name="category_page"),
    path("category/<slug:slug>/<slug:sub_slug>/", views.category_page, name="subcategory_page"),
]