from pathlib import Path
import re
from django.utils.html import escape

import traceback

from django.http import HttpResponse, HttpResponseBadRequest
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
            "table2": None,
            "table3": None,
            "error": None,
        })

    # ✅ Si hay asignatura pero aún no hay códigos, mostrar “elige códigos”
    if not selected_codes:
        return render(request, "generator/_tables_tables.html", {
            "has_subject": True,
            "table1": None,
            "table2": None,
            "table3": None,
            "error": None,
        })

    data = cargar_datos(subject.dataset_path)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)
    codigos_df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

    code_to_type = {}
    for c, t in zip(codigos_df["Código"].astype(str), codigos_df["Tipo"].astype(str)):
        code_to_type[str(c).strip().rstrip(".")] = str(t).strip()

    has_selection = has_subject and bool(selected_codes)

    table1 = table2 = table3 = None
    error = None

    if has_selection:
        try:
            res = generate_from_excel(
                subject.dataset_path,
                selected_codes,
                build_excel=False,
            )

            tabla2_display = marcar_seleccion_tabla2(res.tabla2, selected_codes)
            tabla3_display = marcar_seleccion_tabla3(res.tabla3, selected_codes)

            t1 = _decorate_df_codes(res.tabla1, code_to_type, selected_codes)
            t2 = _decorate_df_codes(tabla2_display, code_to_type, selected_codes)
            t3 = _decorate_df_codes(tabla3_display, code_to_type, selected_codes)

            table1 = _df_to_ctx(t1)
            table2 = _df_to_ctx(t2)
            cols_to_hide = [c for c in ["Tipo", "orden", "Orden"] if c in t3.columns]
            t3 = t3.drop(columns=cols_to_hide)

            table3 = _df_to_ctx(t3)

        except Exception as e:
            error = repr(e)

    ctx = {
        "has_subject": has_subject,
        "has_selection": has_selection,
        "table1": table1,
        "table2": table2,
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

    # ✅ selección actual (viene de los hidden inputs)
    selected_codes = [c.strip() for c in request.POST.getlist("codes") if c.strip()]

    subjects_qs = (
        Subject.objects
        .filter(usersubjectaccess__user=request.user, is_active=True)
        .distinct()
    )
    subject = subjects_qs.filter(id=subject_id).first() if subject_id else None
    has_subject = subject is not None

    # ✅ groups SIEMPRE definido
    groups = {"SSBB": [], "CE": [], "CEv": [], "DO": []}
    groups_cols = {"SSBB": [], "CE": [], "CEv": [], "DO": []}

    if has_subject and q:

        data = cargar_datos(subject.dataset_path)
        df = build_codigos_df(data.ssbb_df, data.ce_df, data.cev_df, data.do_df)

        q_low = q.lower()
        cod = df["Código"].astype(str)
        lab = df["Etiqueta"].astype(str)

        # ✅ CREAR los buckets
        starts = df[cod.str.lower().str.startswith(q_low)]
        contains = df[~cod.str.lower().str.startswith(q_low) & cod.str.lower().str.contains(q_low)]
        label_contains = df[
            ~cod.str.lower().str.contains(q_low) &
            lab.str.lower().str.contains(q_low)
        ]
        
        starts = _sort_df_by_codigo_natural(starts)
        contains = _sort_df_by_codigo_natural(contains)
        label_contains = _sort_df_by_codigo_natural(label_contains)

        out = []
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

        # ✅ agrupar por tipo
        for item in out:
            t = item.get("tipo")
            if t in groups:
                groups[t].append(item)
                
        MAX_PER_COL = 10

        groups_cols = {
            "SSBB": _chunk_list(groups["SSBB"], MAX_PER_COL),
            "CE": _chunk_list(groups["CE"], MAX_PER_COL),
            "CEv": _chunk_list(groups["CEv"], MAX_PER_COL),
            "DO": _chunk_list(groups["DO"], MAX_PER_COL),
        }
    # ✅ pasar selected_codes al template
    ctx = {
        "has_subject": has_subject,
        "q": q,
        "groups_cols": groups_cols,
        "selected_codes": selected_codes,
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