"""Build the shareable team PDF from the reviewed Markdown source. Development dependency: reportlab."""
from pathlib import Path
from html import escape
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
for name, file in [('Arial','arial.ttf'),('ArialBold','arialbd.ttf')]:
    pdfmetrics.registerFont(TTFont(name, 'C:/Windows/Fonts/'+file))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='ArialBold', italic='Arial', boldItalic='ArialBold')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle('BodyGuide',fontName='Arial',fontSize=10.5,leading=14.5,spaceAfter=9,textColor=colors.HexColor('#24343c')))
styles.add(ParagraphStyle('SectionGuide',fontName='ArialBold',fontSize=23,leading=27,spaceAfter=18,textColor=colors.black))
styles.add(ParagraphStyle('SubGuide',fontName='ArialBold',fontSize=12.5,leading=16,spaceBefore=8,spaceAfter=7,textColor=colors.black))
styles.add(ParagraphStyle('CodeGuide',fontName='Courier',fontSize=8.4,leading=12,spaceAfter=10))
def rich(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', text)
story=[]
lines=(ROOT/'docs/team-presentation-guide.md').read_text(encoding='utf-8').splitlines()
paragraph=[]
def flush():
    if paragraph:
        story.append(Paragraph(rich(' '.join(paragraph)),styles['BodyGuide']))
        paragraph.clear()
i=0
while i<len(lines):
    line=lines[i].strip();i+=1
    if not line: flush();continue
    if line=='---': flush();story.append(PageBreak());continue
    if line.startswith('```'):
        flush(); code=[]
        while i<len(lines) and not lines[i].startswith('```'):
            code.append(lines[i]);i+=1
        i+=1
        story.append(Preformatted('\n'.join(code),styles['CodeGuide']));continue
    if line.startswith('!['):
        flush();shot=ROOT/'docs/assets/presentation-machine.png'
        if shot.exists(): story.extend([Spacer(1,5),Image(str(shot),width=400,height=289),Spacer(1,9)])
        continue
    if line.startswith('# '): flush();story.append(Paragraph(rich(line[2:]),styles['SectionGuide']));continue
    if line.startswith('## '): flush();story.append(Paragraph(rich(line[3:]),styles['SubGuide']));continue
    paragraph.append(line)
flush()

def page_frame(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#c9d1d1'));canvas.line(48,751,564,751)
    canvas.setFont('Arial',8);canvas.setFillColor(colors.HexColor('#596b74'))
    canvas.drawString(48,763,'FIELDWORK  /  MANUFACTURING TRACK 02')
    canvas.drawRightString(564,763,'TEAM PRESENTATION GUIDE')
    canvas.drawString(48,28,'Synthetic data  /  Simulated actions  /  October 23 2026')
    canvas.drawRightString(564,28,str(doc.page))
    canvas.restoreState()

doc=SimpleDocTemplate(str(OUT/'manufacturing-team-presentation-guide.pdf'),pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=60,bottomMargin=48,title='Manufacturing maintenance demo team presentation guide',author='Manufacturing Track 2 team')
doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
print(OUT/'manufacturing-team-presentation-guide.pdf')
