"""Build the ASUR Lyric-Video beginner guide PDF (reportlab, no external assets)."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)

OUT = "/Users/user/code security 10/asur/lyric_video_guide/ASUR-Lyric-Video-Guide.pdf"

INK = colors.HexColor("#14202b")
RED = colors.HexColor("#d7263d")
BLUE = colors.HexColor("#1b4965")
SOFT = colors.HexColor("#5d6b76")
BG = colors.HexColor("#eef3f6")
GATE = colors.HexColor("#f2b705")
GREEN = colors.HexColor("#2a9d4a")

styles = getSampleStyleSheet()


def S(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


H1 = S("H1", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK, spaceAfter=6)
H2 = S("H2", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=RED, spaceBefore=14, spaceAfter=6)
SUB = S("SUB", fontName="Helvetica", fontSize=12, leading=16, textColor=SOFT, spaceAfter=10)
BODY = S("BODY", fontName="Helvetica", fontSize=11, leading=16, textColor=INK, spaceAfter=6)
BOLD = S("BOLD", parent=BODY, fontName="Helvetica-Bold")
MONO = S("MONO", fontName="Courier", fontSize=10, leading=14, textColor=BLUE)
CELL = S("CELL", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
CELLB = S("CELLB", parent=CELL, fontName="Helvetica-Bold")
HEAD = S("HEAD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
NODE = S("NODE", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white, alignment=TA_CENTER)
NODESUB = S("NODESUB", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.white, alignment=TA_CENTER)


class TreeNode(Flowable):
    """A top-down family tree of the lyric-video pipeline."""

    def __init__(self, width=175 * mm, height=235 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, c, cx, top, w, h, fill, title, sub):
        x = cx - w / 2.0
        y = top - h
        c.setFillColor(fill)
        c.setStrokeColor(colors.white)
        c.setLineWidth(0)
        c.roundRect(x, y, w, h, 5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx, y + h - 13, title)
        if sub:
            c.setFont("Helvetica", 7.3)
            lines = sub.split("\n")
            yy = y + h - 24
            for ln in lines:
                c.drawCentredString(cx, yy, ln)
                yy -= 9
        return y  # bottom of box

    def _arrow(self, c, cx, y_from, y_to):
        c.setStrokeColor(SOFT)
        c.setLineWidth(1.4)
        c.line(cx, y_from, cx, y_to + 4)
        c.setFillColor(SOFT)
        p = c.beginPath()
        p.moveTo(cx - 3.5, y_to + 6)
        p.lineTo(cx + 3.5, y_to + 6)
        p.lineTo(cx, y_to)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def draw(self):
        c = self.canv
        cx = self.width / 2.0
        top = self.height
        w = 120 * mm
        gap = 11 * mm

        rows = [
            (BLUE, "YOU GIVE 2 FILES", "song.mp3  +  lyrics.txt", 22 * mm),
            (INK, "STAGE 0  -  Inspect", "checks the 2 files are readable", 17 * mm),
            (INK, "STAGE 1  -  Word Timing", "word-timestamps.json + phrases.json\n+ confidence report  (you review)", 20 * mm),
            (INK, "STAGE 2  -  Sync Test", "sync-test.mp4  (plain words on beat)\nyou confirm timing is right", 20 * mm),
            (INK, "STAGE 3  -  Creative Direction", "creative-direction.md + visual-screenplay.json\n+ beat-map.json  (you review the plan)", 20 * mm),
            (GATE, "STAGE 4  -  HERO PROOF  (approval gate)", "hero-proof.mp4 (5 sec, full quality)\n+ 8 preview frames  ->  YOU APPROVE", 21 * mm),
            (INK, "STAGE 5  -  Full Render", "section by section on the same engine", 17 * mm),
            (GREEN, "FINAL VIDEO", "final-lyric-video.mp4  (1080x1920, 9:16)", 20 * mm),
        ]

        y = top
        prev_bottom = None
        for fill, title, sub, h in rows:
            if prev_bottom is not None:
                self._arrow(c, cx, prev_bottom, y)
                y -= gap
            bottom = self._box(c, cx, y, w, h, fill, title, sub)
            prev_bottom = bottom
            y = bottom


def para(text, style=BODY):
    return Paragraph(text, style)


def build():
    doc = BaseDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="ASUR Lyric Video - Simple Guide",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    story = []

    # ---- Page 1: cover + what you give ----
    story.append(Spacer(1, 6))
    story.append(para("ASUR", S("brand", fontName="Helvetica-Bold", fontSize=34, textColor=RED, leading=36)))
    story.append(para("Make a Lyric Video - the simple guide", H1))
    story.append(para("What you give, how to start, and where every result lands.", SUB))

    story.append(para("1. What you give ASUR", H2))
    story.append(para("Just <b>two files</b>. Nothing else. Put them inside the ASUR folder, or tell ASUR where they are.", BODY))

    give = Table(
        [
            [para("FILE", HEAD), para("WHAT IT IS", HEAD), para("EXAMPLE PATH", HEAD)],
            [
                para("1) the song", CELL),
                para("Your full song, any mix. ASUR pulls the vocals out itself.", CELL),
                para("/Users/you/.../asur/song.mp3", MONO),
            ],
            [
                para("2) the words", CELL),
                para("A plain text file - one lyric line per line. Hindi, English, Hinglish, Marathi or mixed all work.", CELL),
                para("/Users/you/.../asur/lyrics.txt", MONO),
            ],
        ],
        colWidths=[26 * mm, 72 * mm, 76 * mm],
    )
    give.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d4db")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(give)
    story.append(Spacer(1, 10))

    story.append(para("The two rules about these files", BOLD))
    story.append(para("- <b>lyrics.txt is the truth about the WORDS.</b> ASUR never guesses or rewrites your lyrics.", BODY))
    story.append(para("- <b>The song is the truth about the TIMING.</b> ASUR listens to the real singing to place each word.", BODY))

    story.append(Spacer(1, 8))
    story.append(para("Example lyrics.txt (one line per lyric line):", BOLD))
    ex = Table(
        [[para(
            "Pyaar kya hai, koi batao<br/>"
            "Dil ne phir se dhokha khaaya<br/>"
            "Raat bhar main soch raha tha<br/>"
            "Kya tha woh jo tune chaaha",
            MONO,
        )]],
        colWidths=[174 * mm],
    )
    ex.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1b1b1b")),
                            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                            ("TOPPADDING", (0, 0), (-1, -1), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(ex)

    story.append(para("2. How to start", H2))
    story.append(para("Open ASUR in this folder and just say, in plain words:", BODY))
    startbox = Table([[para('"Make a lyric video from song.mp3 and lyrics.txt."', MONO)]], colWidths=[174 * mm])
    startbox.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG),
                                  ("BOX", (0, 0), (-1, -1), 1, RED),
                                  ("TOPPADDING", (0, 0), (-1, -1), 9),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(startbox)
    story.append(Spacer(1, 6))
    story.append(para("ASUR then walks the 6 stages below. It <b>stops and shows you something to look at</b> at the key moments - you are always in control. Nothing is ever posted anywhere.", BODY))

    story.append(PageBreak())

    # ---- Page 2: the 6 stages table ----
    story.append(para("3. The complete process - 6 stages", H1))
    story.append(para("Each stage ends in something you can watch or read. You approve, then it moves on.", SUB))

    rows = [
        [para("STAGE", HEAD), para("WHAT IT DOES", HEAD), para("WHAT YOU GET / DO", HEAD)],
        [para("0  Inspect", CELLB),
         para("Checks your song and lyrics open correctly and reads length, format, line count.", CELL),
         para("A short file report. Nothing to approve.", CELL)],
        [para("1  Word Timing", CELLB),
         para("Separates the vocals, then listens word-by-word to place the exact start/end time of every lyric word. Cross-checked twice for accuracy.", CELL),
         para("<b>word-timestamps.json</b>, <b>phrases.json</b>, a confidence report. You skim it.", CELL)],
        [para("2  Sync Test", CELLB),
         para("A plain black video that highlights each word exactly as it is sung - no effects. This is only to prove the timing is perfect.", CELL),
         para("<b>sync-test.mp4</b>. You watch ~25s and confirm words land on beat.", CELL)],
        [para("3  Creative Direction", CELLB),
         para("Reads the MEANING of your lyrics and designs the look - not generic zooms. Builds a beat map and a line-by-line visual plan.", CELL),
         para("<b>creative-direction.md</b>, <b>visual-screenplay.json</b>, <b>beat-map.json</b>. You read the plan.", CELL)],
        [para("4  HERO PROOF  (gate)", CELLB),
         para("Builds ONE short signature section at FULL quality - real motion, real typography, real style. Proof of the look before the long render.", CELL),
         para("<b>hero-proof.mp4</b> (5 sec) + 8 preview frames. <b>You approve the look.</b>", CELL)],
        [para("5  Full Render", CELLB),
         para("Renders the rest of the song on the same engine, section by section, matching the approved look.", CELL),
         para("<b>final-lyric-video.mp4</b> - your finished 9:16 reel.", CELL)],
    ]
    t = Table(rows, colWidths=[34 * mm, 78 * mm, 62 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
                ("BACKGROUND", (0, 5), (0, 5), GATE),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d4db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)

    story.append(para("4. Where the results live", H2))
    story.append(para("Everything for one song is saved inside the project folder, so nothing gets lost or overwritten:", BODY))
    story.append(para("<font name='Courier' color='#1b4965'>/Users/you/.../asur/lyric_video/</font>", BODY))
    story.append(para("- the timing files, the sync test, the creative plan, the hero proof, and the final video all collect here, each stage in its own place.", BODY))

    story.append(para("5. Three rules ASUR always follows", H2))
    story.append(para("- <b>Freeze what you approve.</b> Once you say yes, that file is locked and checksummed - later steps read it but never change it.", BODY))
    story.append(para("- <b>You review a picture, not code.</b> Every important step ends in something you can actually watch or read.", BODY))
    story.append(para("- <b>Prove quality on a small piece first.</b> The 5-second hero proof settles the look before the long render - no wasted hours.", BODY))

    story.append(PageBreak())

    # ---- Page 3: the commands ----
    story.append(para("6. The ASUR commands (and what to type)", H1))
    story.append(para("For a lyric video you do NOT type a slash command. You just say it in plain words (see section 2). There is no /author command - if you type /author, ASUR does not recognise it. The slash commands below are for BUILDING ASUR itself, not for making a video.", SUB))

    story.append(para("To make a lyric video, type this - not a slash command:", BOLD))
    saybox = Table([[para('"Make a lyric video from song.mp3 and lyrics.txt."', MONO)]], colWidths=[174 * mm])
    saybox.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG),
                                ("BOX", (0, 0), (-1, -1), 1, RED),
                                ("TOPPADDING", (0, 0), (-1, -1), 9),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(saybox)
    story.append(Spacer(1, 10))

    story.append(para("The 7 slash commands that actually exist", BOLD))
    cmd_rows = [
        [para("COMMAND", HEAD), para("WHAT IT DOES", HEAD)],
        [para("/architecture", MONO),
         para("Phase 0 - writes the decision records (ADRs) and empty folders. No feature code.", CELL)],
        [para("/build-phase N", MONO),
         para("Builds one phase (0-8) end to end: tests first, build, review, fix, verify, human gate, commit. Example: <b>/build-phase 1</b>", CELL)],
        [para("/verify-phase N", MONO),
         para("Read-only. Re-checks a phase's exit gate (full tests, firewall, fail-closed, determinism). Changes nothing. Example: <b>/verify-phase 1</b>", CELL)],
        [para("/all-phases", MONO),
         para("Drives the whole build P00 to P08 automatically, stopping at every human gate, BLOCK, HOLD, or open question.", CELL)],
        [para("/status", MONO),
         para("Quick one-line health check: current phase, test counts, open questions, next gate. Read-only.", CELL)],
        [para("/report", MONO),
         para("The full read-only dashboard: phase-by-phase table, real test numbers, all open questions, firewall and invariant health.", CELL)],
        [para("/fix-bug &lt;description&gt;", MONO),
         para("Fixes a bug the disciplined way - reproduce with a failing test first, make the minimal fix, re-run tests. Example: <b>/fix-bug sync test crashes on empty lyrics</b>", CELL)],
    ]
    ct = Table(cmd_rows, colWidths=[44 * mm, 130 * mm])
    ct.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d4db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(ct)
    story.append(Spacer(1, 10))
    story.append(para("Why /author did nothing", BOLD))
    story.append(para("/author is not one of ASUR's commands. When you type a command ASUR does not know, it has nothing to run, so it just starts generating free-form text instead of walking the real pipeline. Use the plain-words sentence above for a lyric video, or one of the 7 slash commands above to build ASUR.", BODY))

    story.append(PageBreak())

    # ---- Page 4: family tree ----
    story.append(para("7. The family tree", H1))
    story.append(para("Top to bottom - this is the whole journey, from your 2 files to the finished video.", SUB))
    story.append(Spacer(1, 4))
    story.append(TreeNode(width=174 * mm, height=232 * mm))

    doc.build(story)
    print("WROTE", OUT)


if __name__ == "__main__":
    build()
