# -*- coding: utf-8 -*-
"""极简 .xlsx 读写（仅依赖标准库 zipfile / xml）。

后端坚持"零第三方依赖"，因此在这里用纯标准库生成/解析 xlsx：
- 写入：inlineStr 内联字符串 + 数值单元格，Excel/WPS 可直接打开
- 读取：兼容内联字符串与本工具自己导出的格式（也兼容常见 sharedStrings）
只支持单工作表，足够本项目的备份格式使用。
"""
import io
import zipfile
import xml.etree.ElementTree as ET

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_RS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OD = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_TAG = "{%s}" % _NS  # ElementTree 限定名需用 Clark 记号


def _xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _col_letter(n):
    """1 起始列号 -> Excel 列字母（1->A）。"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(headers, rows, sheet_name="records"):
    """把表头 + 数据写成 .xlsx 字节。rows 为等长 list（与 headers 对齐）。"""
    # ---- worksheet XML ----
    lines = []
    for rnum, row in enumerate([headers] + rows, start=1):
        cells = []
        for i, val in enumerate(row, start=1):
            ref = _col_letter(i) + str(rnum)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cells.append('<c r="{}"><v>{}</v></c>'.format(ref, val))
            else:
                cells.append('<c r="{0}" t="inlineStr"><is><t xml:space="preserve">{1}</t></is></c>'
                             .format(ref, _xml_escape(val)))
        lines.append('<row r="{}">{}</row>'.format(rnum, "".join(cells)))
    sheet = ('<worksheet xmlns="{0}"><sheetData>{1}</sheetData></worksheet>'
             .format(_NS, "".join(lines)))

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="{ct}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    ).format(ct=_CT)

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="{rs}">'
        '<Relationship Id="rId1" Type="{od}/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    ).format(rs=_RS, od=_OD)

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="{ns}" xmlns:r="{od}">'
        '<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    ).format(ns=_NS, od=_OD, name=_xml_escape(sheet_name))

    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="{rs}">'
        '<Relationship Id="rId1" Type="{od}/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="{od}/styles" Target="styles.xml"/>'
        '</Relationships>'
    ).format(rs=_RS, od=_OD)

    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="{ns}">'
        '<fonts count="2">'
        '<font><sz val="11"/><color theme="1"/><name val="宋体"/><family val="2"/></font>'
        '<font><b/><sz val="11"/><color theme="1"/><name val="宋体"/><family val="2"/></font>'
        '</fonts>'
        '<fills count="2">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '</fills>'
        '<borders count="1"><border>'
        '<left style="none"/><right style="none"/><top style="none"/><bottom style="none"/><diagonal/>'
        '</border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    ).format(ns=_NS)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def _col_to_idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def read_xlsx(data):
    """从 .xlsx 字节读数据。返回 (headers, rows)。

    headers: 首行表头（去空白）列表
    rows:    其余行，list[dict]，dict 以表头为键（值为字符串，金额等数值转为文本）
    """
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        # 共享字符串（兼容其他工具生成的 xlsx）
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(_TAG + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_TAG + "t")))
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in names:
            return [], []
        root = ET.fromstring(z.read(sheet_path))

    grid = []
    for row_el in root.iter(_TAG + "row"):
        cells = {}
        for c in row_el.iter(_TAG + "c"):
            ref = c.get("r") or ""
            t = c.get("t")
            if t == "inlineStr":
                el = c.find(_TAG + "is")
                val = "".join(x.text or "" for x in el.iter(_TAG + "t")) if el is not None else ""
            elif t == "s":
                v = c.find(_TAG + "v")
                idx = int(v.text) if v is not None and v.text else 0
                val = shared[idx] if idx < len(shared) else ""
            else:
                v = c.find(_TAG + "v")
                val = v.text if v is not None and v.text is not None else ""
            col = "".join(ch for ch in ref if ch.isalpha()) or _col_letter(len(cells) + 1)
            cells[col] = val
        grid.append(cells)

    if not grid:
        return [], []

    header_cells = sorted(grid[0].items(), key=lambda kv: _col_to_idx(kv[0]))
    headers = [(v or "").strip() for _, v in header_cells]
    col_to_header = {c: (v or "").strip() for c, v in header_cells}
    rows = []
    for cells in grid[1:]:
        d = {}
        for c, v in cells.items():
            h = col_to_header.get(c)
            if h:
                d[h] = v
        rows.append(d)
    return headers, rows