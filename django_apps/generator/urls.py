from django.urls import path
from . import views

app_name = "generator"

urlpatterns = [
    path("", views.index, name="index"),
    path("export/", views.export_by_subject, name="export"),
    path("exports/", views.my_exports, name="my_exports"),
    path("exports/<int:job_id>/download/", views.download_export, name="download_export"),
    path("exports/<int:job_id>/", views.export_detail, name="export_detail"),
    path("tables/", views.tables_view, name="tables"),
    path("tables/render/", views.tables_render, name="tables_render"),   # paso 3
    path("tables/export/", views.tables_export, name="tables_export"),   # paso 4
    path("tables/search/", views.tables_search, name="tables_search"),
    path("tables/selected/add/", views.tables_selected_add, name="tables_selected_add"),
    path("tables/selected/remove/", views.tables_selected_remove, name="tables_selected_remove"),
    path("curriculum/", views.curriculum_builder, name="curriculum_builder"),
    path("curriculum/plans/", views.curriculum_plans, name="curriculum_plans"),
    path("curriculum/plans/save/", views.curriculum_plan_save, name="curriculum_plan_save"),
    path("curriculum/plans/<int:plan_id>/", views.curriculum_plan_detail, name="curriculum_plan_detail"),
    path("curriculum/plans/<int:plan_id>/delete/", views.curriculum_plan_delete, name="curriculum_plan_delete"),
    path("curriculum/analyze/", views.curriculum_analyze, name="curriculum_analyze"),
    path("curriculum/codes/", views.curriculum_codes, name="curriculum_codes"),
]
