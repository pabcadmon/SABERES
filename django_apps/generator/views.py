from pathlib import Path
import re
import unicodedata
from django.utils.html import escape

import json

import traceback

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.conf import settings

from core.loader import cargar_datos
from core.engine.normalize import normalize_codes, NormalizationError

from core.engine.generate import generate_from_excel

from django.contrib.auth.decorators import login_required
from django_apps.accounts.permissions import require_subject_access

from django_apps.generator.models import ExportJob, CurriculumPlan

from django.core.files.base import ContentFile
from django.utils import timezone

from django.http import FileResponse, Http404

from django.core.paginator import Paginator

from django_apps.accounts.models import Subject, UserSubjectAccess
from core.loader import cargar_datos
from core.engine.codes import build_codigos_df
from core.engine.generate import generate_from_excel
from core.engine.display import marcar_seleccion_tabla2, marcar_seleccion_tabla3

from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET

from core.engine.sort import natural_sort_key
from core.engine.generate import generate_from_excel

CODE_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑ0-9]+(?:\.[A-Za-zÁÉÍÓÚÜÑ0-9]+)+")  # tipo GEH.1.C.10

# Ajusta esto a TU fichero por defecto
DEFAULT_EXCEL = Path("data/1ESO_GeH.xlsx")
DEMO_MAX_CODES = 5
DEMO_MAX_RESULTS = 10
DEMO_MAX_RELATIONS = 3
DEMO_MAX_CODES_PER_TYPE = 5

def _get_demo_subject():
    return (
        Subject.objects.filter(code__iexact="LYL_1ESO", is_active=True).first()
        or Subject.objects.filter(name__icontains="lyl", is_active=True).first()
        or Subject.objects.filter(name__icontains="lengua", is_active=True).first()
    )

def _is_demo_user(user) -> bool:
    if not user or not user.is_authenticated:
        return True
    return not UserSubjectAccess.objects.filter(user=user).exists()

def _resolve_subject(user, subject_id):
    if user and user.is_authenticated:
        subjects_qs = (
            Subject.objects
            .filter(usersubjectaccess__user=user, is_active=True)
            .distinct()
        )
        subject = subjects_qs.filter(id=subject_id).first() if subject_id else None
    else:
        subjects_qs = Subject.objects.none()
        subject = None
    demo_mode = False
    demo_subject = None
    if subject is None and _is_demo_user(user):
        demo_subject = _get_demo_subject()
        if demo_subject and str(demo_subject.id) == str(subject_id):
            subject = demo_subject
            demo_mode = True
    elif subject is not None:
        demo_mode = False
    return subject, demo_mode, demo_subject

def _prune_export_jobs(user, keep: int = 15):
    keep_ids = list(
        ExportJob.objects
        .filter(user=user, status=ExportJob.Status.SUCCESS)
        .order_by("-created_at")
        .values_list("id", flat=True)[:keep]
    )
    if keep_ids:
        ExportJob.objects.filter(user=user).exclude(id__in=keep_ids).delete()

def _get_subjects_for_user(user):
    accesses = user.usersubjectaccess_set.select_related("subject").all()
    return [a.subject for a in accesses]

def _normalize_colname(name: str) -> str:
    base = unicodedata.normalize("NFKD", str(name or ""))
    ascii_name = base.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())

def _sort_df_by_codigo_natural(dfx):
    if dfx is None or dfx.empty:
        return dfx
    code_col = None
    for col in dfx.columns:
        key = _normalize_colname(col)
        if "codigo" in key or key == "code":
            code_col = col
            break
    if not code_col:
        return dfx
    return dfx.sort_values(code_col, key=lambda s: s.map(natural_sort_key))
def _get_demo_allowed_codes(df, max_per_type: int):
    if df is None or df.empty:
        return set()
    def _find_col(candidates):
        for col in df.columns:
            key = _normalize_colname(col)
            for cand in candidates:
                if cand in key:
                    return col
        return None
    code_col = _find_col(["codigo", "code"])
    type_col = _find_col(["tipo", "type"])
    if not code_col or not type_col:
        return set()
    df_sorted = _sort_df_by_codigo_natural(df)
    allowed = set()
    for t in ("SSBB", "CE", "CEv", "DO"):
        subset = df_sorted[df_sorted[type_col] == t]
        count = 0
        for code in subset[code_col].astype(str).tolist():
            code_norm = _normalize_code(code)
            if not code_norm:
                continue
            allowed.add(code_norm)
            count += 1
            if count >= max_per_type:
                break
    return allowed

def _apply_demo_description_lock(df, demo_allowed: set):
    if df is None or df.empty:
        return df
    code_col = None
    desc_col = None
    for col in df.columns:
        key = _normalize_colname(col)
        if code_col is None and ("codigo" in key or key == "code" or "elemento" in key):
            code_col = col
        if desc_col is None and ("descripcion" in key or key.startswith("desc") or "etiqueta" in key or "label" in key):
            desc_col = col
    if not code_col or not desc_col:
        return df
    out = df.copy()
    for idx, row in out.iterrows():
        code = _normalize_code(row.get(code_col))
        if code and code not in demo_allowed:
            out.at[idx, desc_col] = "NO DISPONIBLE EN VERSIÓN DEMO"
    return out

