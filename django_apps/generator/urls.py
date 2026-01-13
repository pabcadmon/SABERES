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
    path("secuenciacion/", views.secuenciacion_builder, name="secuenciacion_builder"),
    path("secuenciacion/plans/", views.secuenciacion_plans, name="secuenciacion_plans"),
    path("secuenciacion/plans/save/", views.secuenciacion_plan_save, name="secuenciacion_plan_save"),
    path("secuenciacion/plans/<int:plan_id>/", views.secuenciacion_plan_detail, name="secuenciacion_plan_detail"),
    path("secuenciacion/plans/<int:plan_id>/delete/", views.secuenciacion_plan_delete, name="secuenciacion_plan_delete"),
    path("secuenciacion/analyze/", views.secuenciacion_analyze, name="secuenciacion_analyze"),
    path("secuenciacion/codes/", views.secuenciacion_codes, name="secuenciacion_codes"),
]

