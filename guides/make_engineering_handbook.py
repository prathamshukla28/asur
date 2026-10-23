"""Build the ASUR Engineering Handbook PDF.

An interview handbook: every engineering concept ASUR uses, explained in simple
English, with how ASUR uses it, a snippet to run, the questions an interviewer
asks about it, and which interview round asks them. No runbook, no roadmap.

Re-run it whenever the code changes (a launchd job also does this daily):

    python3 guides/make_engineering_handbook.py

Output: guides/ASUR-Engineering-Handbook.pdf

The state table, the firewall views and the platform table are read from the
code at build time. Everything else is hand-written. Same design rule as the
other guides: reportlab's built-in fonts have no arrow glyphs, so write "-&gt;".
"""

import datetime
import os
import re
import sys
from pathlib import Path

from make_brand_guide import (
    BG,
    BLUE,
    INK,
    LINE,
    MARGIN,
    RED,
    SOFT,
    S,
    band,
    kv_table,
    rule,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

PAGE_W, PAGE_H = A4
W = PAGE_W - 2 * MARGIN
ROOT = Path(__file__).resolve().parent.parent

MONO = ParagraphStyle(
    "mono", parent=S["cell"], fontName="Courier", fontSize=8.2, leading=11,
    textColor=colors.white,
)
NOTE = ParagraphStyle("note", parent=S["cell"], fontSize=9.5, leading=13.5)
TOC1 = ParagraphStyle(
    "toc1", parent=S["body"], fontSize=10.5, leading=17, textColor=INK,
)


# --- tables read from the code at build time ---------------------------------
def live():
    """The three tables that would go stale if typed by hand."""
    sys.path.insert(0, str(ROOT))
    from asur.orchestrator import states as st
    from asur.platforms import DEFAULT_PLATFORM, PLATFORM_REGISTRY
    from asur.tools import projection as proj

    states = []
    for i, name in enumerate(st.STATES):
        label = name
        if name in st.HUMAN_GATE_STATES:
            label = f"<b>{name}</b> (a human must approve)"
        elif st.is_terminal(name):
            label = f"{name} (end)"
        stage = st.stage_of(name)
        states.append([str(i), label, str(stage), st.cost_tier_for_stage(stage)])

    gen_view = proj.build_generation_view(brief={}, hooks={}, quality_floors={}, cost_policy={})
    viral_view = proj.build_viral_view(
        bundle_hashes={}, provenance={}, platform_facts={}, rubric_metadata={},
    )
    views = [
        [view["view"], ", ".join(k for k in view if k != "view"), ", ".join(sorted(forbidden))]
        for view, forbidden in ((gen_view, proj.GENERATION_FORBIDDEN), (viral_view, proj.VIRAL_FORBIDDEN))
    ]

    platforms = []
    for pid, pack in PLATFORM_REGISTRY.items():
        spec = pack.format_spec
        platforms.append([
            pid + (" (default)" if pid == DEFAULT_PLATFORM else ""),
            spec.aspect_ratio, f"{spec.width} x {spec.height}", f"{spec.default_duration_s:g} s",
        ])

    return {"states": states, "views": views, "platforms": platforms}


# --- small building blocks ------------------------------------------------
def c(text):
    """Inline code."""
    return f"<font name='Courier'>{text}</font>"


def code_block(text):
    lines = []
    for raw in text.strip("\n").split("\n"):
        esc = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Keep runs of spaces, so indentation and aligned comments survive.
        lines.append(re.sub(r"^ +| {2,}", lambda m: "&nbsp;" * len(m.group()), esc))
    t = Table([[Paragraph("<br/>".join(lines), MONO)]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def qa_box(question, answer):
    body = Paragraph(
        f"<b><font color='{RED.hexval()}'>Q.</font> {question}</b><br/>"
        f"<b><font color='{BLUE.hexval()}'>A.</font></b> {answer}", NOTE)
    t = Table([[body]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


class HandbookDoc(BaseDocTemplate):
    """Registers every chapter heading with the table of contents."""

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "h1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))


def build(out_path: Path):
    lv = live()
    built = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%d %B %Y")
    doc = HandbookDoc(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=14 * mm, bottomMargin=14 * mm,
        title="ASUR - Engineering Handbook", author="ASUR",
    )
    frame = Frame(MARGIN, 14 * mm, W, PAGE_H - 28 * mm, id="main")

    def paint_bg(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        canvas.setFillColor(BLUE)
        canvas.rect(0, PAGE_H - 6, PAGE_W, 6, stroke=0, fill=1)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SOFT)
        canvas.drawString(MARGIN, 8 * mm, "ASUR Engineering Handbook - built " + built)
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"page {_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=paint_bg)])
    story = []

    def gap(n=6):
        story.append(Spacer(1, n))

    def h1(t):
        # Start a new page only when the chapter would open in the bottom third.
        story.append(CondPageBreak(90 * mm))
        story.append(Spacer(1, 10))
        story.append(Paragraph(t, S["h1"]))
        story.append(rule(RED, 1.5))
        story.append(Spacer(1, 6))

    def p(t):
        story.append(Paragraph(t, S["body"]))

    def table(rows, head, widths):
        story.append(kv_table(rows, head, widths))
        gap(5)

    def code(t):
        story.append(code_block(t))
        gap(5)

    def qa(question, answer):
        story.append(KeepTogether([qa_box(question, answer)]))
        gap(5)

    def tryit(text, note="Run this yourself."):
        story.append(Paragraph("<b>Try it.</b> " + note, S["body"]))
        code(text)

    def asked(text):
        p("<b>Asked in.</b> " + text)
        gap(2)

    def h2(t):
        story.append(CondPageBreak(45 * mm))
        story.append(Paragraph(t, S["h2"]))

    def topic(title, meaning, in_asur):
        """One concept: what it means, then where ASUR uses it."""
        story.append(CondPageBreak(45 * mm))
        story.append(Paragraph(title, S["h2"]))
        p("<b>Simple meaning.</b> " + meaning)
        p("<b>In ASUR.</b> " + in_asur)

    # ================= COVER =================
    gap(12 * mm)
    story.append(Paragraph("ASUR", S["brand"]))
    story.append(Paragraph("Engineering Handbook", S["tagline"]))
    story.append(rule(BLUE, 2))
    gap(8)
    story.append(band("THE CONCEPTS BEHIND ASUR, FOR ENGINEERING INTERVIEWS", BLUE))
    gap(8)
    p("This handbook explains every engineering concept used in ASUR. Each concept has up to "
      "four parts:")
    table([
        ["Simple meaning", "What the idea is, in plain words."],
        ["In ASUR", "Where the code uses it, with the file name."],
        ["Try it", "A few lines you can run in a terminal to see the idea work."],
        ["Q and A", "The question an interviewer asks, and a short answer you can say."],
    ], ["Part", "What it gives you"], [36 * mm, W - 36 * mm])
    p("Read one chapter at a time. Type every 'Try it' snippet yourself; do not just read it. "
      "Then say each answer aloud in your own words. Chapter 14 has coding tasks and the "
      "follow-up questions interviewers ask about your own project.")

    # ================= CONTENTS =================
    story.append(PageBreak())
    story.append(Paragraph("Contents", S["h2"]))
    toc = TableOfContents()
    toc.levelStyles = [TOC1]
    story.append(toc)

    # ================= WHERE ASKED =================
    h1("Where these questions are asked")
    p("These questions are asked for backend, Python, platform and applied AI roles, mostly "
      "for people with two to six years of experience. They come up in these rounds:")
    table([
        ["Project round", ("'Explain your project.' Then they pick one part and go deeper until "
         "you cannot answer. Every company has this round."), "1, 14"],
        ["Fundamentals round", "Hashing, race conditions, atomic writes, locks, idempotency.",
         "2, 3"],
        ["Low-level design or machine coding round", ("'Design a workflow engine.' 'Design a "
         "plugin system.' You write working code in 45 to 90 minutes."), "4, 5, 14"],
        ["System design round", ("Pipelines, orchestration, review before release, and 'how "
         "would you scale this?'"), "4, 6, 14"],
        ["Python round", "Dataclasses, imports, subprocess, the standard library.", "12"],
        ["Testing and DevOps questions", "Test types, flaky tests, CI, linting.", "10"],
        ["Security questions", "Injection, trust boundaries, hashing versus signing.", "2.4, 11"],
        ["Domain round at video or AI companies", "Codecs, FFmpeg, diffusion, speech models.",
         "8, 9"],
    ], ["Round", "What they ask", "Chapters"], [48 * mm, W - 72 * mm, 24 * mm])
    table([
        ["Backend engineer", "1 to 6, 10, 11, 14"],
        ["Python developer", "2 to 5, 10, 12, 14"],
        ["Platform or DevOps engineer", "3, 4, 10, 11"],
        ["Applied AI or ML engineer", "5, 6, 7, 9"],
        ["Video or media engineer", "8, 9"],
        ["Test automation engineer (SDET)", "7, 10"],
    ], ["Role", "Most useful chapters"], [70 * mm, W - 70 * mm])
    h2("What this handbook does not cover")
    p("ASUR has no database, no web server and no network code. So you must prepare these "
      "from other sources:")
    table([
        ["Data structures and algorithms", ("Arrays, trees, graphs, dynamic programming. Most "
         "product companies have one or two rounds of this.")],
        ["SQL and databases", "Joins, indexes, transactions, normalisation."],
        ["Web and APIs", "HTTP, REST, authentication, caching, load balancing."],
    ], ["Topic", "What is asked"], [56 * mm, W - 56 * mm])
    h2("How to answer a project question")
    p("Use the same four steps for every answer about your project.")
    table([
        ["1. Problem", "One line: what needed solving.", ("'Saved outputs must never be lost "
         "or changed silently.'")],
        ["2. What I built", "The mechanism, in two lines.", ("'Every save writes a new "
         "version file with a checksum, created with O_EXCL.'")],
        ["3. Why this way", "The trade-off you accepted.", ("'It uses more disk, but I get "
         "full history and no lost updates.'")],
        ["4. What I would improve", "One honest weakness.", ("'A crash mid-write can leave a "
         "half file. I would write to a temp file and rename.'")],
    ], ["Step", "Say", "Example"], [38 * mm, 50 * mm, W - 88 * mm])

    # ================= 1. PROJECT =================
    h1("1. Explaining the project")
    asked("The project round. Every company, every level.")
    p("ASUR turns a one-line idea into a finished short video. It runs fully on your own "
      "computer. It needs no login, no API key and no internet.")
    code("""
idea -> research -> audience -> strategy -> hooks -> script -> quality gate
     -> visual plan -> small sample (a human approves)
     -> images, voice, music -> edit -> render with FFmpeg
     -> viral check -> publish package (a human approves)
     -> real metrics typed in -> learning for the next video
""")
    table([
        ["SCRIPT", c("asur/script/"), "Turns the idea into hooks and a script."],
        ["GENERATION", c("asur/generation/") + ", " + c("asur/editing/"),
         "Plans the visuals, makes the assets, edits and renders the video."],
        ["VIRAL CHECK", c("asur/viral_check/"), "Scores the result on 12 points and raises risk flags."],
        ["ORCHESTRATOR", c("asur/orchestrator/"), "Moves the project from one state to the next."],
        ["LEARNING", c("asur/learning/"), "Stores real results so the next video starts smarter."],
        ["CORE", c("asur/core/"), "Hashing, storage, gates and identity. Everything else uses it."],
    ], ["Part", "Code", "Job"], [30 * mm, 50 * mm, W - 80 * mm])
    p("ASUR has eight fixed rules. Each rule comes from one engineering concept, and each "
      "concept is explained later in this handbook.")
    table([
        ["LOCAL-01", "Runs only on the local machine.", "Local-first design"],
        ["HONEST-01", "Never shows one 'viral %' number.", "Honest measurement"],
        ["FIREWALL-01", "The maker and the checker never talk.", "Information hiding"],
        ["GATE-01", "If a check is missing, stop.", "Fail closed"],
        ["HUMAN-01", "A human approves important steps.", "Human in the loop"],
        ["PROV-01", "Every asset records where it came from.", "Provenance"],
        ["EXPLAIN-01", "Every decision has a written reason.", "Explainability"],
        ["VERSION-01", "Nothing is overwritten.", "Append-only storage"],
    ], ["Rule", "Simple meaning", "Concept"], [30 * mm, W - 76 * mm, 46 * mm])
    tryit("""
pip install -e .
mkdir demo
asur script --idea "why most people waste money on AI tools" --project demo
ls demo/.script/artifacts            # one folder per stage, one file per version
asur script --idea "why most people waste money on AI tools" --project demo
ls demo/.script/artifacts/script     # v0001 and v0002: nothing was overwritten
""", "Run this from the ASUR folder.")
    qa("Tell me about your project.",
       "ASUR is a local tool that takes one line of idea and produces a finished short video. "
       "The work moves through fixed states, and a gate checks every step. Every output is "
       "saved as a versioned file with a checksum, so nothing is lost or changed silently. "
       "A human approves the two costly steps: full generation and publishing.")
    qa("Does an AI model write the script?",
       "No. The script stages use fixed templates filled from the idea text. So the same idea "
       "always gives the same output, which makes it easy to test. AI models are used only for "
       "images, voice and music, and they are optional.")
    qa("Why local-first and not a cloud service?",
       "Three reasons: the user's content stays private, there is no server cost, and there are "
       "no keys that can leak. The trade-off is that the user needs a capable machine, and "
       "sharing work with a team is harder.")

    # ================= 2. HASHING =================
    h1("2. Hashing and data integrity")
    asked("The fundamentals round and security questions.")
    topic("2.1 Hash function (SHA-256)",
          "A hash function takes any data and gives a short fixed-size fingerprint. The same data "
          "always gives the same fingerprint. If even one character changes, the fingerprint "
          "changes completely. You cannot get the data back from the fingerprint.",
          "Every saved output carries the SHA-256 fingerprint of its content. The code is in "
          + c("asur/core/canonical.py") + ".")
    tryit("""
import hashlib
print(hashlib.sha256(b"hello").hexdigest())
print(hashlib.sha256(b"hellp").hexdigest())    # one letter changed, whole hash changed
""")
    qa("What are the properties of a good hash function?",
       "It is deterministic (same input, same output). It is one-way (you cannot reverse it). "
       "A small change in input gives a very different output. And it is very hard to find two "
       "inputs with the same hash, which is called a collision.")
    qa("Why SHA-256 and not MD5?",
       "MD5 is broken: people can create two different files with the same MD5 hash. SHA-256 "
       "has no known practical collision.")

    topic("2.2 Canonical JSON",
          "The same data can be written as JSON in many ways: different key order, different "
          "spacing. A hash works on bytes, so two equal objects could give two different hashes. "
          "Canonical form means one fixed way of writing the data, so equal data always gives "
          "equal bytes.",
          "ASUR sorts the keys, removes extra spaces, uses UTF-8 and adds one newline at the end. "
          "Then it hashes those bytes.")
    code("""
# asur/core/canonical.py
text = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                  separators=(",", ":"), allow_nan=False) + "\\n"
digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
""")
    tryit("""
import json
a = {"x": 1, "y": 2}
b = {"y": 2, "x": 1}
print(a == b)                                                           # True
print(json.dumps(a) == json.dumps(b))                                   # False
print(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))   # True
""")
    qa("Two dictionaries are equal but their hashes differ. Why?",
       "Because the hash is taken over bytes, not over the object. Key order or spacing was "
       "different when they were turned into text. The fix is to serialise in one canonical "
       "form before hashing.")

    topic("2.3 Checksum",
          "A checksum is a hash stored next to the data. Later you hash the data again and "
          "compare. If the two values differ, the data was damaged or changed.",
          c("save_artifact()") + " refuses to save if the checksum does not match the body. "
          + c("load_latest()") + " checks it again on every read. Both are in "
          + c("asur/core/workspace.py") + ".")
    tryit("""
shasum -a 256 demo/.script/index.json     # note the hash
echo " " >> demo/.script/index.json       # change one byte
shasum -a 256 demo/.script/index.json     # a different hash
""", "In a terminal, on any file.")
    qa("Why verify on read as well as on write?",
       "A file can be damaged after it is written: a disk error, a half-finished write, or "
       "someone editing it by hand. Checking on read means bad data is caught before it is used.")

    topic("2.4 Hashing versus signing",
          "A hash proves the data did not change. It does not prove who wrote it, because anyone "
          "can change the data and compute a new hash. A digital signature uses a private key, "
          "so it also proves who wrote the data.",
          "ASUR uses hashing only. It has no keys by design, so it protects against accidents "
          "and corruption, not against a person who has access to the folder.")
    qa("What is the difference between a hash, a MAC and a digital signature?",
       "A hash needs no key and gives integrity only. A MAC (such as HMAC) uses one shared "
       "secret key and proves the sender knew that key. A digital signature uses a private key "
       "to sign and a public key to verify, so anyone can verify but only the owner can sign.")

    topic("2.5 Content addressing",
          "Content addressing means the name of a thing is made from its content. Same content "
          "gives the same name. Changed content gives a new name. Git commits and Docker image "
          "layers work this way.",
          "An artifact id is the kind plus the first 12 characters of the body hash, for example "
          + c("script-3fa9c1d2e4b7") + ". This is done in " + c("asur/core/envelope.py") + ".")
    qa("What do you gain from content addressing?",
       "Three things. Duplicates are easy to find, because same content has the same name. "
       "Changes are easy to detect, because the name changes. And caching is safe, because a "
       "name can never point to different content later.")

    topic("2.6 Provenance and lineage",
          "Provenance is the record of where something came from. Lineage is the chain of inputs "
          "that led to an output.",
          "Each artifact has a " + c("sources") + " list with the id, version and checksum of "
          "every artifact it was built from. Each media file also records the model, the prompt, "
          "the seed and the licence that made it.")
    qa("Why record lineage?",
       "For debugging and for trust. When an output is wrong, you can walk back through its "
       "inputs to find the step that caused it. And you can prove which exact inputs produced "
       "the final video.")

    # ================= 3. STORAGE =================
    h1("3. Safe storage on disk")
    asked("The fundamentals round, and storage questions in system design.")
    topic("3.1 Append-only storage and versioning",
          "Append-only means you only add new data. You never edit or delete old data. Each "
          "change creates a new version beside the old one.",
          "Each save creates a new file such as " + c("v0002-script-....json") + " next to "
          + c("v0001") + ". The old file is never touched.")
    code("""
<project>/.script/
  index.json                           latest version of each kind
  artifacts/<kind>/v0001-<artifact_id>.json
  artifacts/<kind>/v0002-<artifact_id>.json
""")
    qa("What are the benefits and costs of append-only storage?",
       "Benefits: you have full history, you can go back to any version, and there are no lost "
       "updates because nobody overwrites. Costs: it uses more disk, and you need an index to "
       "find the latest version quickly.")

    topic("3.2 Race condition",
          "A race condition happens when two programs do the same thing at the same time and the "
          "result depends on who is faster. A common case is 'check, then act': both programs "
          "check that a file does not exist, then both write it, and one write is lost.",
          "Two runs could try to save the same version at the same time. ASUR prevents this with "
          "the exclusive create flag explained next.")
    qa("What is a TOCTOU bug?",
       "Time of check to time of use. You check a condition, and before you act on it, "
       "something else changes it. The fix is to make the check and the action one single "
       "step that cannot be split.")

    topic("3.3 Exclusive create (O_EXCL)",
          "O_EXCL is a flag for opening a file. It tells the operating system: create this file "
          "only if it does not exist, otherwise fail. The check and the create happen as one "
          "step, so two programs can never both succeed.",
          "Every artifact file is created with " + c("O_WRONLY | O_CREAT | O_EXCL") + ". If the "
          "file is already there, the save fails instead of overwriting.")
    code("""
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)   # fails if path exists
""")
    tryit("""
import os
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
os.close(os.open("demo.txt", flags))    # works: the file is created
os.open("demo.txt", flags)              # FileExistsError: it will not overwrite
""")
    qa("How do you make sure two processes never write the same file?",
       "Open the file with O_CREAT and O_EXCL. The operating system makes this one atomic step, "
       "so exactly one process creates the file and the other gets an error.")

    topic("3.4 Atomic write (write then rename)",
          "Atomic means all or nothing. If a program crashes in the middle of writing a file, "
          "the file is left half-written. The safe way is to write a temporary file first, then "
          "rename it over the real file. The rename is one step, so a reader sees either the "
          "full old file or the full new file.",
          "The index file " + c("index.json") + " is the only file that changes. It is written "
          "to a temporary file in the same folder and then swapped in with " + c("os.replace") + ".")
    tryit("""
import json, os, tempfile

def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)       # one step: readers see old or new, never half

atomic_write("index.json", {"script": 2})
""")
    qa("Why must the temporary file be in the same folder?",
       "A rename is atomic only inside one file system. If the temporary file is on another "
       "disk, the rename becomes a copy and a delete, which is not atomic.")

    topic("3.5 Lock file",
          "A lock makes sure only one worker does a job at a time. A lock file is a simple lock: "
          "whoever creates the file first owns the job.",
          "Before the checker evaluates a video, it creates " + c("&lt;task_id&gt;.claim") + " "
          "with O_EXCL. A second checker gets an error. This is in " + c("asur/tools/queue.py") + ".")
    qa("What is the risk of a lock file?",
       "If the owner crashes, the lock file stays and the job is blocked forever. This is "
       "called a stale lock. The usual fixes are a timeout, or storing the owner and time "
       "inside the lock so it can be released safely.")

    topic("3.6 Idempotency",
          "An operation is idempotent if doing it twice gives the same result as doing it once. "
          "It makes retries safe.",
          "Sealing the same bundle twice with the same bytes is allowed and changes nothing. "
          "Sealing it again with different bytes raises an error.")
    qa("Why is idempotency important in real systems?",
       "Networks and programs fail, so work gets retried. If an operation is not idempotent, a "
       "retry can charge a customer twice or create a duplicate record. Idempotent operations "
       "can be retried without fear.")

    topic("3.7 JSON Lines log",
          "JSON Lines is a file where each line is one small JSON object. You add a new line "
          "for each event. It is simple to append and simple to read line by line.",
          "The run log (" + c(".asur/runs/&lt;run_id&gt;.jsonl") + "), the hand-off queue and "
          "the hook memory (" + c(".script/memory/hooks.jsonl") + ") all use it.")
    tryit("""
import json
with open("log.jsonl", "a") as f:                     # "a" = append
    f.write(json.dumps({"event": "saved"}) + "\n")
events = [json.loads(line) for line in open("log.jsonl")]
print(events)
""")
    qa("Why JSON Lines and not one big JSON file?",
       "To add one record to a big JSON file you must rewrite the whole file. With JSON Lines "
       "you only append one line. A crash can damage only the last line, not the whole file.")

    # ================= 4. STATE MACHINE =================
    h1("4. State machine and gates")
    asked("Low-level design, machine coding and system design rounds.")
    topic("4.1 Finite state machine",
          "A state machine is a model where a thing is always in exactly one state, and it can "
          "move only along allowed paths. It makes long processes easy to follow, because you "
          "always know where you are and what can happen next.",
          "A project is always in one of 18 states. The only allowed move is one step forward. "
          "The list is in " + c("asur/orchestrator/states.py") + ", and the allowed moves are "
          "built from the order of the list, so a skip cannot be written by mistake.")
    table(lv["states"], ["#", "State", "Stage", "Cost"],
          [10 * mm, W - 60 * mm, 22 * mm, 28 * mm])
    tryit("""
STATES = ["DRAFT", "SCRIPTED", "RENDERED", "PUBLISHED"]
NEXT = dict(zip(STATES, STATES[1:]))      # each state -> the one after it

def advance(state):
    if state not in NEXT:
        raise ValueError("no move from " + state)
    return NEXT[state]

print(advance("DRAFT"))         # SCRIPTED
print(advance("PUBLISHED"))     # ValueError: it is the last state
""", "A forward-only state machine in ten lines.")
    qa("Why use a state machine instead of plain if/else code?",
       "With many steps, if/else code hides the current position inside many flags. A state "
       "machine has one clear state and one table of allowed moves. Illegal moves are "
       "impossible, and the process is easy to test and to log.")
    qa("Where are state machines used in the real world?",
       "Order status in e-commerce, payment status, TCP connections, CI pipelines, and "
       "workflow tools such as AWS Step Functions and Airflow.")

    topic("4.2 Gate",
          "A gate is a checkpoint between two steps. It runs some checks and decides if the "
          "work may move forward.",
          "A gate in " + c("asur/core/gate.py") + " returns one of three answers. It runs every "
          "check and keeps the worst answer.")
    table([
        ["SHIP", "Go ahead. Every check passed."],
        ["HOLD", "Wait. Something is missing, but nothing is wrong."],
        ["BLOCK", "Stop. Something is wrong."],
    ], ["Answer", "Meaning"], [28 * mm, W - 28 * mm])

    topic("4.3 Fail closed and fail open",
          "When a check itself breaks, the system must choose. Fail open means 'allow when "
          "unsure'. Fail closed means 'deny when unsure'. Safety systems should fail closed.",
          "If no checks are given, the gate returns HOLD. If a check crashes, the gate returns "
          "BLOCK. If a check returns an unknown word, the gate returns BLOCK. So a broken check "
          "can never pass by mistake.")
    tryit("""
RANK = {"SHIP": 0, "HOLD": 1, "BLOCK": 2}

def run_gate(checks):
    if not checks:
        return "HOLD"                   # nothing was checked
    worst = "SHIP"
    for check in checks:
        try:
            result = check()
        except Exception:
            result = "BLOCK"            # a broken check never passes
        if result not in RANK:
            result = "BLOCK"            # an unknown answer never passes
        worst = max(worst, result, key=RANK.get)
    return worst

print(run_gate([]))                                # HOLD
print(run_gate([lambda: "SHIP", lambda: 1 / 0]))   # BLOCK
""", "A fail-closed gate. This is the same logic as asur/core/gate.py.")
    qa("Give one example each of fail open and fail closed.",
       "Fail open: a door lock that opens when power is lost, so people can get out. Fail "
       "closed: a login system that rejects everyone when the password database is down. You "
       "choose based on which mistake is more costly.")

    topic("4.4 Human in the loop",
          "Human in the loop means a person must approve before the system does something "
          "costly or hard to undo. A related idea is separation of duties: the person who makes "
          "the work should not be the one who approves it.",
          "Two states need a person: the small sample before full generation, and the final "
          "publish. If nobody approves, the result is HOLD. If the maker approves their own "
          "work, it is recorded honestly as " + c("SELF_APPROVED") + ". The check uses the local "
          "user name and git email from " + c("asur/core/identity.py") + ".")
    qa("What is the four-eyes principle?",
       "An important action needs two different people: one to do it and one to approve it. "
       "Code review is the common example. It reduces mistakes and misuse.")

    topic("4.5 Orchestrator and control tokens",
          "An orchestrator is one central part that tells the other parts when to run. It does "
          "not do the work. It only tracks progress.",
          "The orchestrator in " + c("asur/orchestrator/orchestrator.py") + " carries only a "
          "small control token: state, gate, answer, digest and a retry count. It never carries "
          "the content itself.")
    code("""
step():
  1. find the next state
  2. if the next state is costly and the sample is not approved -> BLOCK
  3. run the gate for that state
  4. write one line to the run log
  5. SHIP -> move to the next state; otherwise stay and count the retry
""")
    qa("What is the difference between orchestration and choreography?",
       "In orchestration, one central controller tells each part what to do. In choreography "
       "there is no controller: each part reacts to events from the others. Orchestration is "
       "easier to follow and debug. Choreography is looser and scales well, but the full flow "
       "is harder to see.")

    topic("4.6 Allow-list and deny-list",
          "An allow-list names what is permitted and rejects everything else. A deny-list names "
          "what is banned and permits everything else. An allow-list is safer, because a new "
          "unknown item is rejected by default.",
          "The run log accepts only seven keys: state, next_state, gate, disposition, substate, "
          "digest, residency. Any other key raises an error, so private content cannot slip "
          "into the log.")
    qa("How do you stop secrets from leaking into logs?",
       "Use an allow-list at the logger: only named safe fields can be written. Do not log "
       "whole objects. This makes a leak impossible instead of just discouraged.")

    topic("4.7 Cheap work first",
          "If a mistake will be found anyway, find it at the cheapest step. Run fast, free "
          "checks before slow, costly work.",
          "Each stage has a cost level. The costly stages (full generation and render) are "
          "blocked until a human has approved a small sample.")
    qa("What does 'shift left' mean?",
       "Move checks earlier in the process. A bug found while writing code costs minutes. The "
       "same bug found in production costs hours and reputation.")

    # ================= 5. ARCHITECTURE =================
    h1("5. Architecture and design patterns")
    asked("Low-level design and Python rounds.")
    topic("5.1 Layers and the dependency rule",
          "In a layered design, code is split into groups, and each group may depend only on "
          "certain other groups. The stable central code should not depend on heavy or changing "
          "outer code.",
          "The control code (core, script, viral check, orchestrator) imports only the Python "
          "standard library. Heavy media libraries are used only inside the adapter files. So "
          "the core runs with zero installed packages.")
    qa("How do you keep an architecture rule from being broken over time?",
       "Turn the rule into an automated test. ASUR has a test that reads every control file "
       "and fails if it imports anything outside the standard library. A rule that lives only "
       "in a document gets broken.")

    topic("5.2 Adapter pattern",
          "An adapter is a thin wrapper that makes an outside tool fit the shape your code "
          "expects. Your code talks to the adapter, and the adapter talks to the tool. To "
          "change the tool, you change only the adapter.",
          "Each model has one file in " + c("asur/generation/adapters/") + ": FFmpeg, SDXL, "
          "Kokoro, Stable Audio, faster-whisper. Each takes a job and returns a result with "
          "provenance. The planning code never imports a model library.")
    qa("How would you replace the image model with a different one?",
       "Write one new adapter with the same input and output shape, and add one line to the "
       "routing table. The planning code and its tests do not change.")

    topic("5.3 Registry (dispatch table)",
          "A registry is a lookup table from a name to the code that handles it. It replaces a "
          "long if/elif chain. Adding a new case means adding one row.",
          c("_ROUTES") + " in " + c("asur/generation/dispatch.py") + " maps a model name to "
          "its adapter module and function.")
    code("""
_ROUTES = {
    "FFmpeg":     ("asur.generation.adapters.ffmpeg", "render"),
    "SDXL":       ("asur.generation.adapters.sdxl", "generate"),
    "Kokoro-82M": ("asur.generation.adapters.kokoro", "synthesize"),
}
module_path, fn_name = _ROUTES[model]
fn = getattr(importlib.import_module(module_path), fn_name)
""")
    qa("What is the open/closed principle?",
       "Code should be open for extension and closed for modification. You can add new "
       "behaviour without editing existing, tested code. A registry does this: a new model is "
       "a new row, not a change to old logic.")

    topic("5.4 Lazy import and optional dependencies",
          "A lazy import loads a library only at the moment it is needed, inside the function, "
          "not at the top of the file. An optional dependency is a library that is installed "
          "only by users who want that feature.",
          "The adapters import " + c("torch") + " and " + c("diffusers") + " inside the function "
          "body. The heavy libraries are in an optional install, " + c("asur[generation]") + ". "
          "The route table stores module names as text, so nothing heavy loads until a job runs.")
    tryit("""
def make_image(prompt):
    import torch            # loaded only when this function is called
    ...

# importing this file is instant, even if torch is not installed
""", "The pattern.")
    qa("When is a lazy import useful?",
       "When a library is slow to load or may not be installed. The program starts fast, and "
       "users who do not use that feature never need the library.")

    topic("5.5 Dependency injection",
          "Dependency injection means a function receives the things it needs as arguments, "
          "instead of creating or finding them itself. This makes the function easy to test, "
          "because a test can pass in a fake.",
          "Every builder accepts an " + c("identity=") + " argument. In real use it comes from "
          "the machine. In tests, a fixed identity is passed in, so tests do not depend on the "
          "machine's git settings.")
    tryit("""
def build(idea, identity=None):
    identity = identity or get_identity()      # real machine value by default
    ...

build("my idea", identity={"git_email": "test@example.com"})    # in a test
""", "The pattern.")
    qa("Why does dependency injection help testing?",
       "The test controls every input. It can pass a fake clock, a fake user or a temporary "
       "folder, so the result is the same on every machine.")

    topic("5.6 Configuration as data",
          "Instead of writing platform differences as if/else in many places, put them in one "
          "data object and pass that object around.",
          "A platform is one frozen dataclass, " + c("PlatformPack") + ", in "
          + c("asur/platforms/") + ". It holds size, aspect ratio and duration. Frozen means it "
          "cannot be changed after it is created.")
    table(lv["platforms"], ["Platform", "Aspect", "Size", "Default length"],
          [56 * mm, 24 * mm, 40 * mm, W - 120 * mm])
    tryit("""
from dataclasses import dataclass

@dataclass(frozen=True)
class Format:
    width: int
    height: int

f = Format(1080, 1920)
f.width = 720               # FrozenInstanceError: it cannot be changed
""")
    qa("What is an immutable object and why use one?",
       "It is an object that cannot change after creation. It is safe to share between many "
       "parts of the program, because no part can change it and surprise the others.")

    topic("5.7 Backward compatibility",
          "A change is backward compatible when existing users see no difference after it.",
          "The new " + c("platform=") + " argument is optional. Tests check that leaving it out "
          "gives output that is byte-for-byte the same as before.")
    qa("How do you add a feature without breaking existing users?",
       "Make the new option optional with a default that keeps the old behaviour. Then write "
       "a test that proves the old output is unchanged.")

    topic("5.8 Pipeline pattern",
          "A pipeline is a chain of steps where each step takes the output of the step before "
          "it. Each step does one job.",
          "Idea -&gt; research -&gt; audience -&gt; strategy -&gt; hooks -&gt; script. Each "
          "stage reads the latest saved artifact and writes its own.")
    qa("What is the benefit of small pipeline stages?",
       "Each stage can be tested alone, re-run alone, and replaced alone. When something "
       "fails, you know exactly which stage failed.")

    # ================= 6. FIREWALL =================
    h1("6. The firewall: keeping maker and checker apart")
    asked("System design rounds, and evaluation questions for AI roles.")
    topic("6.1 Goodhart's law",
          "When a measure becomes a target, it stops being a good measure. If the maker knows "
          "exactly how it will be scored, it learns to please the scorer instead of doing good "
          "work. Students who study only the exam questions are an example.",
          "GENERATION makes the video. VIRAL CHECK scores it. If the maker could see the scoring "
          "rules, the score would become meaningless. So the two never share data or code.")
    qa("Why should the tester be separate from the builder?",
       "A builder who knows the test can pass the test without solving the real problem. In "
       "machine learning this is called training on the test set. Keeping them apart keeps the "
       "result honest.")

    topic("6.2 Projection (filtered view)",
          "A projection is a filtered copy of data that contains only the fields one reader is "
          "allowed to see. This follows the principle of least privilege: give each part only "
          "what it needs.",
          "SCRIPT builds two views in " + c("asur/tools/projection.py") + ". Each view has a "
          "list of forbidden field names.")
    table(lv["views"], ["View", "Carries", "Forbidden names"], [34 * mm, 58 * mm, W - 92 * mm])
    p("Before a view is returned, " + c("conformance_scan()") + " walks every key and every "
      "text value. If a forbidden name appears, it raises " + c("FirewallLeak") + ". A second "
      "guard is a test that fails if the two packages import each other.")
    qa("What is the principle of least privilege?",
       "Every part of a system gets only the access it needs for its job, and nothing more. "
       "If that part has a bug or is misused, the damage stays small.")
    qa("What is the limit of a name-based filter?",
       "It blocks forbidden names, not forbidden meaning. The same value under a harmless key "
       "would pass. So it stops accidents, and new fields still need a human review.")

    topic("6.3 Digest binding",
          "Digest binding means an approval is tied to the exact bytes that were reviewed. If "
          "the content changes after review, the approval no longer matches.",
          "The hand-off queue in " + c("asur/tools/queue.py") + " has four steps. Release "
          "succeeds only when the digests agree.")
    table([
        ["seal", "Hash the bundle and store it. After this it is frozen."],
        ["claim", "One checker takes the job, using a lock file."],
        ["verdict", "The checker records the digest it looked at and its answer."],
        ["place", "Release only if the sealed digest and the verdict digest are the same."],
    ], ["Step", "What happens"], [24 * mm, W - 24 * mm])
    qa("How do you make sure the thing that was reviewed is the thing that ships?",
       "Record the hash of the content inside the approval. At release time, hash the content "
       "again and compare. If someone changed it after review, the hashes differ and the "
       "release is refused.")

    topic("6.4 Rule-based scoring",
          "A rule-based system gives a result from fixed, written rules, not from a trained "
          "model. Every result can be explained by pointing to the rule.",
          "The viral check scores 12 separate dimensions and never joins them into one "
          "percentage. Each score has a written reason. It reads facts that are passed to it; "
          "it does not yet measure the video file itself, so say that plainly if asked.")
    qa("Why not give one 'viral score' out of 100?",
       "Nobody can honestly predict virality with one number. One number hides which part is "
       "weak and gives false confidence. Separate scores with reasons tell the creator what "
       "to fix.")

    # ================= 7. DETERMINISM =================
    h1("7. Determinism and learning")
    asked("Testing questions, and data or AI roles.")
    topic("7.1 Deterministic code",
          "Deterministic means the same input always gives the same output. There is no hidden "
          "randomness and no dependence on time or machine.",
          "All script stages are deterministic templates. The same idea always produces the same "
          "hooks and the same script.")
    qa("Why is determinism valuable?",
       "Tests can check exact output. A bug can be reproduced by running the same input again. "
       "And two people get the same result on two machines.")

    topic("7.2 Hash-seeded variation",
          "Sometimes you want variety without real randomness. You can take a hash of the input "
          "and use it as the 'random' number. It looks random but is the same on every run.",
          "Each hook is scored on 15 dimensions. A small plus or minus is added to each score, "
          "taken from the SHA-256 of the hook text and the dimension name. This is in "
          + c("asur/script/hooks.py") + ".")
    code("""
jitter = (sha256(text + "|" + dimension) scaled to 0..1  - 0.5) * 12     # about +/- 6
""")
    tryit("""
import hashlib

def jitter(text):
    n = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    return (n / 0xFFFFFFFF - 0.5) * 12

print(jitter("my hook|clarity"))    # looks random
print(jitter("my hook|clarity"))    # exactly the same number again
""")
    qa("What is a flaky test and how do you avoid one?",
       "A flaky test passes sometimes and fails sometimes with no code change. Common causes "
       "are random values, time, network and test order. Avoid them by fixing the seed, "
       "passing the clock in, and using no network.")

    topic("7.3 Evidence classes",
          "Not every claim is equally sure. Labelling each claim with how strong its proof is "
          "stops a guess from being presented as a fact.",
          "Every claim gets one of four labels through " + c("evidence.claim()") + ".")
    table([
        ["VERIFIED_FACT", "Publicly stated or directly seen."],
        ["STRONG_EVIDENCE", "Supported by a credible study."],
        ["EMPIRICAL", "Measured from this creator's own videos."],
        ["HYPOTHESIS", "Believable, but not tested."],
    ], ["Label", "Meaning"], [40 * mm, W - 40 * mm])

    topic("7.4 Feedback loop",
          "A feedback loop takes the real result of an action and feeds it back to improve the "
          "next action.",
          "After publishing, the creator types the real numbers (views, completion, shares) "
          "into a file. " + c("asur/learning/") + " compares them with what was expected and "
          "appends the result to the hook memory. The next run reads that memory, so a hook "
          "that was used too often is marked as tired.")
    qa("How many data points do you need before trusting a pattern?",
       "One result proves nothing. You need many comparable cases, and you must compare with "
       "a baseline such as the creator's own average. With few samples you report it as a "
       "hint, not as a finding.")

    # ================= 8. MEDIA =================
    h1("8. Video and audio concepts")
    asked("Video, streaming and media companies.")
    topic("8.1 Container and codec",
          "A container is the file format that holds video and audio together, such as MP4. A "
          "codec is the method that compresses the video or audio inside it, such as H.264 for "
          "video and AAC for audio.",
          "ASUR renders an MP4 file with H.264 video and the " + c("yuv420p") + " pixel format, "
          "which plays on all phones.")
    tryit("""
ffmpeg -f lavfi -i color=c=navy:s=1080x1920:d=3 -r 30 -pix_fmt yuv420p card.mp4
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate \
        -of default=nw=1 card.mp4
# codec_name=h264  width=1080  height=1920  r_frame_rate=30/1
""", "Make a 3-second vertical clip, then ask ffprobe what is inside it.")
    qa("What is the difference between MP4 and H.264?",
       "MP4 is the box. H.264 is how the video inside the box is compressed. One MP4 file can "
       "hold H.264 or another codec, and the same H.264 video can sit inside MP4 or MKV.")

    topic("8.2 Resolution, aspect ratio and frame rate",
          "Resolution is the size in pixels, such as 1080 x 1920. Aspect ratio is the shape, "
          "such as 9:16 for vertical video. Frame rate is how many pictures are shown per "
          "second, such as 30 fps.",
          "These values come from the platform pack, so the same pipeline can produce a "
          "vertical reel or a wide YouTube video.")

    topic("8.3 Bitrate and keyframes",
          "Bitrate is how much data is used per second of video. Higher bitrate means better "
          "quality and a bigger file. A keyframe is a full picture; the frames between "
          "keyframes store only what changed.",
          "FFmpeg picks these during the render. Platforms re-compress every upload, so the "
          "render should be good quality to begin with.")
    qa("Why is video compressed with keyframes and changes?",
       "Most of the picture stays the same from one frame to the next. Storing only the "
       "changes saves a lot of space. Keyframes are needed so that playback can start or "
       "jump to a point.")

    topic("8.4 FFmpeg and the render",
          "FFmpeg is a free command-line tool that reads, changes and writes video and audio. "
          "A filter is one change, such as scale, crop or draw text. Concatenate means join "
          "clips end to end. Mux means put video and audio streams together in one file.",
          "The adapter in " + c("asur/generation/adapters/ffmpeg.py") + " makes one card per "
          "scene (an image scaled and cropped to fit, or a plain colour), burns the on-screen "
          "text with the " + c("drawtext") + " filter, joins the cards, and muxes in the voice "
          "or music.")
    tryit("""
import subprocess
subprocess.run(["ffmpeg", "-y", "-i", "card.mp4", "-vf", "scale=540:960", "small.mp4"],
               check=True, timeout=300)
""")
    qa("How do you run an external program safely from Python?",
       "Use " + c("subprocess.run") + " with the arguments as a list, not as one shell string. "
       "Then user text is passed as plain data and cannot become a command. Also set a timeout "
       "and check the exit code.")

    topic("8.5 Safe area",
          "Apps draw their own buttons and captions on top of a video. Text placed near the top "
          "or bottom edge gets hidden. The safe area is the middle part that stays visible.",
          c("asur/editing/captions.py") + " keeps a 12% band free at the top and the bottom.")

    topic("8.6 Decibels and ducking",
          "A decibel (dB) is the unit for loudness. It is a logarithmic scale: minus 6 dB is "
          "about half the amplitude. Ducking means lowering the music automatically while a "
          "person is speaking.",
          c("asur/editing/audio_mix.py") + " sets default levels: voice at -3 dB and music at "
          "-18 dB, so the music never covers the voice.")

    topic("8.7 Timeline",
          "A timeline is the data model of an edit: tracks (video, audio, text) that hold "
          "clips, and each clip has a start time and a length.",
          c("asur/editing/timeline.py") + " has three dataclasses: " + c("Clip") + ", "
          + c("Track") + " and " + c("Timeline") + ". Every edit creates a new version of the "
          "clip, so any change can be undone.")
    qa("What is a dataclass in Python?",
       "It is a class made mainly to hold data. The " + c("@dataclass") + " decorator writes "
       "the constructor, the comparison and the printing code for you. With "
       + c("frozen=True") + " the object cannot be changed after creation.")

    # ================= 9. AI MODELS =================
    h1("9. AI model concepts")
    asked("Applied AI and ML engineer roles.")
    topic("9.1 Diffusion model",
          "A diffusion model makes an image by starting from random noise and removing a little "
          "noise at each step, guided by the text prompt, until a clear picture appears.",
          "The SDXL adapter makes the background images. SDXL was trained on images of about "
          "one megapixel, so ASUR generates at 832 x 1216 and scales up.")
    table([
        ["Steps", "How many times noise is removed. More steps: slower, usually cleaner."],
        ["Guidance scale", "How strictly the image follows the prompt."],
        ["Seed", "The number that fixes the starting noise. Same seed and prompt: same image."],
    ], ["Setting", "Meaning"], [36 * mm, W - 36 * mm])
    qa("Why record the seed?",
       "For reproducibility. With the same model, prompt, settings and seed, you get the same "
       "image again. Without the seed, you can never recreate an image you liked.")

    topic("9.2 Text to speech and speech to text",
          "Text to speech (TTS) turns written text into a spoken voice. Speech to text (ASR) "
          "turns a voice recording into written text, with the time of each word.",
          "Kokoro makes the voice-over. faster-whisper listens to the voice and returns word "
          "timings, which are used to show captions at the right moment.")
    qa("How are captions timed to the voice?",
       "A speech-to-text model returns each word with a start and end time. The caption for a "
       "word is shown between those two times.")

    topic("9.3 Inference and hardware",
          "Training teaches a model. Inference uses a trained model to produce output. "
          "Inference runs on a GPU when one is available: CUDA on NVIDIA cards, MPS on Apple "
          "Silicon, and CPU as the slow fallback.",
          "ASUR only does inference. It never trains a model. The memory of the GPU (VRAM) "
          "decides which models a machine can run.")
    qa("What is the difference between training and inference?",
       "Training changes the model's weights using a lot of data, and it is slow and costly. "
       "Inference keeps the weights fixed and just runs the model on new input.")

    topic("9.4 Model licences",
          "A model that is free to download is not always free to use for business. Each model "
          "has a licence, and some allow research use only.",
          c("asur/generation/license_guard.py") + " keeps a list of models with risky licences. "
          "It checks the plan before any generation starts and names the asset that is the "
          "problem.")
    qa("Why check licences in code and not by hand?",
       "People forget. A check in code runs every time, and it runs before any costly work "
       "is done.")

    topic("9.5 Tests for code that needs a GPU",
          "Some code cannot run on a normal test server because it needs a GPU or a large "
          "download.",
          "The real model calls are marked " + c("# pragma: no cover") + " and are run by a "
          "person on a capable machine. Everything around them (planning, routing, error "
          "handling) is tested normally.")

    # ================= 10. TESTING =================
    h1("10. Testing and code quality")
    asked("Every backend interview; more deeply for SDET and DevOps roles.")
    topic("10.1 Unit and integration tests",
          "A unit test checks one small piece alone, and is fast. An integration test checks "
          "that several pieces work together, often with a real outside tool, and is slower.",
          "The unit tests use no network, no GPU and no FFmpeg. The integration tests in "
          + c("tests/integration/") + " call the real FFmpeg and skip themselves if it is not "
          "installed.")
    tryit("""
python3 -m pytest tests/test_core.py -q         # one file of unit tests
python3 -m pytest tests -q                      # all unit tests
python3 -m pytest tests -q -m integration       # the tests that need ffmpeg
""", "Run this from the ASUR folder.")
    qa("What is the test pyramid?",
       "Many fast unit tests at the bottom, fewer integration tests in the middle, and very "
       "few slow end-to-end tests at the top. This gives quick feedback and still covers the "
       "full system.")

    topic("10.2 Test isolation",
          "Each test should set up what it needs and leave nothing behind. A test must not "
          "depend on another test, on the network, or on the machine it runs on.",
          "Tests write into temporary folders and pass in a fixed identity. No test touches "
          "the network.")

    topic("10.3 Negative tests",
          "A positive test checks that correct input works. A negative test checks that wrong "
          "input is rejected in the right way.",
          "Every fail-closed path has a test that feeds it bad input and expects the exact "
          "error: a wrong checksum, a missing approver, a leaking view.")
    qa("How do you know a safety check really works?",
       "Break the rule on purpose and confirm the check fails. A check that has never failed "
       "may not be checking anything.")

    topic("10.4 Architecture tests",
          "An architecture test checks the structure of the code, not its behaviour.",
          c("tests/test_boundary.py") + " uses Python's " + c("ast") + " module to read the "
          "imports of every control file and fails on a forbidden one. "
          + c("tests/test_firewall.py") + " fails if the maker and the checker import each "
          "other.")
    tryit("""
import ast
tree = ast.parse(open("asur/core/gate.py").read())
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        print([n.name for n in node.names])
    elif isinstance(node, ast.ImportFrom):
        print(node.module)
""", "Print every import in a file without running the file.")
    qa("What is an AST?",
       "Abstract syntax tree. It is the code turned into a tree of nodes, such as imports, "
       "functions and calls. Tools read the tree to inspect code without running it. Linters "
       "work this way.")

    topic("10.5 Linting and type checking",
          "A linter reads code and reports style problems and likely bugs. A type checker "
          "verifies that values are used with the right types, without running the code.",
          "ASUR uses " + c("ruff") + " as the linter and " + c("mypy") + " as the type checker.")

    topic("10.6 Continuous integration",
          "Continuous integration (CI) runs the checks automatically on every push, so a "
          "problem is found within minutes.",
          "The workflow in " + c(".github/workflows/ci.yml") + " runs ruff, mypy and the tests. "
          "It also installs the package with no extras and confirms the core still imports.")
    qa("What is the difference between CI and CD?",
       "CI builds and tests every change automatically. CD goes one step further and delivers "
       "the tested change to users automatically.")

    topic("10.7 Architecture decision record",
          "An ADR is a short note that records one design decision: the situation, the choice "
          "and its results. It answers 'why is it built this way?' for future engineers.",
          "ASUR keeps its ADRs in " + c("docs/adr/") + ".")

    # ================= 11. SECURITY =================
    h1("11. Security concepts")
    asked("Security questions in backend rounds, and security roles.")
    topic("11.1 Trust boundary and threat model",
          "A trust boundary is the line between what you trust and what you do not. A threat "
          "model is a written list of what can go wrong and what you do about it.",
          "ASUR trusts the local user and the local disk. It does not trust downloaded model "
          "files, third-party packages or input media files.")
    qa("How do you do threat modelling?",
       "Answer four questions. What are we building? What can go wrong? What will we do about "
       "it? Did we do enough? It is also important to write down what you are not defending "
       "against.")

    topic("11.2 Supply-chain risk",
          "Every package you install is code written by someone else that runs with your "
          "permissions. If one package is hacked, your program is hacked.",
          "The core has zero third-party packages, so this risk is zero there. The risk exists "
          "only in the optional generation install.")
    qa("How do you reduce supply-chain risk?",
       "Use fewer dependencies. Pin exact versions. Scan them for known problems. And keep "
       "risky dependencies away from the sensitive part of the system.")

    topic("11.3 Command injection",
          "Injection happens when user text is treated as part of a command. If text is pasted "
          "into a shell command, special characters can run something else.",
          "On-screen text goes into an FFmpeg filter. The adapter escapes special characters "
          "in " + c("_escape_drawtext") + " and passes arguments as a list, never through a "
          "shell.")
    tryit("""
import subprocess
text = "hello; ls"
subprocess.run("echo " + text, shell=True)    # unsafe: also runs ls
subprocess.run(["echo", text])                # safe: prints the text as it is
""")
    qa("What is the general defence against injection?",
       "Keep code and data apart. Pass user input as a parameter, not by building a string. "
       "For SQL that means parameterised queries. For processes it means an argument list "
       "with no shell.")

    topic("11.4 Unsafe file formats",
          "Some file formats can run code when they are opened. Python's pickle is one: loading "
          "a pickle file from a stranger can execute their code.",
          "Old model files use pickle. The safer format is " + c("safetensors") + ", which holds "
          "only numbers and cannot run code.")
    qa("Why is pickle dangerous?",
       "Loading a pickle rebuilds objects by calling code named inside the file. An attacker "
       "can name any function, so loading the file runs their code.")

    topic("11.5 Identity versus authentication",
          "Identity is a name: who you say you are. Authentication is proof of that name, such "
          "as a password or a key.",
          "ASUR records identity only: the OS user and the git name and email. It has no "
          "authentication by design. This gives an honest record of who ran what, but it is "
          "not access control.")
    qa("What is the difference between authentication and authorisation?",
       "Authentication checks who you are. Authorisation checks what you are allowed to do. "
       "Login is authentication; a role or permission check is authorisation.")

    # ================= 12. PYTHON =================
    h1("12. Python features used")
    asked("The Python round.")
    table([
        [c("hashlib"), "Makes SHA-256 hashes."],
        [c("json"), "Reads and writes JSON; " + c("sort_keys") + " gives the canonical form."],
        [c("pathlib"), "Works with file paths as objects, not plain text."],
        [c("os.open") + ", " + c("os.replace"), "Exclusive create and atomic rename."],
        [c("subprocess"), "Runs FFmpeg as a separate program."],
        [c("argparse"), "Builds the command line: " + c("asur script") + ", " + c("asur run")
         + ", " + c("asur render") + "."],
        [c("dataclasses"), "Small data-holding classes; " + c("frozen=True") + " makes them fixed."],
        [c("importlib"), "Imports a module by its name as text, used for lazy loading."],
        [c("ast"), "Reads source code as a tree, used by the architecture test."],
        [c("getpass"), "Gets the current OS user name."],
        [c("pytest"), "The test runner. Markers separate unit and integration tests."],
    ], ["Module", "Used for"], [50 * mm, W - 50 * mm])
    qa("What is the difference between a module and a package in Python?",
       "A module is one " + c(".py") + " file. A package is a folder of modules. "
       + c("asur") + " is a package; " + c("asur/core/gate.py") + " is a module inside it.")
    qa("What does 'standard library only' mean and why does it matter?",
       "The code imports only what ships with Python. Nothing has to be installed, nothing can "
       "break from a package update, and there is no third-party code to audit.")

    # ================= 13. REVISION =================
    h1("13. One-line revision")
    table([
        ["Hash", "A fixed-size fingerprint of data."],
        ["Canonical form", "One fixed way to write data so equal data gives equal bytes."],
        ["Checksum", "A stored hash used to detect change."],
        ["Signature", "A hash made with a private key; proves who wrote it."],
        ["Content addressing", "Naming a thing by the hash of its content."],
        ["Lineage", "The chain of inputs behind an output."],
        ["Append-only", "Add new versions; never edit old ones."],
        ["Race condition", "The result depends on timing between two actors."],
        ["Atomic", "All or nothing; no half-done state is visible."],
        ["Idempotent", "Doing it twice equals doing it once."],
        ["State machine", "One current state and a table of allowed moves."],
        ["Gate", "A checkpoint that answers SHIP, HOLD or BLOCK."],
        ["Fail closed", "When unsure, deny."],
        ["Allow-list", "Name what is permitted; reject the rest."],
        ["Orchestrator", "A central controller that tracks progress."],
        ["Adapter", "A wrapper that makes an outside tool fit your code."],
        ["Registry", "A table from a name to its handler."],
        ["Lazy import", "Load a library only when it is needed."],
        ["Dependency injection", "Pass in what a function needs."],
        ["Immutable", "Cannot change after creation."],
        ["Least privilege", "Give each part only the access it needs."],
        ["Goodhart's law", "A measure that becomes a target stops measuring."],
        ["Digest binding", "An approval tied to the exact bytes reviewed."],
        ["Deterministic", "Same input, same output."],
        ["Container / codec", "The file box / the compression inside it."],
        ["Mux", "Join video and audio streams into one file."],
        ["Diffusion", "Make an image by removing noise step by step."],
        ["Seed", "The number that makes a random result repeatable."],
        ["Inference", "Using a trained model to produce output."],
        ["Unit / integration test", "One piece alone / pieces working together."],
        ["AST", "Source code as a tree."],
        ["CI", "Automatic checks on every change."],
        ["Trust boundary", "The line between trusted and untrusted."],
        ["Injection", "User text treated as a command."],
    ], ["Term", "One line"], [48 * mm, W - 48 * mm])

    # ================= 14. PRACTICE =================
    h1("14. Practice tasks and follow-up questions")
    asked("Machine coding rounds (the tasks) and the project round (the follow-ups).")
    h2("14.1 Coding tasks")
    p("Write each one from memory, with a small test. Then compare with the ASUR file.")
    table([
        ["1", "A function that gives the same hash for equal dictionaries.", "10 min", "2.2"],
        ["2", "An atomic file write.", "10 min", "3.4"],
        ["3", "A lock that only one process can take.", "10 min", "3.3, 3.5"],
        ["4", "A version store: each save makes v1, v2, v3 and never overwrites.", "30 min", "3.1"],
        ["5", "A forward-only state machine that logs every move.", "20 min", "4.1"],
        ["6", "A gate that runs checks and fails closed.", "15 min", "4.3"],
        ["7", "A logger that rejects any key outside an allow-list.", "15 min", "4.6"],
        ["8", "A plugin registry that loads a handler by name.", "15 min", "5.3"],
        ["9", "A test that fails if a file imports a banned module.", "20 min", "10.4"],
        ["10", "Join three clips and add an audio track with FFmpeg.", "20 min", "8.4"],
    ], ["#", "Task", "Time", "See"], [10 * mm, W - 54 * mm, 22 * mm, 22 * mm])
    h2("14.2 Follow-up questions about your project")
    qa("What happens if the power goes off in the middle of a save?",
       "The artifact file can be left half-written. On the next read its checksum does not "
       "match, so the bad data is rejected and never used. The index file is safe, because it "
       "is written to a temporary file and renamed. To improve it, I would write artifacts "
       "through a temporary file too.")
    qa("Two runs save the same version at the same moment. What happens?",
       "Both try to create the same file name with O_EXCL. The operating system lets exactly "
       "one succeed. The other gets an error instead of overwriting, so no data is lost.")
    qa("A render takes ten minutes and the program is closed. What happens?",
       "The saved artifacts stay on disk, but the orchestrator keeps its current state in "
       "memory, so the run starts again from the first state. The fix is to rebuild the state "
       "at start-up by replaying the run log.")
    qa("Why did you use files and not a database?",
       "It is a single-user tool on one machine. Files are simple, easy to inspect, and need "
       "no server. I would move to a database when there are many users, many writers at the "
       "same time, or a need to search across projects.")
    qa("How would you turn this into a service for 1,000 users?",
       "Put an API server in front. Each request becomes a job in a queue. Worker machines "
       "with GPUs take jobs from the queue. Media files go to object storage, named by their "
       "hash. Project state and versions go to a database. Add login, and send progress to "
       "the browser. The state machine and the gates stay the same.")
    qa("What is the weakest part of your project?",
       "The viral check. It scores facts that are passed to it; it does not measure the video "
       "file. I would first read real facts from the file with ffprobe, then compare the "
       "scores with real results from published videos to see if the scores mean anything.")
    qa("How do you know your safety checks work?",
       "Each one has a negative test that breaks the rule on purpose and expects the exact "
       "error. A check that has never been seen to fail may not be checking anything.")

    doc.multiBuild(story)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "ASUR-Engineering-Handbook.pdf"
    tmp = out.with_suffix(".building.pdf")
    build(tmp)
    os.replace(tmp, out)
    print("Wrote", out)