def home(request):
    return render(request, "home.html")


def index(request):
    if request.method == "GET":
        return render(request, "generator/index.html", {"default_excel": str(DEFAULT_EXCEL)})

    # POST
    excel_path = request.POST.get("excel_path", str(DEFAULT_EXCEL)).strip()
    codes_raw = request.POST.get("codes", "").strip()

    if not codes_raw:
        return HttpResponseBadRequest("No has indicado códigos.")

    # Permite separar por coma, espacio o salto de línea
    # Ej: "CE1, A.1\n1.2" -> ["CE1","A.1","1.2"]
    tokens = []
    for part in codes_raw.replace("\n", " ").replace(",", " ").split(" "):
        t = part.strip()
        if t:
            tokens.append(t)

    if not tokens:
        return HttpResponseBadRequest("No has indicado códigos válidos.")

    # Llama al motor
    data = cargar_datos(excel_path)
    try:
        tokens = normalize_codes(tokens, data)
    except NormalizationError as e:
        return HttpResponseBadRequest(str(e))
    res = generate_from_excel(excel_path, tokens)

    filename = "relaciones_curriculares.xlsx"
    response = HttpResponse(
        res.excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@login_required
def export_by_subject(request):
    # SIEMPRE disponible (GET y POST)
    accesses = request.user.usersubjectaccess_set.select_related("subject").all()
    subjects = [a.subject for a in accesses]

    if request.method == "GET":
        return render(request, "generator/export.html", {"subjects": subjects})

    subject_code = (request.POST.get("subject_code") or "").strip()
    codes_raw = (request.POST.get("codes") or "").strip()

    job = None  # lo creamos cuando tengamos subject válido

    def render_error(message: str, status: int = 400):
        nonlocal job
        if job is not None:
            job.error_message = message
            job.save(update_fields=["error_message"])

        return render(
            request,
            "generator/export.html",
            {
                "subjects": subjects,
                "error_message": message,
                "selected_subject_code": subject_code,
                "codes_raw": codes_raw,
            },
            status=status,
        )

    try:
        if not subject_code:
            return render_error("Falta asignatura (subject_code).")

        if not codes_raw:
            return render_error("No has indicado códigos.")

        # Permiso + subject (ya con subject_code validado)
        subject = require_subject_access(request.user, subject_code)

        if not subject.dataset_path:
            return render_error("Esta asignatura no tiene dataset configurado.")

        # Crear el job ya con FK correcta
        job = ExportJob.objects.create(
            user=request.user,
            subject=subject,
            codes_raw=codes_raw,
            status=ExportJob.Status.FAILED,
            error_message="",
        )

        excel_path = str(Path(settings.BASE_DIR) / subject.dataset_path)

        # Parsear códigos
        tokens = []
        for part in codes_raw.replace("\n", " ").replace(",", " ").split(" "):
            t = part.strip()
            if t:
                tokens.append(t)

        if not tokens:
            return render_error("No has indicado códigos válidos.")

        # Core
        data = cargar_datos(excel_path)
        tokens = normalize_codes(tokens, data)

        res = generate_from_excel(excel_path, tokens)

        # Guardar archivo
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{subject_code}_{request.user.username}_{timestamp}.xlsx"
        job.output_file.save(stored_filename, ContentFile(res.excel_bytes), save=False)

        job.status = ExportJob.Status.SUCCESS
        job.error_message = ""
        job.save()
        _prune_export_jobs(request.user)

        # Descarga inmediata
        download_filename = f"relaciones_{subject_code}.xlsx"
        response = HttpResponse(
            res.excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{download_filename}"'
        return response

    except NormalizationError as e:
        return render_error(str(e))

    except Exception as e:
        return render_error(str(e))


@login_required
def my_exports(request):
    qs = (
        ExportJob.objects
        .select_related("subject")
        .filter(user=request.user, status=ExportJob.Status.SUCCESS)
        .order_by("-created_at")
    )

    subject_code = (request.GET.get("subject") or "").strip()
    if subject_code:
        qs = qs.filter(subject__code=subject_code)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # para el dropdown de subjects
    subjects = [a.subject for a in request.user.usersubjectaccess_set.select_related("subject").all()]

    return render(
        request,
        "generator/my_exports.html",
        {
            "page_obj": page_obj,
            "subjects": subjects,
            "selected_subject": subject_code,
            "selected_status": "",
        },
    )

@login_required
def download_export(request, job_id: int):
    try:
        job = ExportJob.objects.get(id=job_id, user=request.user)
    except ExportJob.DoesNotExist:
        raise Http404("No existe")

    if job.status != "SUCCESS" or not job.output_file:
        raise Http404("No disponible")

    return FileResponse(
        job.output_file.open("rb"),
        as_attachment=True,
        filename=job.output_file.name.split("/")[-1],
    )

def tables_view(request):
    # Subjects accesibles: si ya tienes helper/manager, úsalo.
    # Aquí asumo UserSubjectAccess. Ajusta al tuyo.
    if request.user.is_authenticated:
        subjects = (
            Subject.objects
            .filter(usersubjectaccess__user=request.user, is_active=True)
            .order_by("name")
            .distinct()
        )
    else:
        subjects = Subject.objects.none()
    demo_mode = False
    demo_subject = None
    if not subjects.exists() and _is_demo_user(request.user):
        demo_subject = _get_demo_subject()
        if demo_subject:
            subjects = Subject.objects.filter(id=demo_subject.id)
            demo_mode = True

    # Selección por querystring ?subject=<id> (opcional pero útil)
    selected_subject_id = request.GET.get("subject") or ""
    selected_subject = None
    if selected_subject_id:
        selected_subject = subjects.filter(id=selected_subject_id).first()
    if not selected_subject and demo_mode and demo_subject:
        selected_subject = demo_subject

    ctx = {
        "subjects": subjects,
        "selected_subject": selected_subject,
        "demo_mode": demo_mode,
        "demo_subject_id": demo_subject.id if demo_subject else "",
        # defaults de filtros tipo (como Streamlit: todos True)
        "mostrar_ssbb": True,
        "mostrar_ce": True,
        "mostrar_cev": True,
        "mostrar_do": True,
        # seleccionados iniciales vacíos
        "selected_codes": [],
        "options": [],
        "has_subject": False,
        "has_selection": False,
    }
    return render(request, "generator/tables.html", ctx)

@login_required
def export_detail(request, job_id: int):
    return HttpResponse("export_detail pendiente", content_type="text/plain")

def _parse_bool_checkbox(post, name: str) -> bool:
    # En HTML, si el checkbox no está marcado, no viene en POST
    return name in post


def _df_to_ctx(df):
    df2 = df.fillna("")
    headers = [str(c) for c in df2.columns.tolist()]
    rows = df2.astype(str).values.tolist()
    return {"headers": headers, "rows": rows}


@require_POST
def tables_render(request):
    subject_id = (request.POST.get("subject_id") or "").strip()
    only_table2 = (request.POST.get("only_table2") or "").strip() == "1"
    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)

    selected_codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]
    selected_set = set([_normalize_code(c) for c in selected_codes])
    if demo_mode and len(selected_codes) > DEMO_MAX_CODES:
        selected_codes = selected_codes[:DEMO_MAX_CODES]

    has_subject = subject is not None

    # ✅ Si no hay asignatura, no renderizamos nada (evita None.dataset_path)
    if not has_subject:
        return render(request, "generator/_tables_tables.html", {
            "has_subject": False,
            "table1": None,
            "table2_ssbb": None,
            "table2_ce": None,
            "table2_cev": None,
            "table2_do": None,
            "table3": None,
            "error": None,
            "only_table2": only_table2,
            "demo_mode": demo_mode,
            "selected_codes": selected_codes,
        })

    # ✅ Si hay asignatura pero aún no hay códigos, mostrar “elige códigos”
    if not selected_codes:
        return render(request, "generator/_tables_tables.html", {
            "has_subject": True,
            "table1": None,
            "table2_ssbb": None,
            "table2_ce": None,
            "table2_cev": None,
            "table2_do": None,            "table3": None,
            "error": None,
            "only_table2": only_table2,
            "demo_mode": demo_mode,
            "selected_codes": selected_codes,
        })

    data = cargar_datos(subject.dataset_path)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

    code_to_type = {}
    for c, t in zip(codigos_df["Código"].astype(str), codigos_df["Tipo"].astype(str)):
        code_to_type[str(c).strip().rstrip(".")] = str(t).strip()

    demo_allowed = _get_demo_allowed_codes(codigos_df, DEMO_MAX_CODES_PER_TYPE) if demo_mode else None
    has_selection = has_subject and bool(selected_codes)

    table1 = table2_ssbb = table2_ce = table2_cev = table2_do = table3 = None
    error = None

    res = None
    if has_selection:
        try:
            res = generate_from_excel(
                subject.dataset_path,
                selected_codes,
                build_excel=False,
            )

            tabla2_ssbb_display = marcar_seleccion_tabla2(res.tabla2_ssbb, selected_codes)
            tabla2_ce_display = marcar_seleccion_tabla2(res.tabla2_ce, selected_codes)
            tabla2_cev_display = marcar_seleccion_tabla2(res.tabla2_cev, selected_codes)
            tabla2_do_display = marcar_seleccion_tabla2(res.tabla2_do, selected_codes)
            tabla3_display = marcar_seleccion_tabla3(res.tabla3, selected_codes)
            if demo_mode and demo_allowed is not None:
                tabla3_display = _apply_demo_description_lock(tabla3_display, demo_allowed)

            t1 = _decorate_df_codes(res.tabla1, code_to_type, selected_codes, demo_allowed)
            t2_ssbb_src = tabla2_ssbb_display
            t2_ce_src = tabla2_ce_display
            t2_cev_src = tabla2_cev_display
            t2_do_src = tabla2_do_display
            if demo_mode:
                t2_ssbb_src = _trim_relation_df(t2_ssbb_src, DEMO_MAX_RELATIONS)
                t2_cev_src = _trim_relation_df(t2_cev_src, DEMO_MAX_RELATIONS)
            t2_ssbb = _decorate_df_codes(t2_ssbb_src, code_to_type, selected_codes, demo_allowed)
            t2_ce = _decorate_df_codes(t2_ce_src, code_to_type, selected_codes, demo_allowed)
            t2_cev = _decorate_df_codes(t2_cev_src, code_to_type, selected_codes, demo_allowed)
            t2_do = _decorate_df_codes(t2_do_src, code_to_type, selected_codes, demo_allowed)
            t3 = _decorate_df_codes(tabla3_display, code_to_type, selected_codes, demo_allowed)

            t1 = t1.rename(columns=lambda c: str(c).replace(" relacionados", ""))

            table1 = _df_to_ctx(t1)
            try:
                table1["tipo_idx"] = table1["headers"].index("Tipo")
            except ValueError:
                table1["tipo_idx"] = -1
            if only_table2:
                for df in (t2_ssbb, t2_cev):
                    drop_cols = [c for c in ["CE", "DO"] if c in df.columns]
                    if drop_cols:
                        df.drop(columns=drop_cols, inplace=True)

            table2_ssbb = _df_to_ctx(t2_ssbb)
            table2_ce = _df_to_ctx(t2_ce)
            table2_cev = _df_to_ctx(t2_cev)
            table2_do = _df_to_ctx(t2_do)
            cols_to_hide = [c for c in ["Tipo", "orden", "Orden"] if c in t3.columns]
            t3 = t3.drop(columns=cols_to_hide)

            table3 = _df_to_ctx(t3)

        except Exception as e:
            error = repr(e)

    if only_table2:
        table2_ce = None
        table2_do = None
        table2_selected = {
            "headers": ["Elemento selec.", "Relacionados"],
            "rows": [],
        }
        if has_selection and res is not None:
            rows = []
            max_related = DEMO_MAX_RELATIONS if demo_mode else None
            rows.extend(_build_selected_relations_table(res.tabla2_ssbb, selected_codes, code_to_type, "SSBB", max_related, demo_allowed)["rows"])
            rows.extend(_build_selected_relations_table(res.tabla2_cev, selected_codes, code_to_type, "CEv", max_related, demo_allowed)["rows"])
            table2_selected["rows"] = rows
    else:
        table2_selected = None

    ctx = {
        "has_subject": has_subject,
        "has_selection": has_selection,
        "table1": table1,
        "table2_ssbb": table2_ssbb,
        "table2_ce": table2_ce,
        "table2_cev": table2_cev,
        "table2_do": table2_do,
        "table2_selected": table2_selected,
        "table3": table3,
        "error": error,
        "only_table2": only_table2,
        "demo_mode": demo_mode,
        "selected_codes": selected_codes,
    }

    return render(request, "generator/_tables_tables.html", ctx)


