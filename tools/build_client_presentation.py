from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "PPWR_Digital_Platform_Client_Overview_ZH.pptx"
LOGO = ROOT / "cps-coe-design-system_v1.1" / "logo.png"

SW, SH = 13.333, 7.5
FONT = "Microsoft YaHei"
NAVY = "102B46"
BLUE = "0066CC"
BLUE2 = "3D91D6"
CYAN = "20A5A1"
INK = "1A2942"
MUTED = "5A6A7A"
PALE = "F0F6FF"
PALE_GREEN = "EAF6F4"
PAPER = "F7F9FC"
WHITE = "FFFFFF"
LINE = "DCE4ED"
YELLOW = "F4C84A"
GREEN = "23845B"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def shape(slide, kind, x, y, w, h, fill, line_color=None):
    item = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    item.fill.solid()
    item.fill.fore_color.rgb = rgb(fill)
    item.line.color.rgb = rgb(line_color or fill)
    item.line.width = Pt(0.7)
    return item


def box(slide, x, y, w, h, fill=WHITE, line_color=LINE):
    return shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, line_color)


def text(slide, value, x, y, w, h, size=16, color=INK, bold=False,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0.02):
    item = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = item.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    for index, line_text in enumerate(value.split("\n")):
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        para.alignment = align
        para.space_after = Pt(4)
        run = para.add_run()
        run.text = line_text
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
    return item


def line(slide, x1, y1, x2, y2, color=LINE, width=1.2):
    item = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    item.line.color.rgb = rgb(color)
    item.line.width = Pt(width)
    return item


def dot(slide, x, y, diameter, fill):
    return shape(slide, MSO_SHAPE.OVAL, x, y, diameter, diameter, fill)


