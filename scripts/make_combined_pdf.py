#!/usr/bin/env python3
"""把 agent-redteam-lab 的 4 份 markdown 报告合成为一份专业中文 PDF。
用法: ~/.pdfvenv/bin/python make_combined_pdf.py
"""
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc"
pdfmetrics.registerFont(TTFont("CJK", FONT_DIR, subfontIndex=0))
pdfmetrics.registerFont(TTFont("CJKB", FONT_DIR, subfontIndex=1))

BASE = Path("/home/d0ge/agent-redteam-lab/attack-reports")
OUT = Path("/home/d0ge/agent-redteam-lab/综合文档/AI_Agent_红队测试综合报告.pdf")

DOCS = [
    ("报告_漏洞分析_定稿.md", "Part 1 · 漏洞分析报告（定稿）"),
    ("加固前后对比报告.md",   "Part 2 · 加固前后对比（攻防闭环）"),
    ("agent_redteam_report.md", "附录A · 加固前 · 攻击原始数据"),
    ("加固后_攻击原始数据.md", "附录B · 加固后 · 攻击原始数据"),
]

# --- 样式 ---
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1c", parent=ss["Heading1"], fontName="CJKB", fontSize=22,
                    leading=28, textColor=colors.HexColor("#1a3a5c"), spaceAfter=6)
H2 = ParagraphStyle("H2c", parent=ss["Heading2"], fontName="CJKB", fontSize=15,
                    leading=20, textColor=colors.HexColor("#1a3a5c"), spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3c", parent=ss["Heading3"], fontName="CJKB", fontSize=12.5,
                    leading=17, textColor=colors.HexColor("#2a5a8c"), spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontName="CJK", fontSize=10.5,
                      leading=16, alignment=TA_LEFT, spaceAfter=2)
BUL = ParagraphStyle("BUL", parent=ss["Bullet"], fontName="CJK", fontSize=10.5,
                     leading=15, leftIndent=14, bulletIndent=4, spaceAfter=2)
SMALL = ParagraphStyle("SMALL", parent=ss["BodyText"], fontName="CJK", fontSize=9,
                       leading=13, textColor=colors.HexColor("#555555"))

COVER_TITLE = ParagraphStyle("COVER", fontName="CJKB", fontSize=30, leading=38,
                             alignment=TA_CENTER, textColor=colors.HexColor("#1a3a5c"))
COVER_SUB = ParagraphStyle("COVERSUB", fontName="CJK", fontSize=14, leading=20,
                           alignment=TA_CENTER, textColor=colors.HexColor("#555555"))


def esc(t):
    """转义 reportlab Paragraph 的特殊字符。"""
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return t


