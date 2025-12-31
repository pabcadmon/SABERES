from pathlib import Path
import re
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

from django_apps.generator.models import ExportJob

from django.core.files.base import ContentFile
from django.utils import timezone

from django.http import FileResponse, Http404

from django.core.paginator import Paginator

from django_apps.accounts.models import Subject
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

def _get_subjects_for_user(user):
    accesses = user.usersubjectaccess_set.select_related("subject").all()
    return [a.subject for a in accesses]

def _sort_df_by_codigo_natural(dfx):
    if dfx is None or dfx.empty:
        return dfx
    return dfx.sort_values("Código", key=lambda s: s.map(natural_sort_key))

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
        .filter(user=request.user)
        .order_by("-created_at")
    )

    subject_code = (request.GET.get("subject") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if subject_code:
        qs = qs.filter(subject__code=subject_code)
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
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
            "selected_status": status,
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

@login_required
def tables_view(request):
    # Subjects accesibles: si ya tienes helper/manager, úsalo.
    # Aquí asumo UserSubjectAccess. Ajusta al tuyo.
    subjects = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .order_by("name")
        .distinct()
    )

    # Selección por querystring ?subject=<id> (opcional pero útil)
    selected_subject_id = request.GET.get("subject") or ""
    selected_subject = None
    if selected_subject_id:
        selected_subject = subjects.filter(id=selected_subject_id).first()

    ctx = {
        "subjects": subjects,
        "selected_subject": selected_subject,
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


@login_required
@require_POST
def tables_render(request):
    subject_id = (request.POST.get("subject_id") or "").strip()

    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject = subjects_qs.filter(id=subject_id).first() if subject_id else None

    selected_codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

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
        })

    data = cargar_datos(subject.dataset_path)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

    code_to_type = {}
    for c, t in zip(codigos_df["Código"].astype(str), codigos_df["Tipo"].astype(str)):
        code_to_type[str(c).strip().rstrip(".")] = str(t).strip()

    has_selection = has_subject and bool(selected_codes)

    table1 = table2_ssbb = table2_ce = table2_cev = table2_do = table3 = None
    error = None

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

            t1 = _decorate_df_codes(res.tabla1, code_to_type, selected_codes)
            t2_ssbb = _decorate_df_codes(tabla2_ssbb_display, code_to_type, selected_codes)
            t2_ce = _decorate_df_codes(tabla2_ce_display, code_to_type, selected_codes)
            t2_cev = _decorate_df_codes(tabla2_cev_display, code_to_type, selected_codes)
            t2_do = _decorate_df_codes(tabla2_do_display, code_to_type, selected_codes)
            t3 = _decorate_df_codes(tabla3_display, code_to_type, selected_codes)

            table1 = _df_to_ctx(t1)
            table2_ssbb = _df_to_ctx(t2_ssbb)
            table2_ce = _df_to_ctx(t2_ce)
            table2_cev = _df_to_ctx(t2_cev)
            table2_do = _df_to_ctx(t2_do)
            cols_to_hide = [c for c in ["Tipo", "orden", "Orden"] if c in t3.columns]
            t3 = t3.drop(columns=cols_to_hide)

            table3 = _df_to_ctx(t3)

        except Exception as e:
            error = repr(e)

    ctx = {
        "has_subject": has_subject,
        "has_selection": has_selection,
        "table1": table1,
        "table2_ssbb": table2_ssbb,
        "table2_ce": table2_ce,
        "table2_cev": table2_cev,
        "table2_do": table2_do,
        "table3": table3,
        "error": error,
    }

    return render(request, "generator/_tables_tables.html", ctx)


