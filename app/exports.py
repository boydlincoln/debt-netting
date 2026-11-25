"""结果导出：Excel 台账与方案、Word 方案报告与多方抵账协议草稿。"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable, List

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "12344F"
TEAL = "0E7C86"
LIGHT = "EAF2F5"
AMBER = "B7791F"
RED = "B42318"
GRAY = "667085"

THIN = Side(style="thin", color="D0D5DD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
SUBHEADER_FILL = PatternFill("solid", fgColor=LIGHT)
TITLE_FONT = Font(name="微软雅黑", size=16, bold=True, color=NAVY)
HEADER_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10, color="1D2939")
MUTED_FONT = Font(name="微软雅黑", size=9, color=GRAY)
MONEY_FORMAT = '#,##0.00'

RISK_NOTES = [
    "本方案是多方协商一致的清偿与债务更新安排，不是法定自动抵销；须由全部参与方签署书面协议后方可执行。",
    "法定抵销要求债权为同种类金钱给付、均已到期且金额无争议；争议、查封冻结、未到期及约定禁止抵销的债务不得进入自动轧差池。",
    "抵押、职工工资、税款等优先顺位债权依法定顺序受偿，方案按顺位分组独立计算，不跨组互抵。",
    "方案中的头寸、金额与笔数由本地规则与求解器计算得出，线上模型不参与金额分配；执行前应复核主体状态、资产与涉诉信息的时点变化。",
    "本方案及协议草稿仅供业务与法务复核使用，不构成法律意见。",
]


# --------------------------------------------------------------------- 工具
def _yuan(cents: int | float | None) -> float:
    return round((int(cents or 0)) / 100, 2)


def _money(value) -> str:
    return f"{_yuan(value):,.2f}"


def _style_sheet(worksheet, title: str, headers: List[str], widths: List[int], subtitle: str = "") -> int:
    worksheet.sheet_view.showGridLines = False
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(headers)))
    cell = worksheet.cell(row=1, column=1, value=title)
    cell.font = TITLE_FONT
    cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 30
    row = 2
    if subtitle:
        worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(1, len(headers)))
        cell = worksheet.cell(row=2, column=1, value=subtitle)
        cell.font = MUTED_FONT
        row = 3
    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=row, column=index, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        worksheet.column_dimensions[get_column_letter(index)].width = widths[index - 1]
    worksheet.row_dimensions[row].height = 26
    worksheet.freeze_panes = worksheet.cell(row=row + 1, column=1)
    return row + 1


def _write_row(worksheet, row: int, values: Iterable, money_columns: Iterable[int] = ()) -> None:
    money_columns = set(money_columns)
    for index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row, column=index, value=value)
        cell.font = BODY_FONT
        cell.border = BORDER
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        if index in money_columns:
            cell.number_format = MONEY_FORMAT
            cell.alignment = Alignment(horizontal="right", vertical="top")


def _word_setup(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    for name, size, color in (("Heading 1", 16, NAVY), ("Heading 2", 13, TEAL), ("Heading 3", 11, NAVY)):
        heading = document.styles[name]
        heading.font.name = "微软雅黑"
        heading.font.size = Pt(size)
        heading.font.bold = True
        heading.font.color.rgb = RGBColor.from_string(color)
        heading.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    for section in document.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)


def _word_title(document: Document, title: str, subtitle: str = "") -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(title)
    run.font.name = "微软雅黑"
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    if subtitle:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(subtitle)
        run.font.name = "微软雅黑"
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor.from_string(GRAY)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    document.add_paragraph()


def _word_table(document: Document, headers: List[str], rows: List[List[str]], widths: List[float] | None = None):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        paragraph = cell.paragraphs[0]
        run = paragraph.add_run(header)
        run.font.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor.from_string(NAVY)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading = cell._tc.get_or_add_tcPr()
        from docx.oxml import OxmlElement

        element = OxmlElement("w:shd")
        element.set(qn("w:fill"), LIGHT)
        shading.append(element)
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = ""
            paragraph = cells[index].paragraphs[0]
            run = paragraph.add_run(str(value))
            run.font.size = Pt(9)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT if value.replace(",", "").replace(".", "").isdigit() else WD_ALIGN_PARAGRAPH.LEFT
    if widths:
        for index, width in enumerate(widths[: len(headers)]):
            for row in table.rows:
                row.cells[index].width = Cm(width)
    document.add_paragraph()
    return table


def _word_bullets(document: Document, items: Iterable[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        run = paragraph.add_run(item)
        run.font.size = Pt(10)


# --------------------------------------------------------------------- 台账 Excel
def export_ledger_xlsx(entities: List[dict], debts: List[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "债务台账"
    headers = ["编号", "债务人", "债权人", "本金(元)", "利息(元)", "债务金额(元)", "到期日", "顺位分组",
               "争议", "查封冻结", "禁止抵销", "确认状态", "来源", "抵销资格", "规则命中/原因", "备注"]
    widths = [13, 24, 24, 13, 10, 14, 12, 13, 7, 9, 9, 9, 8, 10, 40, 24]
    row = _style_sheet(sheet, "债务台账", headers, widths, "由三角债智能梳理与净额轧差系统导出")
    for debt in debts:
        evaluation = debt.get("eligibility") or {}
        reasons = "；".join(
            [f"{item.get('rule_id')} {item.get('message')}" for item in evaluation.get("blocking", [])]
            + [f"{item.get('rule_id')} {item.get('message')}" for item in evaluation.get("review", [])]
        )
        _write_row(
            sheet,
            row,
            [
                debt["id"],
                debt.get("debtor_name", ""),
                debt.get("creditor_name", ""),
                _yuan(debt.get("principal_cents")),
                _yuan(debt.get("interest_cents")),
                _yuan(debt.get("amount_cents")),
                debt.get("due_date", ""),
                (debt.get("eligibility") or {}).get("group_label", ""),
                "是" if debt.get("disputed") else "否",
                "是" if debt.get("frozen") else "否",
                "是" if debt.get("no_setoff_clause") else "否",
                {"confirmed": "已确认", "pending": "待复核", "rejected": "已排除"}.get(debt.get("status"), debt.get("status")),
                {"manual": "人工录入", "ai": "AI抽取", "import": "批量导入"}.get(debt.get("source"), debt.get("source")),
                "合格" if evaluation.get("eligible") else "不入池",
                reasons or "—",
                debt.get("note", ""),
            ],
            money_columns=(4, 5, 6),
        )
        if not evaluation.get("eligible"):
            sheet.cell(row=row, column=14).font = Font(name="微软雅黑", size=10, color=RED)
        row += 1

    entity_sheet = workbook.create_sheet("参与主体")
    row = _style_sheet(
        entity_sheet,
        "参与主体",
        ["编号", "名称", "统一社会信用代码", "经营状态", "可动用资金(元)", "涉诉", "被执行", "备注"],
        [14, 30, 24, 12, 16, 8, 9, 30],
        "主体信息仅保存在本地",
    )
    for entity in entities:
        _write_row(
            entity_sheet,
            row,
            [
                entity["id"],
                entity.get("name", ""),
                entity.get("credit_code", ""),
                entity.get("status", ""),
                _yuan(entity.get("available_cash_cents")),
                "是" if entity.get("litigation") else "否",
                "是" if entity.get("enforced") else "否",
                entity.get("note", ""),
            ],
            money_columns=(5,),
        )
        row += 1
    return _save_workbook(workbook)


# --------------------------------------------------------------------- 方案 Excel
def export_plan_xlsx(plan: dict) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "方案摘要"
    summary.sheet_view.showGridLines = False
    summary.column_dimensions["A"].width = 26
    summary.column_dimensions["B"].width = 46
    summary["A1"] = "债务轧差化简方案"
    summary["A1"].font = Font(name="微软雅黑", size=18, bold=True, color=NAVY)
    summary.merge_cells("A1:B1")
    summary["A2"] = f"方案编号 {plan['id']}　基准日 {plan['as_of_date']}　生成时间 {plan['created_at']}"
    summary["A2"].font = MUTED_FONT
    summary.merge_cells("A2:B2")

    stats = plan.get("summary", {})
    rows = [
        ("核算记录", plan.get("name") or f"核算 #{plan.get('seq', '')}"),
        ("计算口径", plan.get("mode_label", "法律合规口径")),
        ("参与主体", stats.get("entity_count", 0)),
        ("债务总笔数", stats.get("debt_count", 0)),
        ("纳入轧差笔数", stats.get("included_count", 0)),
        ("未入池笔数", stats.get("excluded_count", 0)),
        ("待复核笔数", stats.get("pending_count", 0)),
        ("清偿交易笔数", stats.get("transaction_count", 0)),
        ("清偿总金额(元)", _money(stats.get("transaction_amount_cents"))),
        ("头寸归零出局主体", stats.get("zero_out_count", 0)),
        ("最优性", "已证明最优" if stats.get("optimality") == "proven" else "启发式（未证明最优）"),
    ]
    row = 4
    for label, value in rows:
        summary.cell(row=row, column=1, value=label).font = Font(name="微软雅黑", size=10, bold=True, color=NAVY)
        summary.cell(row=row, column=2, value=value).font = BODY_FONT
        row += 1

    row += 1
    summary.cell(row=row, column=1, value="校验结果").font = Font(name="微软雅黑", size=12, bold=True, color=TEAL)
    row += 1
    for check in plan.get("checks", []):
        summary.cell(row=row, column=1, value=check.get("name", "")).font = BODY_FONT
        cell = summary.cell(row=row, column=2, value=("通过" if check.get("ok") else "未通过") + f"　{check.get('detail', '')}")
        cell.font = Font(name="微软雅黑", size=10, color="067647" if check.get("ok") else RED)
        row += 1

    position_sheet = workbook.create_sheet("净头寸")
    row = _style_sheet(
        position_sheet,
        "净头寸表",
        ["分组", "主体", "应收总额(元)", "应付总额(元)", "净头寸(元)", "角色", "头寸归零"],
        [15, 30, 16, 16, 16, 12, 10],
        "净头寸 = 应收总额 − 应付总额；同一分组内应收合计与应付合计相等",
    )
    for group in plan.get("groups", []):
        for participant in group.get("participants", []):
            _write_row(
                position_sheet,
                row,
                [
                    group.get("label", ""),
                    participant.get("name", ""),
                    _yuan(participant.get("receivable_cents")),
                    _yuan(participant.get("payable_cents")),
                    _yuan(participant.get("net_cents")),
                    {"debtor": "净债务人", "creditor": "净债权人", "zero": "头寸归零"}.get(participant.get("role"), ""),
                    "是" if participant.get("zero_out") else "否",
                ],
                money_columns=(3, 4, 5),
            )
            row += 1

    tx_sheet = workbook.create_sheet("清偿清单")
    row = _style_sheet(
        tx_sheet,
        "最简清偿清单",
        ["序号", "分组", "付款方", "收款方", "金额(元)", "执行状态", "备注"],
        [7, 15, 30, 30, 16, 12, 30],
        "每笔交易使至少一个主体头寸归零；执行完毕后原始债务全部结清",
    )
    for group in plan.get("groups", []):
        for tx in group.get("transactions", []):
            _write_row(
                tx_sheet,
                row,
                [tx.get("seq"), group.get("label", ""), tx.get("from_name", ""), tx.get("to_name", ""),
                 _yuan(tx.get("amount_cents")), "待执行", ""],
                money_columns=(5,),
            )
            row += 1

    debt_sheet = workbook.create_sheet("债务与入池")
    row = _style_sheet(
        debt_sheet,
        "原始债务与入池情况",
        ["债务编号", "债务人", "债权人", "金额(元)", "到期日", "分组", "状态", "入池", "未入池原因"],
        [15, 26, 26, 15, 12, 14, 10, 8, 46],
        "未入池债务不参与自动轧差，须人工或法务复核",
    )
    for debt in plan.get("included_debts", []):
        _write_row(
            debt_sheet,
            row,
            [debt.get("id"), debt.get("debtor_name"), debt.get("creditor_name"), _yuan(debt.get("amount_cents")),
             debt.get("due_date"), debt.get("group_label", ""), "已确认", "是", ""],
            money_columns=(4,),
        )
        row += 1
    for item in plan.get("excluded", []):
        _write_row(
            debt_sheet,
            row,
            [item.get("debt_id"), item.get("debtor_name"), item.get("creditor_name"), _yuan(item.get("amount_cents")),
             item.get("due_date"), item.get("group_label", ""), item.get("status_label", ""), "否",
             "；".join(item.get("reasons", []))],
            money_columns=(4,),
        )
        row += 1

    schedule = (plan.get("liquidity") or {}).get("schedule") or []
    if schedule:
        schedule_sheet = workbook.create_sheet("分期建议")
        row = _style_sheet(
            schedule_sheet,
            "资金约束下的分期执行建议",
            ["期次", "付款方", "收款方", "金额(元)", "建议付款日"],
            [8, 30, 30, 16, 14],
            "分期建议不改变净额轧差的最小交易笔数，仅供签约时参考",
        )
        for item in schedule:
            _write_row(
                schedule_sheet,
                row,
                [item.get("period"), item.get("payer_name", ""), item.get("payee_name", ""),
                 _yuan(item.get("amount_cents")), item.get("due_date", "")],
                money_columns=(4,),
            )
            row += 1

    return _save_workbook(workbook)


def _save_workbook(workbook: Workbook) -> bytes:
    for sheet in workbook.worksheets:
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------- 方案报告 Word
def export_plan_docx(plan: dict) -> bytes:
    document = Document()
    _word_setup(document)
    mode_label = plan.get("mode_label", "法律合规口径")
    _word_title(
        document,
        "债务轧差化简结果报告",
        f"{plan.get('name') or ('核算 #' + str(plan.get('seq', '')))}　基准日 {plan['as_of_date']}　方案编号 {plan['id']}　{mode_label}",
    )
    if plan.get("mode") == "pure":
        paragraph = document.add_paragraph()
        run = paragraph.add_run(
            "【纯数学口径】本报告忽略争议、查封冻结、到期、禁止抵销与优先分组，仅用于测算理论最少交易笔数，"
            "不能作为清偿或签署协议的依据。"
        )
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor.from_string(RED)

    summary = plan.get("summary", {})

    # 面向普通读者的“大白话”摘要
    plain_group = {
        "ordinary": "普通货款", "mortgage": "抵押贷款", "wage": "职工工资",
        "tax": "税款", "custom": "其他优先款", "all": "全部合并",
    }
    plain_money = lambda cents: f"{round((int(cents or 0) / 100) / 10000, 2):g} 万"
    transactions = plan.get("transactions", [])
    payers: dict[str, int] = {}
    receivers: dict[str, int] = {}
    for tx in transactions:
        payers[tx["from_name"]] = payers.get(tx["from_name"], 0) + int(tx["amount_cents"])
        receivers[tx["to_name"]] = receivers.get(tx["to_name"], 0) + int(tx["amount_cents"])
    document.add_heading("大白话：谁给谁钱", level=1)
    document.add_paragraph(
        f"这次一共 {len(transactions)} 笔付款，合计 {plain_money(summary.get('transaction_amount_cents'))}。"
    )
    _word_table(
        document,
        ["谁付钱", "给谁", "多少钱", "什么钱"],
        [
            [tx["from_name"], tx["to_name"], plain_money(tx["amount_cents"]), plain_group.get(tx.get("group_code"), "欠款")]
            for tx in transactions
        ],
        [4.8, 4.8, 3.2, 3.6],
    )
    document.add_paragraph("出钱的一方：" + "；".join(
        f"{name} {plain_money(amount)}" for name, amount in sorted(payers.items(), key=lambda item: -item[1])
    ))
    document.add_paragraph("收钱的一方：" + "；".join(
        f"{name} {plain_money(amount)}" for name, amount in sorted(receivers.items(), key=lambda item: -item[1])
    ))
    if plan.get("mode") == "pure":
        document.add_paragraph(
            "注意：纯数学口径把争议、查封、未到期、禁止抵销、待复核的欠条也算进来了，并把工资和普通货款混算；"
            "例如付款给工会的主体可能不是原工资债务人。该清单只用于测算，不能执行。"
        )
    elif plan.get("excluded"):
        document.add_paragraph("这次没算的欠条（不是不用还，是要另外处理）：")
        _word_bullets(
            document,
            [
                f"{item.get('debtor_name')} 欠 {item.get('creditor_name')} {plain_money(item.get('amount_cents'))}："
                f"{'；'.join(item.get('reasons', []))}"
                for item in plan.get("excluded", [])
            ],
        )

    document.add_heading("一、方案概况", level=1)
    _word_bullets(
        document,
        [
            f"参与主体 {summary.get('entity_count', 0)} 个，原始债务 {summary.get('debt_count', 0)} 笔，"
            f"纳入轧差 {summary.get('included_count', 0)} 笔，未入池 {summary.get('excluded_count', 0)} 笔。",
            f"净债务人 {summary.get('debtor_count', 0)} 个，净债权人 {summary.get('creditor_count', 0)} 个，"
            f"头寸归零出局主体 {summary.get('zero_out_count', 0)} 个。",
            f"最简清偿方案共 {summary.get('transaction_count', 0)} 笔交易，涉及金额 {_money(summary.get('transaction_amount_cents'))} 元。",
            "求解结论：" + ("已证明交易笔数达到理论最少。" if summary.get("optimality") == "proven"
                           else "在时间预算内未完成最优性证明，当前为启发式近优方案。"),
        ],
    )

    document.add_heading("二、参与主体与净头寸", level=1)
    rows = []
    for group in plan.get("groups", []):
        for participant in group.get("participants", []):
            rows.append(
                [
                    group.get("label", ""),
                    participant.get("name", ""),
                    _money(participant.get("receivable_cents")),
                    _money(participant.get("payable_cents")),
                    _money(participant.get("net_cents")),
                    {"debtor": "净债务人", "creditor": "净债权人", "zero": "头寸归零"}.get(participant.get("role"), ""),
                ]
            )
    _word_table(document, ["分组", "主体", "应收(元)", "应付(元)", "净头寸(元)", "角色"], rows, [3.2, 5.0, 3.0, 3.0, 3.0, 2.2])

    document.add_heading("三、最简清偿清单", level=1)
    rows = []
    for group in plan.get("groups", []):
        for tx in group.get("transactions", []):
            rows.append([str(tx.get("seq")), group.get("label", ""), tx.get("from_name", ""), tx.get("to_name", ""),
                         _money(tx.get("amount_cents"))])
    _word_table(document, ["序号", "分组", "付款方", "收款方", "金额(元)"], rows, [1.4, 3.2, 5.2, 5.2, 3.2])

    document.add_heading("四、被抵销结清的原始债务", level=1)
    rows = [
        [debt.get("id", ""), debt.get("debtor_name", ""), debt.get("creditor_name", ""),
         _money(debt.get("amount_cents")), debt.get("due_date", "")]
        for debt in plan.get("included_debts", [])
    ]
    _word_table(document, ["债务编号", "债务人", "债权人", "金额(元)", "到期日"], rows, [3.2, 4.6, 4.6, 3.2, 2.6])

    document.add_heading("五、校验结果", level=1)
    rows = [
        [check.get("name", ""), "通过" if check.get("ok") else "未通过", check.get("detail", "")]
        for check in plan.get("checks", [])
    ]
    _word_table(document, ["校验项", "结果", "说明"], rows, [5.2, 2.2, 9.2])

    excluded = plan.get("excluded", [])
    if excluded:
        document.add_heading("六、未入池债务与原因", level=1)
        rows = [
            [item.get("debtor_name", ""), item.get("creditor_name", ""), _money(item.get("amount_cents")),
             "；".join(item.get("reasons", []))]
            for item in excluded
        ]
        _word_table(document, ["债务人", "债权人", "金额(元)", "原因"], rows, [4.2, 4.2, 3.0, 6.0])

    liquidity = plan.get("liquidity") or {}
    if liquidity.get("constrained"):
        document.add_heading("七、资金约束提示", level=1)
        _word_bullets(
            document,
            [
                f"{item.get('name')} 应付出 {_money(item.get('payable_cents'))} 元，"
                f"可动用资金 {_money(item.get('available_cash_cents'))} 元，"
                f"资金缺口 {_money(item.get('shortfall_cents'))} 元。"
                for item in liquidity.get("constrained", [])
            ],
        )
        document.add_paragraph("系统已按可动用资金生成分期执行建议（见附表），分期安排不改变净额轧差的最小交易笔数。")

    narrative = (plan.get("ai_narrative") or {}).get("content")
    if narrative:
        document.add_heading("附：方案解读（AI 辅助生成）", level=1)
        for paragraph_text in str(narrative).split("\n"):
            if paragraph_text.strip():
                document.add_paragraph(paragraph_text.strip())

    document.add_heading("八、法律边界与风险提示", level=1)
    _word_bullets(document, RISK_NOTES)

    document.add_paragraph()
    paragraph = document.add_paragraph()
    run = paragraph.add_run("本报告由三角债智能梳理与净额轧差系统自动生成，供业务与法务复核；最终执行须经各方签署书面协议。")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(GRAY)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------- 协议草稿 Word
def export_agreement_docx(plan: dict) -> bytes:
    document = Document()
    _word_setup(document)
    _word_title(document, "多方债务抵销及清偿协议", "（草稿 · 待法务审核）")

    parties = []
    seen = set()
    for group in plan.get("groups", []):
        for participant in group.get("participants", []):
            if participant["id"] in seen:
                continue
            seen.add(participant["id"])
            parties.append(participant)
    for index, party in enumerate(parties):
        prefix = "甲方" if index == 0 else ("乙方" if index == 1 else f"丙方" if index == 2 else f"第{index + 1}方")
        paragraph = document.add_paragraph()
        run = paragraph.add_run(f"{prefix}：{party.get('name', '')}")
        run.font.bold = True
        document.add_paragraph("统一社会信用代码：____________________")
        document.add_paragraph("住所：____________________")
        document.add_paragraph("法定代表人／授权代表：____________________")
        document.add_paragraph()

    document.add_heading("鉴于", level=1)
    _word_bullets(
        document,
        [
            f"截至 {plan['as_of_date']}，各方之间存在本协议附件一《债务清单》所列的债权债务关系；",
            "各方已对上述债务的金额、到期状态与无争议性进行核对，并同意按照本协议约定进行抵销与净额清偿；",
            "本次安排系各方基于真实意思表示达成的多方清偿安排，不构成任何一方对未列明债务的放弃。",
        ],
    )

    document.add_heading("第一条　债务确认", level=1)
    document.add_paragraph(
        "各方确认，截至基准日，附件一所列债务真实、合法、有效，金额无争议，且均已到期，不存在被查封、"
        "冻结或禁止抵销的情形。附件一所列债务经本次抵销后全部结清。"
    )
    rows = [
        [debt.get("id", ""), debt.get("debtor_name", ""), debt.get("creditor_name", ""),
         _money(debt.get("amount_cents")), debt.get("due_date", "")]
        for debt in plan.get("included_debts", [])
    ]
    _word_table(document, ["债务编号", "债务人", "债权人", "金额(元)", "到期日"], rows, [3.2, 4.6, 4.6, 3.2, 2.6])

    document.add_heading("第二条　抵销与净额确认", level=1)
    document.add_paragraph(
        "各方同意，将各自在附件一中的应收、应付债务相互抵销，按主体计算净头寸，并以净额作为本协议项下的"
        "最终清偿义务。抵销后，各方在本协议附件一债务项下的债权债务关系归于消灭。"
    )
    rows = []
    for group in plan.get("groups", []):
        for participant in group.get("participants", []):
            rows.append([group.get("label", ""), participant.get("name", ""),
                         _money(participant.get("receivable_cents")), _money(participant.get("payable_cents")),
                         _money(participant.get("net_cents"))])
    _word_table(document, ["分组", "主体", "应收(元)", "应付(元)", "净头寸(元)"], rows, [3.4, 5.0, 3.2, 3.2, 3.2])

    document.add_heading("第三条　清偿安排", level=1)
    document.add_paragraph("各方应按下列清偿清单完成付款；每笔付款完成后，相应主体之间的净额债务即告结清。")
    rows = []
    for group in plan.get("groups", []):
        for tx in group.get("transactions", []):
            rows.append([str(tx.get("seq")), tx.get("from_name", ""), tx.get("to_name", ""),
                         _money(tx.get("amount_cents"))])
    _word_table(document, ["序号", "付款方", "收款方", "金额(元)"], rows, [1.4, 6.2, 6.2, 3.4])

    document.add_heading("第四条　履行期限与方式", level=1)
    document.add_paragraph(
        "各方应于本协议生效之日起 ______ 个工作日内，将应付款项支付至收款方指定账户。"
        "收款账户信息由各方另行书面确认。付款方不得以本协议之外的债权主张抵扣本协议项下应付款项。"
    )
    schedule = (plan.get("liquidity") or {}).get("schedule") or []
    if schedule:
        document.add_paragraph("对于存在资金约束的付款方，各方可参照下列分期安排履行：")
        rows = [
            [str(item.get("period")), item.get("payer_name", ""), item.get("payee_name", ""),
             _money(item.get("amount_cents")), item.get("due_date", "")]
            for item in schedule
        ]
        _word_table(document, ["期次", "付款方", "收款方", "金额(元)", "建议付款日"], rows, [1.6, 4.6, 4.6, 3.2, 3.2])

    document.add_heading("第五条　陈述与保证", level=1)
    _word_bullets(
        document,
        [
            "各方保证其为依法设立并有效存续的主体，签署本协议已取得内部必要授权；",
            "各方保证附件一所列债务真实、金额准确，不存在未披露的争议、查封、冻结或禁止抵销约定；",
            "各方保证不存在影响本协议履行的重大诉讼、仲裁或执行程序。",
        ],
    )

    document.add_heading("第六条　生效条件", level=1)
    document.add_paragraph(
        "本协议自各方加盖公章并由法定代表人或授权代表签字之日起生效。本协议生效后，"
        "附件一债务即按本协议约定抵销；未纳入本协议的债务不受影响。"
    )

    document.add_heading("第七条　争议解决", level=1)
    document.add_paragraph(
        "因本协议引起的或与本协议有关的争议，各方应友好协商解决；协商不成的，"
        "提交 ________ 人民法院诉讼解决。"
    )

    document.add_heading("第八条　其他", level=1)
    document.add_paragraph(
        "本协议一式 ____ 份，各方各执 ____ 份，具有同等法律效力。附件为本协议不可分割的组成部分。"
    )

    document.add_paragraph()
    document.add_paragraph("（以下无正文，为签署页）")
    document.add_paragraph()
    for index, party in enumerate(parties):
        prefix = "甲方" if index == 0 else ("乙方" if index == 1 else f"丙方" if index == 2 else f"第{index + 1}方")
        document.add_paragraph(f"{prefix}（盖章）：{party.get('name', '')}")
        document.add_paragraph("法定代表人或授权代表（签字）：________________")
        document.add_paragraph("签署日期：______年____月____日")
        document.add_paragraph()

    paragraph = document.add_paragraph()
    run = paragraph.add_run(
        "重要提示：本文件为系统生成的协议草稿，不构成法律意见。方案性质为多方清偿安排，非法定自动抵销；"
        "签署前须由法务对债务真实性、抵销条件、优先顺位与授权手续进行终审。"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(RED)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