def tables_export(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    subject_id = request.POST.get("subject_id") or ""
    codes = request.POST.getlist("codes")

    if not subject_id or not codes:
        return HttpResponse("Faltan asignatura o códigos.", status=400)

    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)
    if subject is None:
        return HttpResponse("Asignatura no válida.", status=400)

    if demo_mode:
        return HttpResponse("Disponible con acceso. Envía un email a pabcadmon@gmail.com para más información.", status=403)

    job = ExportJob.objects.create(
        user=request.user,
        subject=subject,
        status="PENDING",
        codes_raw="\n".join(codes),
    )

    try:
        # ⚠️ IMPORTANTÍSIMO: dataset_path suele ser relativo ("data/GEH.xlsx").
        # Asegura ruta absoluta:
        dataset_path = subject.dataset_path
        if not dataset_path:
            raise RuntimeError("Subject.dataset_path está vacío.")

        if not dataset_path.startswith("/"):
            dataset_path = str(settings.BASE_DIR / dataset_path)

        result = generate_from_excel(dataset_path, codes)  # si aquí revienta, lo veremos

        excel_bytes = getattr(result, "excel_bytes", None)
        if not excel_bytes:
            raise RuntimeError("generate() no devolvió excel_bytes (vacío o None).")

        filename = f"export_{subject.code}_{timezone.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

        job.output_file.save(filename, ContentFile(excel_bytes), save=False)
        job.status = "SUCCESS"
        job.error_message = ""
        job.save()
        _prune_export_jobs(request.user)

        resp = HttpResponse(
            excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    except Exception:
        tb = traceback.format_exc()
        print(tb)  # <-- verás el error real en consola

        job.status = "FAILED"
        job.error_message = tb[:8000]  # evita reventar por tamaño
        job.save()

        # en dev, mejor devolver el traceback para arreglar rápido
        if getattr(settings, "DEBUG", False):
            return HttpResponse(tb, status=500, content_type="text/plain")

        return HttpResponse("Error generando el Excel.", status=500)

@require_POST
def tables_search(request):
    subject_id = (request.POST.get("subject_id") or "").strip()
    q = (request.POST.get("q") or "").strip()
    mode = (request.POST.get("mode") or "").strip()

    selected_codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]
    selected_set = set([_normalize_code(c) for c in selected_codes])
    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)
    has_subject = subject is not None
    if demo_mode and len(selected_codes) > DEMO_MAX_CODES:
        selected_codes = selected_codes[:DEMO_MAX_CODES]

    groups = {"SSBB": [], "CE": [], "CEv": [], "DO": []}
    groups_cols = {"SSBB": [], "CE": [], "CEv": [], "DO": []}

    if has_subject:
        data = cargar_datos(subject.dataset_path)
        df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

        cod = df["Código"].astype(str)
        lab = df["Etiqueta"].astype(str)

        out = []
        max_results = None if demo_mode else 50
        demo_allowed = _get_demo_allowed_codes(df, DEMO_MAX_CODES_PER_TYPE) if demo_mode else None

        if q:
            q_low = q.lower()

            starts = df[cod.str.lower().str.startswith(q_low)]
            contains = df[~cod.str.lower().str.startswith(q_low) & cod.str.lower().str.contains(q_low)]
            label_contains = df[
                ~cod.str.lower().str.contains(q_low) &
                lab.str.lower().str.contains(q_low)
            ]

            starts = _sort_df_by_codigo_natural(starts)
            contains = _sort_df_by_codigo_natural(contains)
            label_contains = _sort_df_by_codigo_natural(label_contains)

            for part in (starts, contains, label_contains):
                for _, row in part.iterrows():
                    out.append({
                        "code": str(row["Código"]),
                        "label": str(row["Etiqueta"]),
                        "tipo": str(row["Tipo"]),
                    })
                    if max_results is not None and len(out) >= max_results:
                        break
                if max_results is not None and len(out) >= max_results:
                    break

        else:
            # 🔥 NUEVO: sin query -> mostrar TODO (o un máximo alto)
            df_all = _sort_df_by_codigo_natural(df)
            print(df_all)

            # si quieres "todo todo", quita el límite o súbelo
            MAX_ALL = None if demo_mode else 500  # recomendado para no matar el render si hay miles
            for _, row in df_all.iterrows():
                out.append({
                    "code": str(row["Código"]),
                    "label": str(row["Etiqueta"]),
                    "tipo": str(row["Tipo"]),
                })
                if MAX_ALL is not None and len(out) >= MAX_ALL:
                    break

        # agrupar por tipo
        for item in out:
            t = item.get("tipo")
            if t in groups:
                groups[t].append(item)

        if demo_mode and demo_allowed is not None:
            for items in groups.values():
                for item in items:
                    code_norm = _normalize_code(item.get("code"))
                    item["demo_disabled"] = code_norm not in demo_allowed and code_norm not in selected_set

        MAX_COLS = 3
        groups_cols = {
            "SSBB": _chunk_list_even(groups["SSBB"], MAX_COLS),
            "CE": _chunk_list_even(groups["CE"], MAX_COLS),
            "CEv": _chunk_list_even(groups["CEv"], MAX_COLS),
            "DO": _chunk_list_even(groups["DO"], MAX_COLS),
        }

    ctx = {
        "has_subject": has_subject,
        "q": q,
        "mode": mode,
        "groups_cols": groups_cols,
        "selected_codes": selected_codes,
        "is_full_list": has_subject and not q,   # opcional para el template
        "max_all": DEMO_MAX_RESULTS if demo_mode else 500,  # opcional
        "demo_mode": demo_mode,
    }
    return render(request, "generator/_code_results.html", ctx)