def tables_export(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    subject_id = request.POST.get("subject_id") or ""
    codes = request.POST.getlist("codes")

    if not subject_id or not codes:
        return HttpResponse("Faltan asignatura o códigos.", status=400)

    subject = Subject.objects.filter(id=subject_id).first()
    if subject is None:
        return HttpResponse("Asignatura no válida.", status=400)

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

@login_required
@require_POST
def tables_search(request):
    subject_id = (request.POST.get("subject_id") or "").strip()
    q = (request.POST.get("q") or "").strip()
    mode = (request.POST.get("mode") or "").strip()

    selected_codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject = subjects_qs.filter(id=subject_id).first() if subject_id else None
    has_subject = subject is not None

    groups = {"SSBB": [], "CE": [], "CEv": [], "DO": []}
    groups_cols = {"SSBB": [], "CE": [], "CEv": [], "DO": []}

    if has_subject:
        data = cargar_datos(subject.dataset_path)
        df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

        cod = df["Código"].astype(str)
        lab = df["Etiqueta"].astype(str)

        out = []

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
                    if len(out) >= 50:
                        break
                if len(out) >= 50:
                    break

        else:
            # 🔥 NUEVO: sin query -> mostrar TODO (o un máximo alto)
            df_all = _sort_df_by_codigo_natural(df)
            print(df_all)

            # si quieres "todo todo", quita el límite o súbelo
            MAX_ALL = 500  # recomendado para no matar el render si hay miles
            for _, row in df_all.iterrows():
                out.append({
                    "code": str(row["Código"]),
                    "label": str(row["Etiqueta"]),
                    "tipo": str(row["Tipo"]),
                })
                if len(out) >= MAX_ALL:
                    break

        # agrupar por tipo
        for item in out:
            t = item.get("tipo")
            if t in groups:
                groups[t].append(item)

        MAX_PER_COL = 15
        groups_cols = {
            "SSBB": _chunk_list(groups["SSBB"], MAX_PER_COL),
            "CE": _chunk_list(groups["CE"], MAX_PER_COL),
            "CEv": _chunk_list(groups["CEv"], MAX_PER_COL),
            "DO": _chunk_list(groups["DO"], MAX_PER_COL),
        }

    ctx = {
        "has_subject": has_subject,
        "q": q,
        "mode": mode,
        "groups_cols": groups_cols,
        "selected_codes": selected_codes,
        "is_full_list": has_subject and not q,   # opcional para el template
        "max_all": 500,                          # opcional
    }
    return render(request, "generator/_code_results.html", ctx)


def _chunk_list(items, chunk_size: int):
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


@login_required
@require_POST
def tables_selected_add(request):
    code = (request.POST.get("code") or "").strip()
    codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

    if code and code not in codes:
        codes.append(code)

    response = render(request, "generator/_selected_codes.html", {"selected_codes": codes})
    response["HX-Trigger-After-Settle"] = "codesChanged"
    return response


@login_required
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

def _decorate_cell(value, code_to_type: dict, selected_set: set) -> str:
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
        label = f"{tipo} | {code}"
        out.append(f'<span class="code-tag {cls}{sel}">{escape(label)}</span>')

    # Si no hemos “tocado” nada y era una celda normal, devolvemos escapado original
    if not touched and not looks_like_list:
        return escape(s)

    # Si era lista, los separamos con espacio como antes
    return " ".join(out)

def _decorate_df_codes(df, code_to_type: dict, selected_codes: list[str]):
    selected_set = set([c.strip().rstrip(".") for c in selected_codes])
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].apply(lambda v: _decorate_cell(v, code_to_type, selected_set))
    return out

@login_required
def curriculum_builder(request):
    subjects = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .order_by("name")
        .distinct()
    )
    return render(request, "curriculum/builder/builder.html", {"subjects": subjects})


@login_required
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
    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject = subjects_qs.filter(id=subject_id).first()
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
    used_ssbb = set()
    used_cev = set()

    for u in units:
        for x in (u.get("ssbb") or []):
            if isinstance(x, str):
                v = x.strip().rstrip(".")
                if v != "":
                    used_ssbb.add(v)

        for x in (u.get("cev") or []):
            if isinstance(x, str):
                v = x.strip().rstrip(".")
                if v != "":
                    used_cev.add(v)

    # 3) Missing
    missing_ssbb_codes = [c for c in all_ssbb.keys() if c not in used_ssbb]
    missing_cev_codes = [c for c in all_cev.keys() if c not in used_cev]

    # Orden natural (reusa tu helper)
    missing_ssbb_codes = sorted(missing_ssbb_codes, key=natural_sort_key)
    missing_cev_codes = sorted(missing_cev_codes, key=natural_sort_key)

    missing_ssbb = [{"code": c, "label": all_ssbb.get(c, "")} for c in missing_ssbb_codes]
    missing_cev = [{"code": c, "label": all_cev.get(c, "")} for c in missing_cev_codes]

    return JsonResponse(
        {
            "ok": True,
            "missing_ssbb": missing_ssbb,
            "missing_cev": missing_cev,
            "totals": {
                "all_ssbb": len(all_ssbb),
                "all_cev": len(all_cev),
                "used_ssbb": len(used_ssbb),
                "used_cev": len(used_cev),
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