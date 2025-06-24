import io
import pandas as pd

def exportar_excel(tabla1, tabla2, seleccionados, resumen_df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        bold_red = workbook.add_format({'bold': True, 'font_color': 'red'})
        bold_black = workbook.add_format({'bold': True})
        normal = workbook.add_format()

        # --- Relaciones por tipo ---
        tabla1.to_excel(writer, sheet_name='Relaciones por tipo', index=False, startrow=1, header=False)
        sheet1 = writer.sheets['Relaciones por tipo']

        for col_num, col in enumerate(tabla1.columns):
            sheet1.write(0, col_num, col, bold_black)

        for row_num, row in enumerate(tabla1.itertuples(index=False), start=1):
            for col_num, cell in enumerate(row):
                if col_num == 0:
                    sheet1.write(row_num, col_num, cell, normal)
                else:
                    if isinstance(cell, str) and ',' in cell:
                        parts = [p.strip() for p in cell.split(',')]
                        rich = []
                        for i, p in enumerate(parts):
                            fmt = bold_red if p in seleccionados else normal
                            rich += [fmt, p]
                            if i < len(parts) - 1:
                                rich += [normal, ', ']
                        sheet1.write_rich_string(row_num, col_num, *rich)
                    else:
                        fmt = bold_red if str(cell).strip() in seleccionados else normal
                        sheet1.write(row_num, col_num, cell, fmt)

        for col_num, col in enumerate(tabla1.columns):
            valores = [str(col)] + tabla1[col].astype(str).tolist()
            sheet1.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # --- Saberes Básicos relacionados ---
        tabla2.to_excel(writer, sheet_name='Saberes Básicos relacionados', index=False, startrow=1, header=False)
        sheet2 = writer.sheets['Saberes Básicos relacionados']

        for col_num, col in enumerate(tabla2.columns):
            sheet2.write(0, col_num, col, bold_black)

        for row_num, row in enumerate(tabla2.itertuples(index=False), start=1):
            for col_num, cell in enumerate(row):
                texto = str(cell).replace('»', '').replace('«', '')

                if ',' in texto:
                    parts = [p.strip() for p in texto.split(',')]
                    rich = []
                    for i, part in enumerate(parts):
                        fmt = bold_red if part in seleccionados else normal
                        rich.append(fmt)
                        rich.append(part)
                        if i < len(parts) - 1:
                            rich.append(normal)
                            rich.append(', ')
                    sheet2.write_rich_string(row_num, col_num, *rich)
                else:
                    fmt = bold_red if texto in seleccionados else normal
                    sheet2.write(row_num, col_num, texto, fmt)

        for col_num, col in enumerate(tabla2.columns):
            valores = [str(col)] + tabla2[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # --- Descripciones de elementos mostrados ---
        resumen_df.to_excel(writer, sheet_name='Descr. de elementos mostrados', index=False, startrow=1, header=False)
        sheet3 = writer.sheets['Descr. de elementos mostrados']

        for col_num, col in enumerate(resumen_df.columns):
            sheet3.write(0, col_num, col, bold_black)

        for row_num, row in enumerate(resumen_df.itertuples(index=False), start=1):
            for col_num, cell in enumerate(row):
                sheet3.write(row_num, col_num, str(cell), normal)

        for col_num, col in enumerate(resumen_df.columns):
            valores = [str(col)] + resumen_df[col].astype(str).tolist()
            sheet3.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

    output.seek(0)
    return output