def _chunk_list(items, chunk_size: int):
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def _chunk_list_even(items, max_cols: int):
    if not items:
        return []
    cols = min(max_cols, len(items))
    per_col = (len(items) + cols - 1) // cols
    return _chunk_list(items, per_col)

@require_POST
def tables_selected_add(request):
    code = (request.POST.get("code") or "").strip()
    codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

    subject_id = (request.POST.get("subject_id") or "").strip()
    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)

    if demo_mode and subject and code and code not in codes:
        data = cargar_datos(subject.dataset_path)
        df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)
        allowed = _get_demo_allowed_codes(df, DEMO_MAX_CODES_PER_TYPE)
        if _normalize_code(code) not in allowed:
            response = render(request, "generator/_selected_codes.html", {"selected_codes": codes})
            response["HX-Trigger-After-Settle"] = "codesChanged"
            return response

    if demo_mode and code and code not in codes and len(codes) >= DEMO_MAX_CODES:
        response = render(request, "generator/_selected_codes.html", {"selected_codes": codes})
        response["HX-Trigger"] = json.dumps({
            "demoLimitReached": "VERSIÓN DEMO - Límite de 5 códigos simultáneos. Envía un email a pabcadmon@gmail.com para más información."
        })
        response["HX-Trigger-After-Settle"] = "codesChanged"
        return response

    if code and code not in codes:
        codes.append(code)

    response = render(request, "generator/_selected_codes.html", {"selected_codes": codes})
    response["HX-Trigger-After-Settle"] = "codesChanged"
    return response


