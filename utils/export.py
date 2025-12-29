import io
import pandas as pd

def _write_tabla_with_formatting(sheet, tabla, seleccionados, bold_red, bold_black, normal):
    """Helper para escribir una tabla con formato de seleccionados."""
    tabla.to_excel(pd.ExcelWriter(pd.io.excel._get_writer(), engine='xlsxwriter').book, 
                   sheet_name='temp', index=False)
    
    for col_num, col in enumerate(tabla.columns):
        sheet.write(0, col_num, col, bold_black)

    for row_num, row in enumerate(tabla.itertuples(index=False), start=1):
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
                sheet.write_rich_string(row_num, col_num, *rich)
            else:
                fmt = bold_red if texto in seleccionados else normal
                sheet.write(row_num, col_num, texto, fmt)

    for col_num, col in enumerate(tabla.columns):
        valores = [str(col)] + tabla[col].astype(str).tolist()
        sheet.set_column(col_num, col_num, max(len(v) for v in valores) + 2)


def exportar_excel(tabla1, tabla2_ssbb, tabla2_ce, tabla2_cev, tabla2_do, tabla3, seleccionados):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        bold_red = workbook.add_format({'bold': True, 'font_color': 'red'})
        bold_black = workbook.add_format({'bold': True})
        normal = workbook.add_format()

        # --- Sheet 1: Relaciones por tipo ---
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

        # --- Sheet 2: Relaciones individuales (SSBB, CE, CEv, DO) ---
        # Tabla 2: SSBB relacionados
        tabla2_ssbb.to_excel(writer, sheet_name='Relaciones individuales', index=False, startrow=1, header=False)
        sheet2 = writer.sheets['Relaciones individuales']
        
        for col_num, col in enumerate(tabla2_ssbb.columns):
            sheet2.write(0, col_num, col, bold_black)

        for row_num, row in enumerate(tabla2_ssbb.itertuples(index=False), start=1):
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

        for col_num, col in enumerate(tabla2_ssbb.columns):
            valores = [str(col)] + tabla2_ssbb[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # Tabla 3: CE relacionados (comienza en fila 2 + height(tabla2_ssbb) + 2)
        startrow_tabla3 = len(tabla2_ssbb) + 4
        sheet2.merge_range(startrow_tabla3 - 1, 0, startrow_tabla3 - 1, len(tabla2_ce.columns) - 1, 'Tabla 3: CE relacionados', bold_black)
        tabla2_ce.to_excel(writer, sheet_name='Relaciones individuales', index=False, startrow=startrow_tabla3, header=False)
        
        for col_num, col in enumerate(tabla2_ce.columns):
            sheet2.write(startrow_tabla3, col_num, col, bold_black)

        for row_num, row in enumerate(tabla2_ce.itertuples(index=False), start=startrow_tabla3 + 1):
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

        for col_num, col in enumerate(tabla2_ce.columns):
            valores = [str(col)] + tabla2_ce[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # Tabla 4: CEv relacionados
        startrow_tabla4 = startrow_tabla3 + len(tabla2_ce) + 3
        sheet2.merge_range(startrow_tabla4 - 1, 0, startrow_tabla4 - 1, len(tabla2_cev.columns) - 1, 'Tabla 4: CEv relacionados', bold_black)
        tabla2_cev.to_excel(writer, sheet_name='Relaciones individuales', index=False, startrow=startrow_tabla4, header=False)
        
        for col_num, col in enumerate(tabla2_cev.columns):
            sheet2.write(startrow_tabla4, col_num, col, bold_black)

        for row_num, row in enumerate(tabla2_cev.itertuples(index=False), start=startrow_tabla4 + 1):
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

        for col_num, col in enumerate(tabla2_cev.columns):
            valores = [str(col)] + tabla2_cev[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # Tabla 5: DO relacionados
        startrow_tabla5 = startrow_tabla4 + len(tabla2_cev) + 3
        sheet2.merge_range(startrow_tabla5 - 1, 0, startrow_tabla5 - 1, len(tabla2_do.columns) - 1, 'Tabla 5: DO relacionados', bold_black)
        tabla2_do.to_excel(writer, sheet_name='Relaciones individuales', index=False, startrow=startrow_tabla5, header=False)
        
        for col_num, col in enumerate(tabla2_do.columns):
            sheet2.write(startrow_tabla5, col_num, col, bold_black)

        for row_num, row in enumerate(tabla2_do.itertuples(index=False), start=startrow_tabla5 + 1):
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

        for col_num, col in enumerate(tabla2_do.columns):
            valores = [str(col)] + tabla2_do[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # Tabla 6: Descripciones de elementos mostrados (antigua tabla 3)
        startrow_tabla6 = startrow_tabla5 + len(tabla2_do) + 3
        sheet2.merge_range(startrow_tabla6 - 1, 0, startrow_tabla6 - 1, len(tabla3.columns) - 1, 'Tabla 6: Descripciones de elementos mostrados', bold_black)
        tabla3.to_excel(writer, sheet_name='Relaciones individuales', index=False, startrow=startrow_tabla6, header=False)
        
        for col_num, col in enumerate(tabla3.columns):
            sheet2.write(startrow_tabla6, col_num, col, bold_black)

        for row_num, row in enumerate(tabla3.itertuples(index=False), start=startrow_tabla6 + 1):
            for col_num, cell in enumerate(row):
                sheet2.write(row_num, col_num, str(cell), normal)

        for col_num, col in enumerate(tabla3.columns):
            valores = [str(col)] + tabla3[col].astype(str).tolist()
            sheet2.set_column(col_num, col_num, max(len(v) for v in valores) + 2)

        # --- Sheet 3: Descripciones de elementos mostrados (copia para compatibilidad) ---
        tabla3.to_excel(writer, sheet_name='Descr. de elementos mostrados', index=False, startrow=1, header=False)
        sheet3 = writer.sheets['Descr. de elementos mostrados']

        for col_num, col in enumerate(tabla3.columns):
            sheet3.write(0, col_num, col, bold_black)

        for row_num, row in enumerate(tabla3.itertuples(index=False), start=1):
            for col_num, cell in enumerate(row):
                sheet3.write(row_num, col_num, str(cell), normal)

        for col_num, col in enumerate(tabla3.columns):
            valores = [str(col)] + tabla3[col].astype(str).tolist()
    return output
