"""Build the ASUR Complete Guide PDF (version 2).

Re-run this ANY time something is added or removed from ASUR so the guide
stays the single source anyone can read to understand the whole project:

    python3 guides/make_brand_guide.py

Output: guides/ASUR-Complete-Guide.pdf
Previous edition: guides/ASUR-Complete-Guide-v1.pdf (generator make_brand_guide_v1.py)

Design rule (reportlab built-in fonts have no sub/superscript glyphs):
never use unicode sub/superscript characters or arrows -- they render as black
boxes. Use "-&gt;" for arrows and <sub>/<super> tags inside Paragraph if needed.
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
GUIDE_DATE = "October 2026"
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
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"page {_doc.page}")
        canvas.restoreState()

    from reportlab.platypus import PageTemplate
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=paint_bg)])

    story = []
    W = PAGE_W - 2 * MARGIN

    def h1(t):
        story.append(Paragraph(t, S["h1"]))

    def h2(t):
        story.append(Paragraph(t, S["h2"]))

    def p(t):
        story.append(Paragraph(t, S["body"]))

    def small(t):
        story.append(Paragraph(t, S["small"]))

    def gap(n=6):
        story.append(Spacer(1, n))

    def table(rows, head, widths):
        story.append(kv_table(rows, head, widths))

    def code(t, color=INK):
        story.append(code_box(t, color))

    # ================= PAGE 1: COVER =================
    gap(14 * mm)
    story.append(Paragraph("ASUR", S["brand"]))
    story.append(Paragraph(
        "The honest, firewalled AI Content Creation OS &mdash; one idea in, a finished video out, "
        "and it learns from every video.", S["tagline"]))
    story.append(rule(RED, 2))
    gap(8)
    story.append(band("COMPLETE GUIDE &mdash; VERSION 2 (" + GUIDE_DATE + ")", BLUE))
    gap(6)
    p("<b>What ASUR is, in one breath.</b> You type a one-line idea. ASUR researches it, figures out "
      "who it is for, picks a strategy, writes and scores 20+ hooks, writes the script, plans every "
      "shot, generates the visuals and voice, edits them on a timeline with captions and music, "
      "renders a platform-ready MP4, judges it honestly on 12 dimensions, packages it for YouTube "
      "or Instagram, and then <b>stops and waits for you</b>. After you publish, you feed back the "
      "real numbers and ASUR remembers which hooks worked, so the next video starts smarter.")
    p("<b>Where it runs.</b> 100% on your own Mac. No login, no API keys, no cloud. The core is "
      "pure Python standard library; the heavy media tools (FFmpeg, SDXL, Kokoro voice, "
      "faster-whisper) are optional add-ons.")
    gap(4)
    h2("What changed since version 1 of this guide")
    table([
        ["Folders", ("The project was reorganized. Side tools moved to <b>studio/</b>, PDFs to "
         "<b>guides/</b>, old output videos to <b>outputs/</b>; personal notes left the repo. "
         "Nothing was deleted.")],
        ["YouTube folder", ("Now really exists: <b>asur/youtube/demo/</b> was produced by a real "
         "<font name='Courier'>asur render</font> run (final video, thumbnail, title, description, "
         "tags, metadata, content report).")],
        ["New stages", ("P09 platform packs (Instagram Reels, YouTube Shorts, YouTube Long) and P10 "
         "real render + publish package are now in the guide.")],
        ["IDEA 4 concepts", ("All 10 concepts (reconciliation every 4 hours, webhooks, gateway API, "
         "WebSocket, PPP, pooling, OOP abstract, WebRTC, SFU, signalling server) are mapped onto "
         "the ASUR flow with an honest status for each.")],
        ["Tests", "309 automated tests pass (was 221 in version 1)."],
        ["Old guide", "Kept untouched as <b>guides/ASUR-Complete-Guide-v1.pdf</b>."],
    ], ["Area", "What is new"], [32 * mm, W - 32 * mm])

    # ================= PAGE 2: THE COMPLETE FLOW =================
    story.append(PageBreak())
    h1("1. The complete flow (remember this page)")
    p("Every ASUR video walks the same road. Red boxes are machine work, gold boxes are "
      "<b>you</b>, green is the learning loop that makes the next video better.")
    gap(2)
    story.append(FlowTree([
        ("1. IDEA\n(one line from you)", BLUE),
        ("2. SCRIPT\nresearch, audience, strategy", RED),
        ("3. HOOKS + SCRIPT\n20+ hooks scored, 13-check gate", RED),
        ("4. PLAN THE VIDEO\ndirection, screenplay, assets", RED),
        ("GATE 1: HERO PROOF\nyou approve one sample", GOLD),
        ("5. GENERATION\nimages, voice, music (adapters)", RED),
        ("6. EDITING\ntimeline, captions, mix", RED),
        ("7. RENDER\nplatform MP4 + QA", RED),
        ("8. VIRAL CHECK\n12 honest dimensions", RED),
        ("GATE 2: PUBLISH\nyou approve + upload", GOLD),
        ("9. LEARNING\nreal numbers -> memory", GREEN),
    ]))
    small("The arrow from LEARNING goes back to SCRIPT: the hook memory is read by the next idea.")

    # ================= PAGE 3: 26 STAGES =================
    story.append(PageBreak())
    h1("2. The 26 stages and the code that runs each one")
    p("Every stage writes one <b>artifact</b> (a checksummed JSON file) into the project's "
      "append-only store <font name='Courier'>.script/artifacts/&lt;kind&gt;/vNNNN-*.json</font>. "
      "Nothing is ever overwritten; a change makes v0002.")
    table([
        ["1", "Idea", "script/idea.py", "idea"],
        ["2", "Research", "script/research.py", "research"],
        ["3", "Audience", "script/audience.py", "audience"],
        ["4", "Strategy", "script/strategy.py", "strategy"],
        ["5", "Hooks (20+ scored)", "script/hooks.py, hook_memory.py", "hooks"],
        ["6", "Script", "script/script_builder.py", "script"],
        ["7", "Script quality gate (13 checks)", "script/quality_gate.py", "quality report"],
        ["8", "Creative direction", "generation/creative_direction.py", "creative_direction"],
        ["9-10", "Timing + fact check", "script/evidence.py", "evidence classes"],
        ["11", "Visual screenplay", "generation/visual_screenplay.py", "visual_screenplay"],
        ["12-13", "Asset strategy + generation plan", "asset_strategy.py, generation_plan.py",
         "asset_plan, generation_plan"],
        ["14", "License guard", "generation/license_guard.py", "license block"],
        ["15-17", "Hero proof (one sample)", "generation/hero_proof.py", "hero_proof"],
        ["18", "<b>GATE 1 &mdash; you approve the hero proof</b>", "core/gate.py", "approval"],
        ["19", "Full generation (first paid-in-time step)", "generation/dispatch.py + adapters/",
         "media + provenance"],
        ["20", "Section QA", "generation/section_qa.py", "section report"],
        ["21", "Edit + final render", "editing/*, generation/render.py", "edit_plan, final_render"],
        ["22", "Final QA (5 families)", "generation/final_qa.py", "final_qa"],
        ["23", "Viral check", "viral_check/evaluate.py", "viral_check"],
        ["24", "Publish package", "learning/publish_package.py", "publish_package"],
        ["25", "<b>GATE 2 &mdash; you approve publishing</b>", "core/gate.py", "approval"],
        ["26", "Performance + learning", "performance.py, metrics_ingest.py, learning.py",
         "performance, learning"],
    ], ["Stage", "What happens", "Code (inside asur/asur/)", "Artifact"],
        [14 * mm, 58 * mm, 64 * mm, W - 136 * mm])

    # ================= PAGE 4: STATES + GATES =================
    story.append(PageBreak())
    h1("3. The state machine: 18 states, 2 human gates")
    p("The orchestrator (<font name='Courier'>orchestrator/states.py</font>) moves a project "
      "through 18 states. It only ever sees <b>control tokens</b> (state, gate, verdict, digest) "
      "&mdash; never the content itself. If anything is missing, it stops at HOLD or BLOCK "
      "(fail closed).")
    table([
        [("DRAFT -&gt; INPUTS_VERIFIED -&gt; RESEARCH_COMPLETE -&gt; STRATEGY_APPROVED -&gt; "
         "HOOK_APPROVED -&gt; SCRIPT_APPROVED -&gt; TIMING_VERIFIED"), "Cheap (stages 0-6)",
         "Pure thinking. Free, instant, runs anywhere."],
        [("CREATIVE_DIRECTION_APPROVED -&gt; SCREENPLAY_APPROVED -&gt; HERO_PROOF_READY -&gt; "
         "<b>HERO_PROOF_APPROVED (Gate 1)</b>"), "Moderate (7-18)",
         "One sample is made so you can say yes before anything expensive."],
        [("FULL_GENERATION -&gt; QA -&gt; VIRAL_CHECK_APPROVED -&gt; "
         "<b>PUBLISH_READY (Gate 2)</b> -&gt; PUBLISHED -&gt; PERFORMANCE_CAPTURED -&gt; LEARNED"),
         "Expensive (19+)", "GPU/time cost. Only after Gate 1. Publishing only after Gate 2."],
    ], ["States", "Cost tier", "Meaning"], [96 * mm, 30 * mm, W - 126 * mm])
    gap(6)
    h2("The two human gates")
    p("<b>Gate 1 &mdash; Hero proof (stage 18).</b> ASUR makes one representative shot. You "
      "approve it before full generation spends time and compute.")
    p("<b>Gate 2 &mdash; Publish (stage 25).</b> ASUR builds the full upload package and stops. "
      "It never uploads by itself. You review the package in the youtube/ folder and publish.")
    p("Approvals are recorded with your local identity (<font name='Courier'>whoami</font> + "
      "git name/email). If you approve your own work alone, it is honestly recorded as "
      "<font name='Courier'>HOLD:SELF_APPROVED</font>.")
    gap(4)
    h2("The firewall (why the judge can be trusted)")
    p("GENERATION and VIRAL CHECK never talk to each other. SCRIPT hands each one a filtered "
      "view (<font name='Courier'>tools/projection.py</font>): GENERATION_VIEW has the brief and "
      "quality floors but not the judge's criteria; VIRAL_VIEW has the finished video hashes and "
      "facts but every target is stripped by name. A hand-off queue with a hash chain "
      "(<font name='Courier'>tools/queue.py</font>) proves nothing was tampered with. "
      "So the maker cannot \"study for the test\".")

    # ================= PAGE 5: WHAT ASUR CAN DO =================
    story.append(PageBreak())
    h1("4. Everything ASUR can do today")
    p("Honest status. <b>HAVE</b> = works now and is tested. <b>PARTIAL</b> = works with limits. "
      "<b>PLANNED</b> = designed, not built yet.")
    table([
        ["Turn one idea into a full plan: research, audience, strategy, 20+ scored hooks, script",
         "HAVE"],
        ["Write in English, Hindi, Hinglish, Indian-English, Marathi", "HAVE"],
        ["Script quality gate with 13 checks and evidence classes", "HAVE"],
        ["Creative direction, shot-by-shot visual screenplay, asset + generation plan", "HAVE"],
        ["License guard (blocks known license traps) + provenance on every asset", "HAVE"],
        ["Timeline editing with 15 primitives, captions inside safe area, audio mix", "HAVE"],
        ["Edit controls: accept, reject, modify, regenerate, lock, unlock, revert, branch, compare",
         "HAVE"],
        ["Render a real platform MP4 with FFmpeg (9:16 or 16:9)", "HAVE"],
        ["Burned-in captions", ("PARTIAL &mdash; needs an FFmpeg build with drawtext; otherwise "
         "renders clean cards and says so in provenance")],
        ["Final QA in 5 families: visual, audio, text, content, platform", "HAVE"],
        [("Honest viral check: 12 dimensions, risk flags, verdict PASS / PASS-WITH-CHANGES / "
         "REJECT, never a fake % score"), "HAVE"],
        ["Platform packs: Instagram Reels, YouTube Shorts, YouTube Long", "HAVE"],
        [("Publish package in youtube/&lt;project&gt;/package/ (video, thumbnail, title, "
         "description, tags, metadata, report)"), "HAVE"],
        ["Learning: read your real numbers from a file, update hook memory", "HAVE"],
        ["Daily self-check (status, stdlib purity, firewall, lint, types, tests, drift)", "HAVE"],
        ["AI image generation (SDXL)", ("PARTIAL &mdash; adapter code present, needs "
         "<font name='Courier'>asur[generation]</font> install + model weights")],
        ["AI voice (Kokoro), AI music (Stable Audio), speech-to-text (faster-whisper)",
         "PARTIAL &mdash; adapter code being written right now (uncommitted work)"],
        ["AI video clips (Wan 2.2)", "PLANNED &mdash; stub only"],
        ["Automatic uploading to YouTube / Instagram", "NOT ALLOWED by design &mdash; you publish"],
    ], ["Capability", "Status"], [W - 62 * mm, 62 * mm])

    # ================= PAGE 6: COMMANDS =================
    story.append(PageBreak())
    h1("5. How to use it: the commands")
    p("Run everything from the <b>asur/</b> folder. ASUR is installed in editable mode, so "
      "<font name='Courier'>asur</font> and <font name='Courier'>python3 -m asur.cli</font> "
      "are the same thing.")
    h2("A. Write a script from an idea")
    code("asur script --idea \"why most people waste money on AI tools\" \\<br/>"
         "&nbsp;&nbsp;--project . --project-id myvideo --language hinglish --platform youtube_shorts")
    gap(4)
    h2("B. Run the orchestrator on a project")
    code("asur run --project . --project-id myvideo")
    gap(4)
    h2("C. Make the youtube/ folder for real (demo, 2 commands)")
    code("python3 studio/seed_demo_project.py --project-id demo<br/>"
         "asur render --project . --project-id demo --platform youtube_shorts", BLUE)
    small("Step 1 builds every artifact from idea to edit plan plus the viral check. Step 2 renders "
          "the MP4 and writes the package, then stops at Gate 2. Platforms: instagram_reels, "
          "youtube_shorts, youtube_long.")
    gap(4)
    h2("D. Reserved commands (not built yet)")
    code("asur generate     # reserved: full generation from the CLI<br/>"
         "asur viral-check  # reserved: standalone viral check", SOFT)
    gap(4)
    h2("E. Health checks")
    code("python3 -m pytest -q          # 309 tests<br/>"
         "ruff check asur studio       # lint<br/>"
         "python3 -m asur.tools.daily_driver   # daily self-check report")

    # ================= PAGE 7: YOUTUBE FOLDER =================
    story.append(PageBreak())
    h1("6. The youtube/ folder")
    p("<b>Why you could not see it before:</b> the folder is created by "
      "<font name='Courier'>asur render</font>, and that command had only ever run inside "
      "automatic tests (in temporary folders that are wiped). It had never been run on a real "
      "project in your asur folder. It has now been run, so the folder exists:")
    code("asur/youtube/<br/>"
         "&nbsp;&nbsp;demo/                      &lt;- one folder per project<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;render/                  &lt;- rendered video versions<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;_work/                   &lt;- temporary frames/cards<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;package/                 &lt;- READY TO UPLOAD<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-final-video.mp4<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-thumbnail.jpg<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-title.txt<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-description.txt<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-tags.txt<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-platform-metadata.json<br/>"
         "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v0001-content-report.json", BLUE)
    gap(4)
    p("<b>Versioning.</b> Files are never overwritten. Render again and you get v0002-*. "
      "<b>Git.</b> youtube/ is in .gitignore (videos are large and personal), so it lives on "
      "your disk only. <b>Every new project</b> gets its own folder: "
      "<font name='Courier'>youtube/&lt;project-id&gt;/</font>.")
    p("<b>Known limit on this Mac:</b> the Homebrew FFmpeg here has no <i>drawtext</i> filter, so "
      "captions are not burned in; the video renders with clean cards and the provenance says "
      "exactly that. Installing an FFmpeg built with libfreetype turns captions on.")

    # ================= PAGE 8: FOLDER MAP =================
    story.append(PageBreak())
    h1("7. The organized folder map")
    p("The project now has one clear rule: <b>the product</b> lives in "
      "<font name='Courier'>asur/</font>, <b>everything around it</b> has its own labelled "
      "shelf. Moves only &mdash; nothing was deleted.")
    table([
        ["asur/", "THE PRODUCT. The Python package (all stages, gates, firewall)."],
        ["tests/", "309 automated tests (+ integration tests that need FFmpeg)."],
        ["docs/", "Design docs, frozen SPEC, ADRs (decisions), build plans, progress P00-P08."],
        ["studio/", ("Hands-on creator tools: render_demo.py, edit_video.py, "
         "seed_demo_project.py, lyric_video/ (ingest, timing, sync, Remotion stub, your song "
         "project).")],
        ["guides/", "These PDFs and the scripts that generate them (v1 kept)."],
        ["youtube/", "Upload-ready packages per project (made by asur render). Not in git."],
        ["outputs/", "Old output videos: edit_out/ (6 edit styles) and render_out/ (demo reel)."],
        ["scripts/", "com.asur.daily.plist &mdash; macOS schedule for the daily self-check."],
        [".script/", "The artifact store (every stage's JSON, versioned). Not in git."],
        [".github/", "CI: tests, lint, and a stdlib-only import probe on every push."],
        ["root files", ("README, AGENTS (the constitution), CHANGELOG, DEFERRED (honest list of "
         "what is not real yet), SECURITY, CONTRIBUTING, LICENSE (MIT), pyproject.toml, MAP.md.")],
    ], ["Folder", "What lives there"], [28 * mm, W - 28 * mm])
    gap(6)
    h2("Inside the package: asur/asur/")
    table([
        ["core/", ("canonical JSON + SHA-256, artifact envelope, gates, local identity, "
         "versioned workspace, media workspace (youtube/)")],
        ["script/", ("idea, research, audience, strategy, hooks, hook memory, script, quality "
         "gate, evidence")],
        ["generation/", ("creative direction, screenplay, asset + generation plans, hero proof, "
         "license guard, dispatch (router), adapters/, section + final QA, render")],
        ["editing/", "timeline, 15 primitives, captions, audio mix, edit controls, OTIO adapter"],
        ["viral_check/", "12 dimensions, risk flags, verdict"],
        ["learning/", "publish package, performance, metrics ingest, learning memory"],
        ["platforms/", "base PlatformPack + Instagram Reels, YouTube Shorts, YouTube Long"],
        ["orchestrator/", "18 states, control-token orchestrator, run log"],
        ["tools/", "firewall projections, hash-chained queue, status, daily driver"],
        ["cli.py", "the asur command: script, run, render (+ reserved generate, viral-check)"],
    ], ["Module", "Contents"], [28 * mm, W - 28 * mm])

    # ================= PAGE 9-10: IDEA 4 CONCEPTS =================
    story.append(PageBreak())
    h1("8. The 10 IDEA-4 concepts, mapped onto ASUR")
    p("Each concept below is placed where it belongs in the flow. The status is honest. One "
      "rule shapes everything: <b>ASUR-LOCAL-01 &mdash; 100% local, no network</b>. Concepts "
      "that need the internet can only exist as an optional, human-approved add-on, or "
      "<b>loopback-only</b> (127.0.0.1, your own machine).")
    table([
        ["<b>OOP abstract</b>", "One base contract, many implementations.",
         ("platforms/base.py PlatformPack (3 packs share it); generation adapters share one "
         "run contract via dispatch.py."),
         "PARTIAL &mdash; next: formal abstract Adapter and Platform base classes."],
        ["<b>Gateway API</b>", "One front door that routes every request.",
         ("generation/dispatch.py run_job: model name -&gt; adapter. cli.py is the human front "
         "door."), "PARTIAL &mdash; next: loopback-only HTTP gateway (stdlib)."],
        ["<b>Pooling</b>", "Reuse expensive things instead of recreating them.",
         "Not yet. Sections render one after another; models reload each time.",
         "PLANNED &mdash; worker pool for section renders; keep models loaded."],
        ["<b>Reconciliation every 4 hours</b>", ("Regularly compare \"what should be\" with "
         "\"what is\" and fix drift."), ("tools/daily_driver.py detect_drift + checksums in "
         "workspace + hash-chain in queue; scheduled by scripts/com.asur.daily.plist (once a "
         "day, weekdays 09:00)."), ("PARTIAL &mdash; next: 4-hour interval (StartInterval 14400) "
         "and reconcile index vs files vs youtube/ packages.")],
        ["<b>Webhooks</b>", "\"Call me when X happens.\"",
         ("Local equivalent exists: every step is written to the run log "
         "(orchestrator/observability.py)."), ("PLANNED &mdash; local event hooks only. Real "
         "internet webhooks (e.g. YouTube callbacks) break LOCAL-01.")],
        ["<b>WebSocket</b>", "Live two-way stream.",
         "Not yet.", ("PLANNED &mdash; loopback live progress feed from the run log to a local "
         "dashboard.")],
        ["<b>Purchasing power parity</b>", "Fair price per country.",
         ("Not code. Fits the business side (pricing tiers) and the 5 languages already "
         "supported."), "PLANNED &mdash; pricing table; no network needed."],
        ["<b>WebRTC</b>", "Live audio/video between browsers.",
         "Not yet.", ("PLANNED, optional &mdash; live remote review at Gate 1. Needs network + "
         "human approval.")],
        ["<b>SFU</b>", "Server that forwards one stream to many viewers.",
         "Not yet.", "PLANNED, optional &mdash; several reviewers watch the hero proof together."],
        ["<b>Signalling server</b>", "Introduces two WebRTC peers to each other.",
         "Not yet.", "PLANNED, optional &mdash; needed only if WebRTC is added; LAN-only first."],
    ], ["Concept", "Simple meaning", "Where it is in ASUR now", "Status / next step"],
        [30 * mm, 36 * mm, 58 * mm, W - 124 * mm])

    story.append(PageBreak())
    h1("9. How the concepts fit together (target design)")
    p("Read this top to bottom. Each layer uses the concept named in brackets. Solid today = "
      "<font color='#1d7a4d'><b>green</b></font>; partly there = "
      "<font color='#c08a2d'><b>gold</b></font>; future = <font color='#d7263d'><b>red</b></font>.")
    gap(2)
    story.append(FlowTree([
        ("YOU: CLI or local dashboard\n[Gateway API, WebSocket]", GOLD),
        ("ORCHESTRATOR: 18 states\ncontrol tokens only", GREEN),
        ("GATEWAY: dispatch.run_job\n[Gateway API]", GOLD),
        ("WORKER POOL\n[Pooling]", RED),
        ("ADAPTERS: FFmpeg, SDXL, Kokoro...\n[OOP abstract]", GOLD),
        ("ARTIFACT STORE + youtube/\nversioned, checksummed", GREEN),
        ("RUN LOG EVENTS\n[Webhooks, local]", GOLD),
        ("RECONCILER every 4h\n[Reconciliation]", GOLD),
        ("OPTIONAL LIVE REVIEW at Gate 1\n[WebRTC + SFU + Signalling]", RED),
        ("PRICING PER COUNTRY\n[PPP]", RED),
    ]))

    # ================= PAGE 11: HONESTY =================
    story.append(PageBreak())
    h1("10. The 8 laws and the honest judge")
    table([
        ["LOCAL-01", "100% local, key-free. Identity = whoami + git name/email."],
        ["HONEST-01", "No fake \"% viral\" number. Ever."],
        ["FIREWALL-01", "Maker and judge never talk directly."],
        ["GATE-01", "Fail closed. Missing evidence = HOLD or BLOCK, never PASS."],
        ["HUMAN-01", "Humans own inputs, approvals, history. No machine publishing."],
        ["PROV-01", "Every asset carries origin, model, prompt, license."],
        ["EXPLAIN-01", "Every score and rejection has a written reason."],
        ["VERSION-01", "Nothing silently overwritten. Append-only, checksummed."],
    ], ["Law", "Meaning"], [30 * mm, W - 30 * mm])
    gap(6)
    h2("The 12 viral-check dimensions")
    table([
        ["Attention", "Retention", "Satisfaction", "Value"],
        ["Shareability", "Saveability", "Replayability", "Originality"],
        ["Authenticity", "Visual Quality", "Audience Fit", "Platform Fit"],
    ], ["", "", "", ""], [W / 4] * 4)
    small("Verdict: any hard risk -&gt; REJECT; any soft risk or weak dimension -&gt; "
          "PASS-WITH-CHANGES; otherwise PASS. Each dimension is scored on input quality against "
          "documented signals, with its evidence class.")

    # ================= PAGE 12: STUDIO =================
    story.append(PageBreak())
    h1("11. The studio: hands-on tools")
    table([
        ["studio/seed_demo_project.py", ("Builds a full project (idea -&gt; edit plan + viral "
         "check) so asur render can make the youtube/ package."),
         "python3 studio/seed_demo_project.py --idea \"...\" --project-id demo"],
        ["studio/render_demo.py", ("Idea -&gt; ASUR script -&gt; 9:16 reel with macOS voice, "
         "Ken-Burns motion and captions."), ("python3 studio/render_demo.py --idea \"...\" "
         "(writes outputs/render_out/)")],
        ["studio/edit_video.py", ("Your clip -&gt; 4 edit styles: punchy, cinematic, meme, "
         "beatcut (1080x1920), optional auto captions."),
         "python3 studio/edit_video.py --input clip.mp4 (writes outputs/edit_out/)"],
        ["studio/lyric_video/ingest.py", ("Song -&gt; song.wav + draft lyrics. Rights gate "
         "(--i-have-rights) and lyrics gate."), "python3 studio/lyric_video/ingest.py ..."],
        ["studio/lyric_video/timing.py", ("Vocal isolation (Demucs) + forced alignment -&gt; "
         "word timestamps, phrases, confidence report. --freeze locks it."),
         "python3 studio/lyric_video/timing.py --project ..."],
        ["studio/lyric_video/sync.py", ("Sync-test video with red word highlight to check "
         "timing by eye."), "python3 studio/lyric_video/sync.py --project ..."],
    ], ["Tool", "What it does", "How to run"], [46 * mm, 66 * mm, W - 112 * mm])
    small("Full lyric-video walkthrough: guides/ASUR-Lyric-Video-Guide.pdf.")

    # ================= PAGE 13: STATUS + ROADMAP =================
    story.append(PageBreak())
    h1("12. Honest status and what comes next")
    table([
        ["Phases P00-P10", ("Built: foundations, SCRIPT, state machine + CLI, firewall + queue, "
         "generation core + hero proof, editing, full render + QA, viral check, learning + "
         "publish, platform packs, real render + package.")],
        ["Tests", "309 passing. Lint clean on asur/ and studio/."],
        ["In progress (uncommitted)", ("P11 real prompts for generation: new adapter code "
         "for Kokoro, Stable Audio, faster-whisper and a test file "
         "(tests/test_generation_prompt_p11.py) that currently fails on purpose (tests written "
         "first).")],
        ["Known issues", ("2 type-check warnings (generation_plan.py, cli.py); FFmpeg on this Mac "
         "lacks drawtext so captions are not burned in.")],
        ["Fixed in this update", ("Render no longer fails when FFmpeg lacks drawtext: it renders "
         "clean cards and records why (honest provenance).")],
    ], ["Area", "State"], [40 * mm, W - 40 * mm])
    gap(6)
    h2("Roadmap")
    table([
        ["Next", "Finish P11 adapters (voice, music, captions) and make the P11 tests pass", "IN PROGRESS"],
        ["Next", ("Concepts that keep ASUR local: abstract base classes, worker pool, 4-hour "
         "reconciler, local event hooks, loopback gateway + WebSocket progress"), "PLANNED"],
        ["Later", "Wan 2.2 video clips; asur generate and asur viral-check commands", "PLANNED"],
        ["Optional", ("Live remote review (WebRTC + SFU + signalling) and PPP pricing &mdash; "
         "only behind a human gate, because they need the network"), "PLANNED"],
    ], ["When", "Goal", "Status"], [20 * mm, W - 52 * mm, 32 * mm])
    gap(8)
    story.append(rule(LINE, 0.75))
    gap(4)
    small("This guide is generated from a script. Whenever ASUR changes, re-run "
          "<font name='Courier'>python3 guides/make_brand_guide.py</font> to produce an updated "
          "copy. It does not update on its own. The previous edition is kept as "
          "guides/ASUR-Complete-Guide-v1.pdf (generator: guides/make_brand_guide_v1.py).")

    doc.build(story)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "ASUR-Complete-Guide.pdf"
    build(out)
    print("Wrote", out)