def add_header_footer(canvas, doc):
    canvas.saveState()
    w, h = canvas._pagesize
    if doc.page > 1:
        canvas.setFont("CJK", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(20 * mm, h - 14 * mm, "AI Agent 红队测试综合报告")
        canvas.drawRightString(w - 20 * mm, h - 14 * mm, f"第 {doc.page} 页")
        canvas.setLineWidth(0.5)
        canvas.setStrokeColor(colors.HexColor("#cccccc"))
        canvas.line(20 * mm, h - 16 * mm, w - 20 * mm, h - 16 * mm)
        canvas.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
    canvas.restoreState()


def render_md(md_text, story):
    """把 markdown 文本解析成 reportlab flowables。"""
    lines = md_text.split("\n")
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i].rstrip()

        # 代码块
        if line.strip().startswith("```"):
            if in_code:
                story.append(Spacer(1, 4))
                in_code = False
            else:
                story.append(Spacer(1, 4))
                in_code = True
            i += 1
            continue
        if in_code:
            story.append(Paragraph(esc(line) or "&nbsp;",
                        ParagraphStyle("code", fontName="CJK", fontSize=8.5, leading=11,
                                       leftIndent=10, textColor=colors.HexColor("#333333"),
                                       backColor=colors.HexColor("#f0f0f0"))))
            i += 1
            continue

        s = line.strip()
        if not s:
            i += 1
            continue
        # 水平分隔
        if re.match(r"^[-*_]{3,}$", s):
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#cccccc")))
            story.append(Spacer(1, 6))
            i += 1
            continue
        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            lvl, txt = len(m.group(1)), esc(m.group(2))
            txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
            if lvl == 1:
                story.append(Paragraph(txt.split("：")[0] or txt, H1))
            elif lvl == 2:
                story.append(Paragraph(txt, H2))
            else:
                story.append(Paragraph(txt, H3))
            i += 1
            continue
        # 列表
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            item = esc(m.group(1))
            item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
            story.append(Paragraph(item, BUL, bulletText="•"))
            i += 1
            continue
        # 有序列表
        m = re.match(r"^\d+[.、]\s+(.*)$", s)
        if m:
            item = esc(m.group(1))
            item = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item)
            story.append(Paragraph(item, BUL, bulletText="·"))
            i += 1
            continue
        # 加粗单行
        m = re.fullmatch(r"\*\*(.+?)\*\*", s)
        if m:
            story.append(Paragraph(f"<b>{esc(m.group(1))}</b>", BODY))
            i += 1
            continue
        # 普通段落（处理行内加粗/反引号/内联代码）
        txt = esc(s)
        txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
        txt = re.sub(r"`([^`]+)`", r"<font name='CJK' color='#a00'>\1</font>", txt)
        story.append(Paragraph(txt, BODY))
        i += 1


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=24 * mm, rightMargin=24 * mm,
        topMargin=24 * mm, bottomMargin=22 * mm,
        title="AI Agent 红队测试综合报告",
        author="AI Security Portfolio",
    )
    story = []

    # --- 封面 ---
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("AI Agent 红队测试", COVER_TITLE))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("综合报告", COVER_TITLE))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph("攻击发现 · 防御加固 · 攻防闭环验证", COVER_SUB))
    story.append(Spacer(1, 40 * mm))
    meta = [
        ["测试对象", "多权限工具 AI Agent（文件 / 数据库 / SQL / 网络）"],
        ["推理模型", "cohere/north-mini-code:free（OpenRouter）"],
        ["测试方式", "黑盒攻击 + 工具层验证 + 人工复核"],
        ["测试环境", "全 Docker 容器隔离（lab_internal 网络）"],
        ["测试日期", "2026-09-05"],
    ]
    tbl = Table(meta, colWidths=[45 * mm, 95 * mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "CJK"),
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a3a5c")),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#dddddd")),
    ]))
    story.append(tbl)
    story.append(PageBreak())

    # --- 目录 ---
    story.append(Paragraph("目录", H1))
    toc = []
    for fn, title in DOCS:
        part = title.split("·")[0].strip()
        toc.append(Paragraph(f"<b>{esc(title)}</b>", BODY))
    for t in toc:
        story.append(t)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#cccccc")))
    story.append(PageBreak())

    # --- 正文 ---
    for fn, title in DOCS:
        text = (BASE / fn).read_text(encoding="utf-8")
        story.append(Paragraph(esc(title), H1))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")))
        story.append(Spacer(1, 6))
        render_md(text, story)
        story.append(PageBreak())

    # --- 附注 ---
    story.append(Paragraph("附注", H2))
    story.append(Paragraph(
        "本综合报告为 AI Agent 安全攻防测试作品集核心素材。所有攻击在完全隔离的 Docker 容器环境内进行，"
        "全程未接触宿主机与其他容器，所有数据均为靶场虚构。测试方法（隔离环境 + 工具化 agent + 自动化攻击 + "
        "人工复核）与 OpenAI / Anthropic 等主流 AI 公司验证 Agent 安全所用方法论同源。", BODY))

    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print(f"PDF 生成成功: {OUT}")
    print(f"页面数: {doc.page}")


if __name__ == "__main__":
    build()
