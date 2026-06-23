<<<<<<< HEAD
cat ~/anketa_bot/pdf_generator.py
=======
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

def generate_pdf(answers, questions, output_path, patient_name, date_str):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm)
    t_style = ParagraphStyle("T", fontSize=14, alignment=1, spaceAfter=4*mm)
    q_style = ParagraphStyle("Q", fontSize=9, spaceAfter=1*mm)
    a_style = ParagraphStyle("A", fontSize=11, leftIndent=4*mm, spaceAfter=4*mm)
    story = []
    story.append(Paragraph("ANKETA PATSIENTA", t_style))
    story.append(Paragraph(f"Patsient: {patient_name} Data: {date_str}", t_style))
    story.append(Spacer(1, 6*mm))
    for key, question in questions:
        if key not in answers:
            continue
        answer = answers.get(key, "-") or "-"
        story.append(Paragraph(question, q_style))
        story.append(Paragraph(answer, a_style))
    doc.build(story)
>>>>>>> 289e3af (first commit)
