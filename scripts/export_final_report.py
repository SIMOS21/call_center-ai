"""Export the existing report as an explicitly paginated, verifiable PDF."""
import html
import json
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from pypdf import PdfReader


def main():
    output = Path("output/pdf")
    output.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Report", "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("ReportBold", "C:/Windows/Fonts/arialbd.ttf"))
    styles = {
        "body": ParagraphStyle("body", fontName="Report", fontSize=10, leading=14, spaceAfter=9, alignment=TA_LEFT),
        "title": ParagraphStyle("title", fontName="ReportBold", fontSize=19, leading=24, spaceAfter=18, textColor=colors.HexColor("#15324c")),
        "small": ParagraphStyle("small", fontName="Report", fontSize=8, leading=11, spaceAfter=6),
    }
    def p(text, style="body"):
        text = text.replace("—", "-").replace("–", "-").replace("\u2011", "-")
        escaped = html.escape(text)
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
        escaped = escaped.replace("`", "")
        return Paragraph(escaped, styles[style])
    text = Path("docs/RAPPORT_TECHNIQUE.md").read_text(encoding="utf-8")
    sections = re.split(r"\n## (?=\d+\.)", text)[1:]
    assert len(sections) == 10
    story = []
    for index, section in enumerate(sections):
        title, body = section.split("\n", 1)
        if index:
            story.append(PageBreak())
        story.append(p("COMMERCEOPS AI / PROJET 3 ENSAF", "small"))
        story.append(p(title, "title"))
        if index == 0:
            story.append(p("Audit du 12 novembre 2026 : livraison PARTIAL. Rotation confirmée par l'utilisateur ; évaluation humaine et vidéo non attestées. Les résultats guidés historiques ne constituent pas une mesure indépendante.", "small"))
        if index == 1:
            diagram = Drawing(460, 105)
            labels = [(0, 65, "Streamlit"), (115, 65, "FastAPI / Agent"), (290, 65, "Medusa / PostgreSQL"), (115, 10, "RAG ABCD"), (290, 10, "SQLite / MLflow")]
            for x, y, label in labels:
                diagram.add(Rect(x, y, 108 if x < 290 else 165, 30, fillColor=colors.HexColor("#e8f1f7"), strokeColor=colors.HexColor("#315b75")))
                diagram.add(String(x+7, y+11, label, fontName="Report", fontSize=9))
            for x1,y1,x2,y2 in [(108,80,115,80),(223,80,290,80),(169,65,169,40),(223,75,290,30)]:
                diagram.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor("#315b75")))
            story.extend([diagram, Spacer(1, 10)])
        for paragraph in body.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if paragraph.startswith("|"):
                lines = [line for line in paragraph.splitlines() if line.startswith("|") and not re.match(r"\|[\s:|\-]+$", line)]
                cells = [[p(cell.strip(), "small") for cell in line.strip("|").split("|")] for line in lines]
                table = Table(cells, colWidths=[460/len(cells[0])]*len(cells[0]))
                table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f1f7")),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),.3,colors.lightgrey)]))
                story.extend([table, Spacer(1,10)])
            else:
                story.append(p(paragraph.replace("\n", " ")))
        if index == 9:
            story.append(p("Compléments audit final : logs Python 3.14 et reproduction propre Python 3.12 dans reports/final-audit/. Jeu distinct gelé de 16 cas : revue humaine non attestée, mesures de récupération provisoires uniquement. Captures Admin/CI et vidéo non disponibles dans cette exportation.", "small"))
    target = output/"CommerceOps_AI_Rapport_Final.pdf"
    def footer(canvas, doc):
        canvas.setFont("Report", 8)
        canvas.drawString(43, 27, "CommerceOps AI - Audit final - 12 novembre 2026")
        canvas.drawRightString(552, 27, str(doc.page))
    SimpleDocTemplate(str(target), pagesize=(595.28,841.89), leftMargin=45,rightMargin=45,topMargin=38,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    pages = len(PdfReader(target).pages)
    assert 8 <= pages <= 12, pages
    Path("reports/final-audit/pdf-validation.json").write_text(json.dumps({"path":str(target),"pages":pages,"visual_review":"PENDING"},indent=2),encoding="utf-8")
    print("PDF pages:",pages)
    import fitz
    document = fitz.open(target)
    from PIL import Image
    previews=[]
    for number,page in enumerate(document):
        pix=page.get_pixmap(matrix=fitz.Matrix(.8,.8))
        pic=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
        previews.append(pic)
    sheet=Image.new("RGB",(previews[0].width*5,previews[0].height*3),"#cccccc")
    for i,pic in enumerate(previews):
        sheet.paste(pic,((i%5)*pic.width,(i//5)*pic.height))
    sheet.save("reports/final-audit/pdf-contact-sheet.png")


if __name__ == "__main__":
    main()