@require_POST
def tables_selected_remove(request):
    code = (request.POST.get("code") or "").strip()
    codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

    codes = [c for c in codes if c != code]

    response = render(request, "generator/_selected_codes.html", {"selected_codes": codes})
    response["HX-Trigger-After-Settle"] = "codesChanged"
    return response

CODE_TOKEN_RE = re.compile(r"^»?(?P<code>[A-Za-zÁÉÍÓÚÜÑ0-9]+(?:\.[A-Za-zÁÉÍÓÚÜÑ0-9]+)*)«?$")

def _type_to_css(t: str) -> str:
    t = (t or "").strip()
    if t == "SSBB": return "type-ssbb"
    if t == "DO":   return "type-do"
    if t == "CE":   return "type-ce"
    if t == "CEv":  return "type-cev"
    return ""

def _decorate_cell(value, code_to_type: dict, selected_set: set, demo_allowed: set | None = None) -> str:
    """
    Convierte celdas tipo:
      "GEH.1.C.1, GEH.1.C.10"
      "»GEH.1.C.1«, GEH.1.C.2"
      "1, 2, 3"
    en pills con texto "TIPO | CODE".
    Si la celda no parece lista de códigos, la devuelve escapada sin tocar.
    """
    if value is None:
        return ""

    s = str(value).strip()
    if s == "":
        return ""

    # Heurística: si hay comas o marcadores »«, tratamos como lista de tokens
    looks_like_list = ("," in s) or ("»" in s) or ("«" in s)

    parts = [p.strip() for p in s.split(",")] if looks_like_list else [s]

    out = []
    touched = False

    for p in parts:
        if p == "":
            continue

        m = CODE_TOKEN_RE.match(p)
        if not m:
            # no es token de código -> dejamos texto normal
            out.append(escape(p))
            continue

        raw_code = m.group("code")
        code = raw_code.strip().rstrip(".")
        tipo = (code_to_type.get(code) or "").strip()

        if not tipo:
            # No sabemos el tipo -> lo dejamos como texto normal (pero escapado)
            out.append(escape(p))
            continue

        touched = True
        cls = _type_to_css(tipo)
        sel = " is-selected" if code in selected_set else ""
        demo_disabled = demo_allowed is not None and code not in demo_allowed and code not in selected_set
        disabled_cls = " is-disabled" if demo_disabled else ""
        label = f"{code}"
        title = "Disponible con acceso. Envía un email a pabcadmon@gmail.com para más información." if demo_disabled else ("Quitar" if code in selected_set else "Añadir")
        data_disabled = ' data-disabled="1"' if demo_disabled else ""
        out.append(
            f'<span class="code-tag {cls}{sel}{disabled_cls}" data-code="{escape(label)}" title="{title}"{data_disabled}>{escape(label)}</span>'
        )

    # Si no hemos “tocado” nada y era una celda normal, devolvemos escapado original
    if not touched and not looks_like_list:
        return escape(s)

    # Si era lista, los separamos con espacio como antes
    rendered = " ".join(out)
    if looks_like_list:
        return f'<div class="code-tag-list">{rendered}</div>'
    return rendered

