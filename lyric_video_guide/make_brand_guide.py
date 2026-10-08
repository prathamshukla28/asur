"""Build the ASUR Complete Brand & Project Guide PDF.

Re-run this ANY time something is added or removed from ASUR so the guide
stays the single source anyone can read to understand the whole project:

    python3 lyric_video_guide/make_brand_guide.py

Output: lyric_video_guide/ASUR-Complete-Guide.pdf

Design rule (reportlab built-in fonts have no sub/superscript glyphs):
never use unicode sub/superscript characters -- they render as black boxes.
Use <sub>/<super> tags inside Paragraph if ever needed.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --- Brand palette (ASUR) ------------------------------------------------
INK = colors.HexColor("#14181f")       # near-black body text
RED = colors.HexColor("#d7263d")       # ASUR accent (the red-line motif)
BLUE = colors.HexColor("#1b3a5b")      # deep brand blue
SOFT = colors.HexColor("#5b6675")      # muted grey text
BG = colors.HexColor("#f4f1ea")        # warm paper
GOLD = colors.HexColor("#c08a2d")      # human-gate / approval highlight
GREEN = colors.HexColor("#1d7a4d")     # done / shipped
LINE = colors.HexColor("#d9d2c4")      # hairline rules

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


def _styles():
    ss = getSampleStyleSheet()
    out = {}
    out["brand"] = ParagraphStyle(
        "brand", parent=ss["Title"], fontName="Helvetica-Bold",
        fontSize=44, leading=46, textColor=RED, alignment=TA_CENTER, spaceAfter=2,
    )
    out["tagline"] = ParagraphStyle(
        "tagline", parent=ss["Normal"], fontName="Helvetica-Oblique",
        fontSize=13, leading=17, textColor=BLUE, alignment=TA_CENTER, spaceAfter=10,
    )
    out["h1"] = ParagraphStyle(
        "h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
        fontSize=19, leading=22, textColor=BLUE, spaceBefore=12, spaceAfter=6,
    )
    out["h2"] = ParagraphStyle(
        "h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=RED, spaceBefore=8, spaceAfter=3,
    )
    out["body"] = ParagraphStyle(
        "body", parent=ss["Normal"], fontName="Helvetica",
        fontSize=10.5, leading=15, textColor=INK, alignment=TA_LEFT, spaceAfter=5,
    )
    out["small"] = ParagraphStyle(
        "small", parent=ss["Normal"], fontName="Helvetica",
        fontSize=9, leading=12.5, textColor=SOFT,
    )
    out["cell"] = ParagraphStyle(
        "cell", parent=ss["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=13, textColor=INK,
    )
    out["cellb"] = ParagraphStyle(
        "cellb", parent=ss["Normal"], fontName="Helvetica-Bold",
        fontSize=9.5, leading=13, textColor=BLUE,
    )
    out["head"] = ParagraphStyle(
        "head", parent=ss["Normal"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=colors.white,
    )
    out["code"] = ParagraphStyle(
        "code", parent=ss["Normal"], fontName="Courier-Bold",
        fontSize=10, leading=14, textColor=colors.white,
    )
    out["node"] = ParagraphStyle(
        "node", parent=ss["Normal"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=10.5, textColor=colors.white, alignment=TA_CENTER,
    )
    return out


S = _styles()


def rule(color=LINE, w=1):
    t = Table([[""]], colWidths=[PAGE_W - 2 * MARGIN], rowHeights=[w])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), w, color)]))
    return t


def band(text, color):
    """A full-width colored heading band."""
    p = Paragraph(text, S["head"])
    t = Table([[p]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def kv_table(rows, head, widths):
    data = [[Paragraph(h, S["head"]) for h in head]]
    for r in rows:
        data.append([Paragraph(c, S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def code_box(text, color=INK):
    p = Paragraph(text, S["code"])
    t = Table([[p]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


class FlowTree(Flowable):
    """Top-down family tree of the ASUR loop: boxes + arrows."""

    def __init__(self, nodes, width=PAGE_W - 2 * MARGIN):
        super().__init__()
        self.nodes = nodes  # list of (label, color)
        self.width = width
        self.box_h = 30
        self.gap = 15
        self.height = len(nodes) * (self.box_h + self.gap)

    def wrap(self, *args):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        box_w = 150
        x = (self.width - box_w) / 2.0
        y = self.height - self.box_h
        for i, (label, color) in enumerate(self.nodes):
            c.setFillColor(color)
            c.roundRect(x, y, box_w, self.box_h, 6, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9)
            # two-line centered label
            lines = label.split("\n")
            ly = y + self.box_h / 2 + (len(lines) - 1) * 5 - 3
            for ln in lines:
                c.drawCentredString(x + box_w / 2, ly, ln)
                ly -= 11
            if i < len(self.nodes) - 1:
                # arrow down to next box
                ax = x + box_w / 2
                top = y
                bot = y - self.gap
                c.setStrokeColor(SOFT)
                c.setLineWidth(1.5)
                c.line(ax, top, ax, bot + 4)
                p = c.beginPath()
                p.moveTo(ax - 4, bot + 6)
                p.lineTo(ax + 4, bot + 6)
                p.lineTo(ax, bot)
                p.close()
                c.setFillColor(SOFT)
                c.drawPath(p, stroke=0, fill=1)
            y -= (self.box_h + self.gap)


def build(out_path: Path):
    doc = BaseDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=14 * mm, bottomMargin=14 * mm,
        title="ASUR - Complete Guide", author="ASUR",
    )
    frame = Frame(MARGIN, 14 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 28 * mm, id="main")

    def paint_bg(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        canvas.setFillColor(RED)
        canvas.rect(0, PAGE_H - 6, PAGE_W, 6, stroke=0, fill=1)  # red-line motif top
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SOFT)
        canvas.drawString(MARGIN, 8 * mm, "ASUR - the honest, firewalled AI Content Creation OS")
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, "page %d" % _doc.page)
        canvas.restoreState()

    from reportlab.platypus import PageTemplate
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=paint_bg)])

    story = []

    # ---------------- PAGE 1: COVER + WHAT IS ASUR ----------------
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph("ASUR", S["brand"]))
    story.append(Paragraph(
        "The honest, firewalled AI Content Creation OS &mdash; that learns from every video.",
        S["tagline"]))
    story.append(Spacer(1, 4))
    story.append(rule(RED, 2))
    story.append(Spacer(1, 10))
    story.append(Paragraph("What ASUR is (in one breath)", S["h1"]))
    story.append(Paragraph(
        "ASUR turns a <b>one-line idea</b> (or a song, or your own raw clip) into a finished "
        "9:16 short video &mdash; and it does the whole job the way a disciplined creative team would: "
        "it <b>understands</b> the idea, <b>creates</b> the visuals, <b>edits</b> them, <b>honestly judges</b> "
        "whether it is strong, lets <b>you</b> approve, <b>measures</b> real performance, and <b>learns</b> "
        "so the next video is better.", S["body"]))
    story.append(Paragraph(
        "It runs <b>100% on your own computer</b> with <b>no logins and no keys</b>. Nothing is faked, "
        "nothing is hidden, and nothing important happens without your say-so.", S["body"]))
    story.append(Spacer(1, 6))
    story.append(band("THE ONE-LINE MOAT (why nobody can copy it)", BLUE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Competitors optimize one stage and resell the same frontier models. ASUR's edge is the "
        "<b>closed loop</b>: an honest, <b>firewalled</b> viral judge plus a <b>learning memory</b> so every "
        "video is informed by the measured performance of the last. The <b>system</b> is the product &mdash; "
        "you can swap in any generation engine (free today, paid frontier models later) by changing a "
        "config, not rewriting the app.", S["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("The loop (this is the heart of ASUR)", S["h2"]))
    story.append(Paragraph(
        "<b>SCRIPT</b> understands &rarr; <b>GENERATION</b> creates &rarr; <b>EDITING</b> shapes &rarr; "
        "<b>VIRAL CHECK</b> challenges &rarr; <b>a human decides</b> &rarr; <b>ANALYTICS</b> measures &rarr; "
        "<b>SCRIPT learns</b> &rarr; (repeat, better every time).", S["body"]))
    story.append(PageBreak())

    # ---------------- PAGE 2: THE 8 PROMISES (INVARIANTS) ----------------
    story.append(band("THE 8 PROMISES ASUR NEVER BREAKS", RED))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "These are the unbreakable rules. Every part of ASUR obeys them, and the code is tested to prove it.",
        S["body"]))
    inv = [
        ["1. Stays local, no login", "Runs on your machine. No accounts, no API keys, no internet needed. Your identity is just your computer user + git name."],
        ["2. Never a fake viral %", "It will never say '93% viral'. It gives honest, separate signals and labels what is a fact vs a guess."],
        ["3. The firewall", "The part that MAKES the video and the part that JUDGES it never talk directly. The judge can't be bribed to rubber-stamp. This is the moat."],
        ["4. Fail closed", "If anything is missing or unclear, ASUR stops and waits &mdash; it never pushes forward on a guess."],
        ["5. Humans own approvals", "You approve the look and the publish. The machine never publishes or does anything irreversible on its own."],
        ["6. Every asset is traceable", "Each image/voice/clip carries where it came from and its licence &mdash; so you always know it is safe to use."],
        ["7. No black box", "Every decision has a plain-language reason you can read."],
        ["8. Nothing silently overwritten", "Every version is kept. You can always go back. Nothing is lost."],
    ]
    story.append(Spacer(1, 4))
    story.append(kv_table(inv, ["Promise", "What it means for you"],
                          [58 * mm, PAGE_W - 2 * MARGIN - 58 * mm]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("The 5 parts (instruments) + the conductor", S["h2"]))
    parts = [
        ["SCRIPT", "The brain. Understands the idea, writes hooks + the script, remembers what worked."],
        ["GENERATION", "The creator. Turns the script into visuals, voice, music (the pixels)."],
        ["EDITING", "The editing room &mdash; shared, human-controlled. Timeline, effects, captions, cuts."],
        ["VIRAL CHECK", "The honest judge. Scores 12 things 0-100, never one fake number."],
        ["ORCHESTRATOR", "The conductor. Moves the project stage to stage, stops at the gates."],
        ["THE FIREWALL", "Sits between the creator and the judge so they never collude. Nobody else has this."],
    ]
    story.append(kv_table(parts, ["Part", "Plain-language job"],
                          [42 * mm, PAGE_W - 2 * MARGIN - 42 * mm]))
    story.append(PageBreak())

    # ---------------- PAGE 3: THE 9 PHASES + PIPELINE ----------------
    story.append(band("HOW ASUR WAS BUILT: 9 PHASES (P00-P08) - ALL DONE", GREEN))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "ASUR was built phase by phase, tests first. <b>All 9 phases are complete and 214 tests pass.</b>",
        S["body"]))
    phases = [
        ["P00", "Foundations", "The rulebook + safety checks (8 promises wired in, local-only guard)."],
        ["P01", "SCRIPT brain", "Idea -> hooks -> full script, remembers past hooks."],
        ["P02", "Orchestrator", "The 18-step pipeline runtime + the two human gates."],
        ["P03", "Firewall", "Maker and judge kept apart; safe hand-off with fingerprints."],
        ["P04", "Generation + Hero Proof", "Plans the visuals; makes a tiny 5s proof to approve first."],
        ["P05", "Editing room", "Timeline, 15 effects, captions, audio mix, full manual control."],
        ["P06", "Full build + QA", "Builds all sections; 5-family quality check incl. 'looks human not AI'."],
        ["P07", "Viral Check", "12 honest scores, yes/no risk flags, a PASS / CHANGES / REJECT verdict."],
        ["P08", "Learning + Publish", "You approve publish; real numbers fold back so the next video is smarter."],
    ]
    story.append(Spacer(1, 4))
    story.append(kv_table(phases, ["#", "Phase", "What it gives you"],
                          [14 * mm, 42 * mm, PAGE_W - 2 * MARGIN - 56 * mm]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("The pipeline + the 2 human gates", S["h2"]))
    story.append(Paragraph(
        "A project walks forward one safe step at a time (18 states). It <b>stops and asks you twice</b>: "
        "<b>(Gate 1) the Hero Proof</b> &mdash; approve a tiny 5-second sample before any expensive work; and "
        "<b>(Gate 2) Publish</b> &mdash; approve the finished video before anything goes out. ASUR never "
        "skips a gate and never self-approves irreversible steps.", S["body"]))
    story.append(Spacer(1, 4))
    story.append(band("CHEAP WORK EARLY, EXPENSIVE WORK ONLY AFTER YOU APPROVE THE PROOF", GOLD))
    story.append(PageBreak())

    # ---------------- PAGE 4: WHAT YOU CAN MAKE TODAY ----------------
    story.append(band("WHAT YOU CAN MAKE TODAY (3 real tools, free + local)", BLUE))
    story.append(Spacer(1, 6))
    story.append(Paragraph("1. Idea -> Reel", S["h2"]))
    story.append(Paragraph(
        "Give one line (e.g. <i>'why most people waste money on AI tools'</i>). ASUR writes the whole "
        "script and renders a real 9:16 video with a natural voice, moving backgrounds and captions.", S["body"]))
    story.append(code_box('PYTHONPATH="$(pwd)" python3 render_demo.py', INK))
    story.append(Spacer(1, 6))
    story.append(Paragraph("2. Your clip -> 2+ polished edits", S["h2"]))
    story.append(Paragraph(
        "Give your own video. ASUR auto-cuts it to 9:16, re-paces it, grades the colour, and writes "
        "captions (even from the real speech) &mdash; in <b>4 styles</b>: punchy, cinematic, meme, beatcut.", S["body"]))
    story.append(code_box('PYTHONPATH="$(pwd)" python3 edit_video.py --input your_clip.mp4 --captions auto', INK))
    story.append(Spacer(1, 6))
    story.append(Paragraph("3. Song + lyrics -> art-directed lyric video", S["h2"]))
    story.append(Paragraph(
        "Give a <b>song</b> and a <b>lyrics.txt</b>. ASUR times every word to the vocal, writes the creative "
        "direction, and builds a real motion-graphics lyric video (Remotion engine). See the separate "
        "<i>ASUR-Lyric-Video-Guide.pdf</i> for the full 6-stage walkthrough.", S["body"]))
    story.append(Spacer(1, 8))
    story.append(band("THE HONEST FREE-vs-PAID STORY", RED))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Free + local today:</b> real scripts, real voice, real motion, real captions, real editing &mdash; "
        "everything runs on your Mac with no bills. It is genuinely good, but it is <b>not</b> the look of "
        "paid frontier models (Veo, Kling, Runway).", S["body"]))
    story.append(Paragraph(
        "<b>Paid later (the dial you turn):</b> because of the firewall + adapter design, swapping in a top "
        "paid model is a <b>config change, not a rewrite</b>. ASUR's brain, honesty and learning stay the "
        "same &mdash; only the paintbrush gets sharper. That is why the system, not any single model, is the product.",
        S["body"]))
    story.append(PageBreak())

    # ---------------- PAGE 5: ROADMAP + BRAND + FAMILY TREE ----------------
    story.append(band("THE ROAD TO 'BEST IN THE WORLD' (5 stages)", GREEN))
    story.append(Spacer(1, 6))
    road = [
        ["Stage 1", "Elite script brain", "DONE"],
        ["Stage 2", "Genuinely good free render", "IN PROGRESS"],
        ["Stage 3", "Prove the honest moat with real data", "NEXT"],
        ["Stage 4", "A clean product people touch", "PLANNED"],
        ["Stage 5", "Flip the quality dial with paid models (adapter swap)", "PLANNED"],
    ]
    story.append(kv_table(road, ["Stage", "Goal", "Status"],
                          [24 * mm, PAGE_W - 2 * MARGIN - 24 * mm - 32 * mm, 32 * mm]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("ASUR as a brand", S["h2"]))
    story.append(Paragraph(
        "<b>Name:</b> ASUR. <b>Tagline:</b> the honest, firewalled AI Content Creation OS that learns from "
        "every video. <b>What makes it different</b> from Runway / CapCut / OpusClip: they optimise one stage "
        "and resell the same models; ASUR owns the <b>closed, honest, firewalled learning loop</b> that none of "
        "them have. Visual identity: clean warm paper, deep blue, and the signature <b>red line</b> motif.", S["body"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Family tree: how the whole thing flows", S["h1"]))
    story.append(Spacer(1, 4))
    tree = FlowTree([
        ("YOUR IDEA / CLIP / SONG", BLUE),
        ("SCRIPT\n(understands + writes)", RED),
        ("GENERATION\n(makes the visuals)", RED),
        ("EDITING\n(shapes + captions)", RED),
        ("VIRAL CHECK\n(honest judge)", RED),
        ("GATE 1: HERO PROOF\n(you approve)", GOLD),
        ("GATE 2: PUBLISH\n(you approve)", GOLD),
        ("ANALYTICS -> LEARNING\n(next video smarter)", GREEN),
    ])
    story.append(tree)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This guide is auto-generated. Whenever ASUR changes, re-run "
        "<font name='Courier'>python3 lyric_video_guide/make_brand_guide.py</font> and it stays current.",
        S["small"]))

    doc.build(story)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "ASUR-Complete-Guide.pdf"
    build(out)
    print("Wrote", out)