def base_slide(prs, dark=False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(NAVY if dark else PAPER)
    return slide


def heading(slide, section, title_text, subtitle=""):
    text(slide, section.upper(), 0.72, 0.34, 4.2, 0.22, 9, BLUE, True)
    text(slide, title_text, 0.72, 0.68, 11.9, 0.55, 25, NAVY, True)
    if subtitle:
        text(slide, subtitle, 0.74, 1.29, 11.6, 0.38, 11, MUTED)


def footer(slide, page, dark=False):
    fg = "91A8BF" if dark else "7D8B9A"
    rule = "35516B" if dark else LINE
    line(slide, 0.72, 7.06, 12.62, 7.06, rule, 0.75)
    text(slide, "TÜV SÜD  |  PPWR DIGITAL PLATFORM", 0.75, 7.12, 5.6, 0.18, 8, fg, True)
    text(slide, "CLIENT OVERVIEW  ·  2026.10", 8.82, 7.12, 3.2, 0.18, 8, fg, False, PP_ALIGN.RIGHT)
    text(slide, f"{page:02d}", 12.18, 7.105, 0.38, 0.2, 9, fg, True, PP_ALIGN.RIGHT)


def label(slide, value, x, y, w, fill=PALE, color=BLUE):
    box(slide, x, y, w, 0.3, fill, fill)
    text(slide, value, x + 0.08, y + 0.025, w - 0.16, 0.2, 9, color, True,
         PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)


def card_title(slide, title_text, x, y, w, color=INK):
    text(slide, title_text, x, y, w, 0.35, 15, color, True)


def bullet(slide, title_text, desc, x, y, w, accent=BLUE, title_color=INK, desc_color=MUTED):
    dot(slide, x, y + 0.06, 0.12, accent)
    text(slide, title_text, x + 0.23, y, w - 0.23, 0.27, 12, title_color, True)
    text(slide, desc, x + 0.23, y + 0.31, w - 0.25, 0.38, 9.5, desc_color)


def make_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    prs.core_properties.title = "PPWR 数字化平台 | 客户展示"
    prs.core_properties.subject = "PPWR 技术文档、欧盟符合性声明与合规工作流"
    prs.core_properties.author = "TÜV SÜD CPS CoE × HDL"
    prs.core_properties.keywords = "PPWR, TD, DoC, RAG, compliance"

    # 1. Cover
    s = base_slide(prs, True)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 0, 0.14, SH, BLUE)
    if LOGO.exists():
        s.shapes.add_picture(str(LOGO), Inches(0.78), Inches(0.62), width=Inches(0.46), height=Inches(0.46))
    text(s, "TÜV SÜD  ·  CPS CENTER OF EXCELLENCE", 1.38, 0.67, 5.8, 0.26, 10, "D8E8F6", True)
    label(s, "客户交流演示  /  CLIENT OVERVIEW", 0.82, 1.66, 2.65, "1E4261", "B7D8F5")
    text(s, "PPWR 数字化平台", 0.8, 2.25, 7.1, 0.8, 34, WHITE, True)
    text(s, "从包装数据到技术文档与符合性声明", 0.84, 3.14, 7.3, 0.48, 19, "C8D9E9", False)
    text(s, "结构化收集  ·  可追溯审核  ·  持续合规", 0.84, 3.86, 6.4, 0.35, 13, "69D0C3", True)
    nodes = [(8.45, 1.44, "BOM", BLUE), (10.08, 2.28, "证据", CYAN),
             (11.42, 3.46, "审核", YELLOW), (10.06, 4.62, "TD / DoC", BLUE2),
             (8.4, 5.38, "追踪", CYAN)]
    for i in range(len(nodes) - 1):
        line(s, nodes[i][0] + 0.43, nodes[i][1] + 0.4, nodes[i + 1][0] + 0.43,
             nodes[i + 1][1] + 0.4, "45627B", 1.1)
    for x, y, caption, color in nodes:
        dot(s, x, y, 0.84, color)
        text(s, caption, x - 0.16, y + 0.27, 1.15, 0.24, 10, NAVY if color == YELLOW else WHITE,
             True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(s, "基于 Regulation (EU) 2025/40", 0.84, 6.5, 5.2, 0.25, 10, "91A8BF")
    footer(s, 1, True)

    # 2. The operating challenge
    s = base_slide(prs)
    heading(s, "01  |  WHY DIGITAL", "把分散的合规工作，变成一条可追踪的工作流",
            "围绕 PPWR 技术文档（TD）与欧盟符合性声明（DoC）的资料准备、审查、交付和维护。")
    box(s, 0.72, 1.92, 5.45, 4.62, WHITE, LINE)
    card_title(s, "常见工作断点", 1.02, 2.22, 4.8)
    bullet(s, "资料分散", "邮件、表格和共享盘里的版本难以统一", 1.02, 2.82, 4.75, BLUE)
    bullet(s, "要求难映射", "包装层级、材料与法规条目需要逐项关联", 1.02, 3.66, 4.75, CYAN)
    bullet(s, "影响难定位", "供应商或证书变化后，受影响文件不易找全", 1.02, 4.50, 4.75, YELLOW)
    bullet(s, "响应有时限", "监管要求提供技术文档时，准备时间有限", 1.02, 5.34, 4.75, BLUE2)
    box(s, 6.42, 1.92, 6.18, 4.62, NAVY, NAVY)
    text(s, "平台把这些环节连起来", 6.82, 2.27, 5.3, 0.4, 19, WHITE, True)
    stages = [("登记", "包装 / BOM"), ("收集", "数据 / 证据"), ("审查", "规则 / 专家"), ("交付", "TD / DoC")]
    sx = 6.82
    for i, (name, desc) in enumerate(stages):
        bx = sx + i * 1.38
        dot(s, bx + 0.31, 3.15, 0.54, [BLUE, CYAN, YELLOW, BLUE2][i])
        text(s, str(i + 1), bx + 0.31, 3.29, 0.54, 0.18, 11, NAVY if i == 2 else WHITE,
             True, PP_ALIGN.CENTER)
        text(s, name, bx, 3.89, 1.18, 0.28, 13, WHITE, True, PP_ALIGN.CENTER)
        text(s, desc, bx - 0.05, 4.25, 1.3, 0.3, 9, "B9CADB", False, PP_ALIGN.CENTER)
        if i < len(stages) - 1:
            line(s, bx + 0.82, 3.42, bx + 1.32, 3.42, "7794AE", 1.1)
    line(s, 6.82, 4.93, 12.12, 4.93, "35516B", 0.8)
    text(s, "16 类要求", 6.84, 5.23, 1.55, 0.36, 18, WHITE, True)
    text(s, "73 项目录", 8.54, 5.23, 1.58, 0.36, 18, WHITE, True)
    text(s, "中英双语", 10.39, 5.23, 1.55, 0.36, 18, "69D0C3", True)
    text(s, "按包装单元组织，逐项记录证据、状态与来源。", 6.84, 5.83, 5.15, 0.3, 10, "B9CADB")
    footer(s, 2)

    # 3. End-to-end workflow
    s = base_slide(prs)
    heading(s, "02  |  END-TO-END", "从包装登记到持续合规，流程在一个项目里闭环",
            "客户团队与 TÜV SÜD 专家围绕同一份项目记录协作。")
    flow = [
        ("01", "建项目", "选择责任方\n与适用场景", BLUE),
        ("02", "建包装", "登记包装单元\n导入 BOM", CYAN),
        ("03", "判适用", "项目画像 ×\n材料组成", BLUE2),
        ("04", "交证据", "按条目提交\n资料与说明", YELLOW),
        ("05", "做审核", "规则预审 +\n专家决定", CYAN),
        ("06", "出文件", "生成 TD / DoC\n及资料包", BLUE),
        ("07", "管变更", "证书 / 法规\n变化追踪", BLUE2),
    ]
    start, gap, width = 0.72, 0.22, 1.52
    for i, (number, title_text, desc, accent) in enumerate(flow):
        x = start + i * (width + gap)
        box(s, x, 2.28, width, 2.35, WHITE, LINE)
        text(s, number, x + 0.16, 2.49, 0.5, 0.25, 10, accent, True)
        text(s, title_text, x + 0.16, 2.92, width - 0.32, 0.35, 15, NAVY, True)
        text(s, desc, x + 0.16, 3.5, width - 0.32, 0.68, 10, MUTED)
        if i < len(flow) - 1:
            line(s, x + width, 3.45, x + width + gap - 0.03, 3.45, BLUE2, 1.5)
    box(s, 0.72, 5.05, 11.94, 1.18, PALE_GREEN, PALE_GREEN)
    text(s, "共同工作方式", 1.02, 5.31, 1.8, 0.3, 13, "23845B", True)
    text(s, "客户准备包装信息与证据  →  平台检查完整性和关联关系  →  专家作出合规判断并把关文件",
         2.78, 5.27, 9.3, 0.38, 14, NAVY, True, valign=MSO_ANCHOR.MIDDLE)
    text(s, "所有 AI 输出均为辅助信息，不能替代专家审批或制造商责任。", 1.03, 5.75, 10.8, 0.24, 9, MUTED)
    footer(s, 3)

    # 4. Data model
    s = base_slide(prs)
    heading(s, "03  |  PACKAGING DATA", "让每一份证据，都能回到具体的包装与材料",
            "层级化标识贯穿 BOM、证据、审核记录与最终文件。")
    box(s, 0.72, 1.94, 7.0, 4.72, WHITE, LINE)
    card_title(s, "包装结构与追溯链", 1.03, 2.23, 5.7)
    levels = [
        ("PS-001", "包装系统", 1.12, BLUE),
        ("PU-001", "包装单元", 2.02, CYAN),
        ("PU-001-C001", "组件 / 材料", 2.92, BLUE2),
        ("…-TST-001", "测试证据", 3.82, YELLOW),
    ]
    for i, (code, name, y, accent) in enumerate(levels):
        box(s, 1.16 + i * 0.34, y, 4.88 - i * 0.64, 0.62, PALE if i < 3 else "FFF8DF", LINE)
        dot(s, 1.37 + i * 0.34, y + 0.19, 0.18, accent)
        text(s, code, 1.67 + i * 0.34, y + 0.16, 2.4, 0.25, 12, NAVY, True)
        text(s, name, 4.58 - i * 0.2, y + 0.17, 1.15, 0.22, 9, MUTED, False, PP_ALIGN.RIGHT)
        if i < len(levels) - 1:
            line(s, 1.54 + i * 0.34, y + 0.64, 1.54 + (i + 1) * 0.34, y + 0.88, "9CB2C7", 1.2)
    text(s, "支持手工登记，也支持 Excel BOM 导入。", 1.18, 5.28, 5.8, 0.27, 10, MUTED)
    text(s, "组件材料、质量、供应商和证书可关联检查。", 1.18, 5.7, 5.8, 0.27, 10, MUTED)
    box(s, 7.98, 1.94, 4.64, 2.16, NAVY, NAVY)
    label(s, "SCENARIO A", 8.28, 2.22, 1.25, "234A69", "B7D8F5")
    text(s, "按包装单元建档", 8.28, 2.73, 3.9, 0.34, 16, WHITE, True)
    text(s, "每个包装单元独立形成 TD 与 DoC，\n并提供文件包索引。", 8.29, 3.2, 3.8, 0.55, 10, "C5D7E6")
    box(s, 7.98, 4.34, 4.64, 2.32, PALE_GREEN, PALE_GREEN)
    label(s, "SCENARIO B", 8.28, 4.62, 1.25, "D6EFEA", "23845B")
    text(s, "合并建档", 8.28, 5.1, 3.9, 0.34, 16, NAVY, True)
    text(s, "一个 TD 汇总多个包装单元，\n适合包装制造商作为责任方的流程。", 8.29, 5.57, 3.8, 0.55, 10, MUTED)
    footer(s, 4)

    # 5. Review
    s = base_slide(prs)
    heading(s, "04  |  REVIEW", "把可自动核对的先交给规则，把专业判断留给专家",
            "平台的提交预审是确定性规则；它与知识问答中的 RAG 是两项不同能力。")
    box(s, 0.72, 1.97, 5.76, 4.62, WHITE, LINE)
    label(s, "第一道：规则式预审", 1.04, 2.25, 2.1, PALE, BLUE)
    text(s, "提交内容的结构化检查", 1.04, 2.78, 4.9, 0.35, 17, NAVY, True)
    checks = [
        ("字段与证据是否完整", "缺项提醒", BLUE),
        ("法规限值与申报值", "例如 Art 5(4) 重金属限值", CYAN),
        ("项目画像与适用性", "食品接触、材料、重复使用等", BLUE2),
        ("BOM 质量交叉核对", "与包装单元申报质量比较", YELLOW),
        ("报告时效与供应商证书", "超期或缺失时提示专家关注", CYAN),
    ]
    for i, (title_text, desc, accent) in enumerate(checks):
        bullet(s, title_text, desc, 1.06, 3.35 + i * 0.57, 4.95, accent)
    box(s, 6.8, 1.97, 5.82, 4.62, NAVY, NAVY)
    label(s, "第二道：专家复核", 7.12, 2.25, 1.85, "234A69", "B7D8F5")
    text(s, "有依据、有记录的最终决定", 7.12, 2.78, 4.9, 0.35, 17, WHITE, True)
    bullet(s, "批准 / 驳回 / 确认不适用", "问题可附评论并退回客户补充", 7.14, 3.45, 4.8, "69D0C3", WHITE, "C5D7E6")
    bullet(s, "检查结论带法规来源", "便于复核，也便于定位原始要求", 7.14, 4.36, 4.8, YELLOW, WHITE, "C5D7E6")
    bullet(s, "专家保留最终判断权", "AI 预审不构成合规批准", 7.14, 5.27, 4.8, BLUE2, WHITE, "C5D7E6")
    footer(s, 5)

    # 6. RAG assistant
    s = base_slide(prs)
    heading(s, "05  |  KNOWLEDGE ASSISTANT", "用 RAG 回答法规问题，并把答案连回来源",
            "支持中文与英文提问；结果标注引用，并区分法规要求与建议 / 良好实践。")
    box(s, 0.72, 2.02, 3.25, 3.95, NAVY, NAVY)
    label(s, "提问", 1.03, 2.34, 0.75, "234A69", "B7D8F5")
    text(s, "例如：\n食品接触包装的 PFAS\n需要哪些证据？", 1.04, 2.98, 2.55, 1.25, 17, WHITE, True)
    text(s, "按项目、包装单元或要求条目缩小检索范围。", 1.04, 4.76, 2.4, 0.68, 10, "C5D7E6")
    box(s, 4.25, 2.02, 4.85, 3.95, WHITE, LINE)
    card_title(s, "双路知识检索", 4.58, 2.34, 3.9)
    bullet(s, "精选知识池", "法规释义、标准、实施决定、解释与良好实践", 4.59, 2.97, 4.05, BLUE)
    bullet(s, "法规文件全文", "PDF / HTML 页面级提取、分段并保留页码", 4.59, 3.91, 4.05, CYAN)
    box(s, 4.59, 5.08, 4.1, 0.55, PALE, PALE)
    text(s, "BM25 排序  ·  中文分词扩展  ·  命中来源可追溯", 4.75, 5.22, 3.76, 0.22, 9, BLUE, True,
         PP_ALIGN.CENTER)
    box(s, 9.4, 2.02, 3.22, 3.95, PALE_GREEN, PALE_GREEN)
    card_title(s, "回答与边界", 9.72, 2.34, 2.5, "23845B")
    bullet(s, "本地回答", "不配置模型也可基于检索来源组织答案", 9.73, 2.98, 2.5, "23845B")
    bullet(s, "可选 LLM", "模型仅接收检索来源，并要求引用", 9.73, 3.98, 2.5, BLUE)
    text(s, "无可靠来源时明确提示咨询专家。", 9.74, 5.22, 2.52, 0.45, 9, MUTED, True)
    text(s, "RAG 用于知识问答与动态指引；条目提交预审仍由确定性规则执行。", 1.03, 6.31, 11.2, 0.28, 11, NAVY, True)
    footer(s, 6)

    # 7. Deliverables
    s = base_slide(prs)
    heading(s, "06  |  DOCUMENTS", "审核结果直接沉淀为可交付的文件与证据包",
            "生成内容按法规结构组织，并保留版本和草稿状态。")
    cards = [
        (0.74, BLUE, "TD", "技术文档", "依 Annex VII\nT00 / T01、§1–§21\n附录 A / B"),
        (4.52, CYAN, "DoC", "欧盟符合性声明", "依 Art 39 与 Annex VIII\n覆盖声明要素\n由制造商签署"),
        (8.3, YELLOW, "ZIP", "监管资料包", "TD + DoC + 证据文件\n按目录打包\n支持响应监管要求"),
    ]
    for x, accent, code, title_text, desc in cards:
        box(s, x, 2.18, 3.56, 3.1, WHITE, LINE)
        box(s, x + 0.28, 2.49, 0.78, 0.58, accent, accent)
        text(s, code, x + 0.31, 2.66, 0.72, 0.22, 12, NAVY if accent == YELLOW else WHITE,
             True, PP_ALIGN.CENTER)
        text(s, title_text, x + 0.29, 3.39, 2.95, 0.34, 17, NAVY, True)
        text(s, desc, x + 0.29, 3.94, 2.98, 0.93, 11, MUTED)
    box(s, 0.74, 5.65, 11.12, 0.71, "FFF8DF", "F0E3B1")
    text(s, "未达到就绪条件时显示 DRAFT / OPEN；平台不代替制造商签署 DoC。",
         1.03, 5.86, 10.45, 0.28, 12, NAVY, True, PP_ALIGN.CENTER)
    text(s, "监管要求提供技术文档的时限可能为 10 天；资料包旨在帮助提高准备效率，不构成时限保证。",
         1.02, 6.53, 11.1, 0.22, 9, MUTED)
    footer(s, 7)

    # 8. Ongoing compliance
    s = base_slide(prs)
    heading(s, "07  |  CHANGE & MONITORING", "变化发生时，沿影响链找到需要复核的内容",
            "把供应商证书、材料变化和法规更新，关联到项目条目与输出文件。")
    flow = [("供应商材料", "证书 / 成分", BLUE), ("组件", "BOM 关系", CYAN),
            ("包装单元", "PU / 项目", BLUE2), ("要求条目", "重开复核", YELLOW),
            ("TD / DoC", "标记待更新", CYAN)]
    for i, (title_text, detail, accent) in enumerate(flow):
        x = 0.78 + i * 2.48
        box(s, x, 2.28, 2.02, 1.18, WHITE, LINE)
        dot(s, x + 0.17, 2.48, 0.2, accent)
        text(s, title_text, x + 0.48, 2.43, 1.38, 0.26, 12, NAVY, True)
        text(s, detail, x + 0.2, 2.88, 1.62, 0.22, 9, MUTED)
        if i < len(flow) - 1:
            line(s, x + 2.03, 2.88, x + 2.39, 2.88, "89A6BF", 1.35)
    box(s, 0.78, 4.12, 5.75, 1.86, PALE, PALE)
    label(s, "证书生命周期", 1.08, 4.4, 1.5, "DDEBFA", BLUE)
    text(s, "30 天到期提醒", 1.08, 4.91, 2.35, 0.36, 17, NAVY, True)
    text(s, "材料与供应商证书集中管理；到期提醒帮助团队提前跟进。", 1.08, 5.4, 4.9, 0.35, 10, MUTED)
    box(s, 6.85, 4.12, 5.73, 1.86, PALE_GREEN, PALE_GREEN)
    label(s, "法规监控", 7.15, 4.4, 1.1, "D6EFEA", "23845B")
    text(s, "更新待专家确认", 7.15, 4.91, 2.8, 0.36, 17, NAVY, True)
    text(s, "文件变化可映射到法规与条目；影响摘要进入专家复核流程。", 7.15, 5.4, 4.9, 0.35, 10, MUTED)
    text(s, "变更影响分析辅助识别范围；最终适用性和文件更新仍需责任人确认。", 1.08, 6.39, 10.9, 0.23, 9, MUTED, True)
    footer(s, 8)

    # 9. Guidance and import
    s = base_slide(prs)
    heading(s, "08  |  CLIENT EXPERIENCE", "让客户知道交什么、如何交，以及为什么要交",
            "双语界面、动态证据指引与智能导入，降低资料准备过程中的沟通成本。")
    features = [
        (0.74, BLUE, "01", "动态证据指南", "按法规级别、适用性与适用日期\n显示必需、建议或良好实践。\n提供格式、验收标准与示例。"),
        (4.52, CYAN, "02", "智能导入", "从文件名、内容和目录识别\n文件类型与可能的条目归属。\n导入前先进入暂存复核。"),
        (8.3, YELLOW, "03", "中英双语", "界面、要求说明与知识问答\n支持中文和英文协作。\n法规来源与建议分开呈现。"),
    ]
    for x, accent, no, title_text, desc in features:
        box(s, x, 2.21, 3.56, 2.85, WHITE, LINE)
        text(s, no, x + 0.3, 2.52, 0.5, 0.3, 11, accent, True)
        text(s, title_text, x + 0.3, 3.03, 2.95, 0.37, 17, NAVY, True)
        text(s, desc, x + 0.3, 3.65, 2.98, 1.0, 10, MUTED)
    box(s, 0.74, 5.42, 11.12, 0.84, "FFF8DF", "F0E3B1")
    text(s, "试点说明", 1.02, 5.69, 1.0, 0.24, 10, "8B6810", True)
    text(s, "当前不含 OCR：扫描件和图片主要按文件名识别，关键内容仍需人工确认。",
         2.0, 5.64, 9.4, 0.32, 12, NAVY, True)
    footer(s, 9)

    # 10. Boundaries and next step
    s = base_slide(prs, True)
    text(s, "09  |  PILOT TO PRODUCTION", 0.75, 0.42, 5.5, 0.24, 9, "69D0C3", True)
    text(s, "从代表性项目试点，逐步接入企业运行环境", 0.75, 0.84, 11.8, 0.56, 25, WHITE, True)
    text(s, "先验证流程与数据，再按企业要求规划生产化。", 0.78, 1.48, 10.4, 0.32, 12, "C5D7E6")
    box(s, 0.78, 2.18, 5.62, 3.72, "183B59", "35516B")
    card_title(s, "当前试点版本", 1.1, 2.5, 4.8, WHITE)
    bullet(s, "本地数据库与文件存储", "适合演示和受控试点", 1.11, 3.15, 4.65, "69D0C3", WHITE, "C5D7E6")
    bullet(s, "可选模型服务", "不配置 LLM 时，知识问答仍可本地生成", 1.11, 4.05, 4.65, YELLOW, WHITE, "C5D7E6")
    bullet(s, "专家保持最终决定权", "AI 内容为辅助，DoC 由制造商签署", 1.11, 4.95, 4.65, BLUE2, WHITE, "C5D7E6")
    box(s, 6.82, 2.18, 5.72, 3.72, "183B59", "35516B")
    card_title(s, "生产化评估重点", 7.15, 2.5, 4.8, WHITE)
    bullet(s, "企业身份与权限", "对接 SSO、角色及审计要求", 7.16, 3.15, 4.75, "69D0C3", WHITE, "C5D7E6")
    bullet(s, "数据与运行环境", "对象存储、服务端数据库、备份和监控", 7.16, 4.05, 4.75, YELLOW, WHITE, "C5D7E6")
    bullet(s, "业务集成与治理", "接口、法规维护、模型和数据治理", 7.16, 4.95, 4.75, BLUE2, WHITE, "C5D7E6")
    text(s, "建议下一步：选取 1–2 个代表性包装项目，验证 BOM、证据、审查和文件交付的完整路径。",
         0.82, 6.28, 11.4, 0.35, 13, WHITE, True)
    footer(s, 10, True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    return prs


if __name__ == "__main__":
    presentation = make_deck()
    print(f"Created {OUTPUT} with {len(presentation.slides)} slides")