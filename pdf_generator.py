from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

pdfmetrics.registerFont(TTFont("DejaVu", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))BLOCKS = {
    "давление_паспорт": "ПАСПОРТ ЗДОРОВЬЯ",
    "фио": "БЛОК 1. Личные данные и стратегия",
    "энергия_утро": "БЛОК 2. Сон и психоэмоциональный статус",
    "тип_питания": "БЛОК 3. Питание и ЖКТ",
    "мёрзнут_руки": "БЛОК 4. Эндокринология и метаболизм",
    "давление": "БЛОК 5. Кардиология и сосуды",
    "тип_кожи": "БЛОК 6. Дерматология",
    "косметология": "БЛОК 7. Косметология",
    "спорт": "БЛОК 8. Движение и образ жизни",
    "мышечная_сила": "БЛОК 9. Функциональный возраст",
    "зубы": "БЛОК 10. Стоматология и ЛОР",
    "тазовое_дно": "БЛОК 11. Гинекология / Урология",
    "препараты": "БЛОК 12. Препараты и нутрицевтики",
    "экология": "БЛОК 13. Экология и быт",
    "хронические_диагнозы": "БЛОК 14. История болезней",
}

def clean_text(text):
    emojis = ["📋","👤","🧠","🥗","🌡️","❤️","✨","💉","🏃","👴","🦷","👩","💊","🌿","📁","🎯","📊","👋"]
    for e in emojis:
        text = text.replace(e, "")
    return text.split("\n")[0].strip()def generate_pdf(answers, questions, output_path, patient_name, date_str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    title_style = ParagraphStyle("T", fontName="DejaVu-Bold", fontSize=15,
        alignment=TA_CENTER, spaceAfter=3*mm, textColor=colors.HexColor("#1a1a2e"))
    subtitle_style = ParagraphStyle("S", fontName="DejaVu", fontSize=10,
        alignment=TA_CENTER, spaceAfter=2*mm, textColor=colors.HexColor("#B8860B"))
    patient_style = ParagraphStyle("P", fontName="DejaVu-Bold", fontSize=12,
        alignment=TA_CENTER, spaceAfter=2*mm, textColor=colors.HexColor("#1a1a2e"))
    block_style = ParagraphStyle("B", fontName="DejaVu-Bold", fontSize=11,
        spaceAfter=2*mm, spaceBefore=5*mm, textColor=colors.HexColor("#1a1a2e"),
        backColor=colors.HexColor("#F0EDE0"), leftIndent=3*mm, borderPad=2*mm)
    question_style = ParagraphStyle("Q", fontName="DejaVu-Bold", fontSize=8,
        spaceAfter=1*mm, spaceBefore=3*mm, textColor=colors.HexColor("#666666"),
        leftIndent=4*mm)
    answer_style = ParagraphStyle("A", fontName="DejaVu", fontSize=10,
        spaceAfter=1*mm, textColor=colors.HexColor("#1a1a2e"), leftIndent=7*mm)story = []
    story.append(Paragraph("МАСТЕР-АНКЕТА СИСТЕМНОГО АУДИТА", title_style))
    story.append(Paragraph("ДОЛГОЛЕТИЯ И ОМОЛОЖЕНИЯ", title_style))
    story.append(Paragraph("Золотой стандарт Anti-Age и Превентивной Медицины v2.0", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#B8860B")))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"Пациент: {patient_name}", patient_style))
    story.append(Paragraph(f"Дата заполнения: {date_str}", patient_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CCCCCC")))
    story.append(Spacer(1, 5*mm))
    current_block = None
    for key, question in questions:
        if key not in answers:
            continue
        answer = answers.get(key, "-") or "-"
        if key in BLOCKS and BLOCKS[key] != current_block:
            current_block = BLOCKS[key]
            story.append(Spacer(1, 2*mm))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#B8860B")))
            story.append(Paragraph(current_block, block_style))
        clean_q = clean_text(question)
        story.append(Paragraph(clean_q, question_style))
        story.append(Paragraph(str(answer), answer_style))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#B8860B")))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Документ сформирован автоматически - Anti-Age аудит v2.0", subtitle_style))
    doc.build(story)
EOFcd ~/anketa_bot && git add . && git commit -m "fix font paths" && git push -f origin main