def _decorate_df_codes(df, code_to_type: dict, selected_codes: list[str], demo_allowed: set | None = None):
    selected_set = set([c.strip().rstrip(".") for c in selected_codes])
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].apply(lambda v: _decorate_cell(v, code_to_type, selected_set, demo_allowed))
    return out

def _normalize_code(value: str) -> str:
    return str(value or "").strip().rstrip(".")

def _normalize_related_list(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    # If it's a whitespace-separated list of codes, convert to comma-separated
    if re.fullmatch(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+(?:\s+[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+)+", s):
        return ", ".join(s.split())
    return s

def _find_relation_columns(df, primary_type: str):
    cols = [str(c) for c in df.columns]
    lower = [c.lower() for c in cols]
    if primary_type == "SSBB":
        primary_idx = next((i for i, c in enumerate(lower) if "ssbb" in c or c == "sb"), None)
        related_idx = next((i for i, c in enumerate(lower) if "cev" in c), None)
    else:
        primary_idx = next((i for i, c in enumerate(lower) if "cev" in c), None)
        related_idx = next((i for i, c in enumerate(lower) if "ssbb" in c or c == "sb"), None)
    if primary_idx is None or related_idx is None:
        return None, None
    return cols[primary_idx], cols[related_idx]

def _build_selected_relations_table(df, selected_codes, code_to_type: dict, primary_type: str, max_related: int | None = None, demo_allowed: set | None = None):
    primary_col, related_col = _find_relation_columns(df, primary_type)
    if primary_col is None or related_col is None:
        return {"headers": ["Elemento selec.", "Relacionados"], "rows": []}

    rel_map = {}
    for _, row in df.iterrows():
        primary = _normalize_code(row.get(primary_col))
        if not primary:
            continue
        related = _normalize_related_list(row.get(related_col))
        if primary in rel_map and related:
            rel_map[primary] = f"{rel_map[primary]}, {related}"
        elif related:
            rel_map[primary] = related
        else:
            rel_map.setdefault(primary, "")

    selected_set = set([_normalize_code(c) for c in selected_codes])
    rows = []
    for code in selected_codes:
        code_norm = _normalize_code(code)
        if not code_norm:
            continue
        if code_to_type.get(code_norm) != primary_type:
            continue
        related = rel_map.get(code_norm, "")
        if max_related is not None and related:
            related_codes = re.findall(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+", related)
            if len(related_codes) > max_related:
                related = ", ".join(related_codes[:max_related])
        left = _decorate_cell(code_norm, code_to_type, selected_set, demo_allowed)
        right = _decorate_cell(related, code_to_type, selected_set, demo_allowed)
        rows.append([left, right])

    return {"headers": ["Elemento selec.", "Relacionados"], "rows": rows}

def _trim_relation_df(df, max_items: int):
    out = df.copy()
    def trim_cell(value):
        s = str(value or "").strip()
        if not s:
            return s
        codes = re.findall(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+", s)
        if len(codes) <= max_items:
            return s
        return ", ".join(codes[:max_items])
    for col in out.columns:
        out[col] = out[col].apply(trim_cell)
    return out

def curriculum_builder(request):
    if request.user.is_authenticated:
        subjects = (
            Subject.objects
            .filter(usersubjectaccess__user=request.user, is_active=True)
            .order_by("name")
            .distinct()
        )
    else:
        subjects = Subject.objects.none()
    demo_mode = False
    demo_subject = None
    if not subjects.exists() and _is_demo_user(request.user):
        demo_subject = _get_demo_subject()
        if demo_subject:
            subjects = Subject.objects.filter(id=demo_subject.id)
            demo_mode = True
    return render(
        request,
        "curriculum/builder/builder.html",
        {
            "subjects": subjects,
            "demo_mode": demo_mode,
            "demo_subject_id": demo_subject.id if demo_subject else "",
        },
    )


@login_required
@require_GET
def curriculum_plans(request):
    subject_id = (request.GET.get("subject_id") or "").strip()
    if not subject_id:
        return JsonResponse({"ok": False, "error": "Falta subject_id."}, status=400)

    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)
    if subject is None:
        return JsonResponse({"ok": False, "error": "Asignatura no válida o sin acceso."}, status=404)

    if demo_mode:
        return JsonResponse({"ok": True, "items": []})

    items = []
    for plan in CurriculumPlan.objects.filter(user=request.user, subject=subject).order_by("-updated_at"):
        items.append({
            "id": plan.id,
            "name": plan.name,
            "updated_at": plan.updated_at.isoformat(),
        })

    return JsonResponse({"ok": True, "items": items})


@login_required
@require_GET
def curriculum_plan_detail(request, plan_id: int):
    try:
        plan = CurriculumPlan.objects.get(id=plan_id, user=request.user)
    except CurriculumPlan.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Curriculum no encontrado."}, status=404)

    return JsonResponse({
        "ok": True,
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "subject_id": plan.subject_id,
            "units": plan.units or [],
        },
    })


@login_required
@require_POST
def curriculum_plan_save(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    subject_id = payload.get("subject_id")
    name = (payload.get("name") or "").strip() or "Curriculum"
    units = payload.get("units") or []
    plan_id = payload.get("id")

    if not subject_id:
        return JsonResponse({"ok": False, "error": "Falta subject_id."}, status=400)

    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)
    if subject is None:
        return JsonResponse({"ok": False, "error": "Asignatura no válida o sin acceso."}, status=404)

    if demo_mode:
        return JsonResponse({"ok": True, "id": plan_id or "demo", "name": name})

    if plan_id:
        try:
            plan = CurriculumPlan.objects.get(id=plan_id, user=request.user)
        except CurriculumPlan.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Curriculum no encontrado."}, status=404)
        plan.name = name
        plan.units = units
        plan.subject = subject
        plan.save(update_fields=["name", "units", "subject", "updated_at"])
    else:
        plan = CurriculumPlan.objects.create(
            user=request.user,
            subject=subject,
            name=name,
            units=units,
        )

    return JsonResponse({"ok": True, "id": plan.id, "name": plan.name})


@login_required
@require_POST
def curriculum_plan_delete(request, plan_id: int):
    try:
        plan = CurriculumPlan.objects.get(id=plan_id, user=request.user)
    except CurriculumPlan.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Curriculum no encontrado."}, status=404)

    plan.delete()
    return JsonResponse({"ok": True})


@require_POST
def curriculum_analyze(request):
    """
    Espera JSON:
    {
      "subject_id": 123,
      "units": [
        {"name": "UD1", "ssbb": ["..."], "cev": ["..."]},
        ...
      ]
    }
    Devuelve:
    {
      "missing_ssbb": [{"code": "...", "label": "..."}],
      "missing_cev":  [{"code": "...", "label": "..."}],
      "totals": {...}
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    subject_id = payload.get("subject_id")
    units = payload.get("units") or []

    if not subject_id:
        return JsonResponse({"ok": False, "error": "Falta subject_id."}, status=400)

    # ✅ Seguridad: asignatura válida + acceso del usuario (como tables_search / tables_view)
    subject, demo_mode, demo_subject = _resolve_subject(request.user, subject_id)
    if subject is None:
        return JsonResponse({"ok": False, "error": "Asignatura no válida o sin acceso."}, status=404)

    # 1) Universo desde Excel: todos los SSBB y CEv de esa asignatura
    data = cargar_datos(subject.dataset_path)
    df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

    # Normaliza a strings seguros
    df["Código"] = df["Código"].astype(str)
    df["Etiqueta"] = df["Etiqueta"].astype(str)
    df["Tipo"] = df["Tipo"].astype(str)

    # Solo SSBB y CEv
    df_ssbb = df[df["Tipo"] == "SSBB"]
    df_cev = df[df["Tipo"] == "CEv"]

    # Mapa code -> label
    all_ssbb = {}
    for _, row in df_ssbb.iterrows():
        code = str(row["Código"]).strip().rstrip(".")
        all_ssbb[code] = str(row["Etiqueta"])

    all_cev = {}
    for _, row in df_cev.iterrows():
        code = str(row["Código"]).strip().rstrip(".")
        all_cev[code] = str(row["Etiqueta"])

    # 2) Lo usado por el usuario (repartido entre unidades)
    used_ssbb_counts = {}
    used_cev_counts = {}

    for u in units:
        for x in (u.get("ssbb") or []):
            if isinstance(x, str):
                v = x.strip().rstrip(".")
                if v != "":
                    used_ssbb_counts[v] = used_ssbb_counts.get(v, 0) + 1

        for x in (u.get("cev") or []):
            if isinstance(x, str):
                v = x.strip().rstrip(".")
                if v != "":
                    used_cev_counts[v] = used_cev_counts.get(v, 0) + 1

    # 3) Missing
    missing_ssbb_codes = [c for c in all_ssbb.keys() if c not in used_ssbb_counts]
    missing_cev_codes = [c for c in all_cev.keys() if c not in used_cev_counts]

    # Orden natural (reusa tu helper)
    missing_ssbb_codes = sorted(missing_ssbb_codes, key=natural_sort_key)
    missing_cev_codes = sorted(missing_cev_codes, key=natural_sort_key)

    missing_ssbb = [{"code": c, "label": all_ssbb.get(c, "")} for c in missing_ssbb_codes]
    missing_cev = [{"code": c, "label": all_cev.get(c, "")} for c in missing_cev_codes]
    used_ssbb_list = [
        {"code": c, "label": all_ssbb.get(c, ""), "count": used_ssbb_counts[c]}
        for c in used_ssbb_counts
    ]
    used_cev_list = [
        {"code": c, "label": all_cev.get(c, ""), "count": used_cev_counts[c]}
        for c in used_cev_counts
    ]

    return JsonResponse(
        {
            "ok": True,
            "missing_ssbb": missing_ssbb,
            "missing_cev": missing_cev,
            "used_ssbb": used_ssbb_list,
            "used_cev": used_cev_list,
            "totals": {
                "all_ssbb": len(all_ssbb),
                "all_cev": len(all_cev),
                "used_ssbb": len(used_ssbb_counts),
                "used_cev": len(used_cev_counts),
                "units": len(units),
            },
            "subject": {"id": subject.id, "name": subject.name},
        }
    )


@login_required
@require_GET
def curriculum_codes(request):
    subject_id = (request.GET.get("subject_id") or "").strip()
    if not subject_id:
        return JsonResponse({"ok": False, "error": "Falta subject_id."}, status=400)

    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject = subjects_qs.filter(id=subject_id).first()
    if subject is None:
        return JsonResponse({"ok": False, "error": "Asignatura no válida o sin acceso."}, status=404)

    data = cargar_datos(subject.dataset_path)
    df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)
    df_all = _sort_df_by_codigo_natural(df)

    ssbb = []
    cev = []

    for _, row in df_all.iterrows():
        t = str(row["Tipo"])
        item = {"code": str(row["Código"]), "label": str(row["Etiqueta"])}
        if t == "SSBB":
            ssbb.append(item)
        elif t == "CEv":
            cev.append(item)

    return JsonResponse({"ok": True, "ssbb": ssbb, "cev": cev})
