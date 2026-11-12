"""Build the reviewed CALIBRE v4 implementation plan as a Word document."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "CALIBRE_v4_Implementation_and_Remediation_Plan.docx"


def shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    element = OxmlElement("w:shd")
    element.set(qn("w:fill"), fill)
    props.append(element)


def set_cell_text(cell, text: str, bold: bool = False) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Aptos"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    run.font.size = Pt(8.5)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for idx, heading in enumerate(headers):
        cell = table.rows[0].cells[idx]
        shade(cell, "1F4E78")
        set_cell_text(cell, heading, True)
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
        cell.width = Inches(widths[idx])
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            if row_index % 2:
                shade(cells[idx], "F3F7FA")
            cells[idx].width = Inches(widths[idx])
            set_cell_text(cells[idx], value)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.add_run(item)


def main() -> None:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    styles["Normal"]._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    styles["Normal"].font.size = Pt(10.5)
    for name, size in (("Title", 22), ("Heading 1", 15), ("Heading 2", 12)):
        styles[name].font.name = "Aptos Display" if name != "Normal" else "Aptos"
        styles[name]._element.rPr.rFonts.set(qn("w:ascii"), styles[name].font.name)
        styles[name]._element.rPr.rFonts.set(qn("w:hAnsi"), styles[name].font.name)
        styles[name].font.size = Pt(size)
        styles[name].font.color.rgb = RGBColor(0, 0, 0)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title.add_run("CALIBRE v4 Implementation and Remediation Plan")
    intro = doc.add_paragraph()
    intro.add_run("Decision. ").bold = True
    intro.add_run(
        "Migrate the working PULSE and SIA codebase toward a durable evidence-verification platform without rewriting or overstating the existing system. "
        "This plan identifies current gaps, fixes the Day-0 irreversible record format, and defines gated follow-on work."
    )

    doc.add_heading("Scope and conclusion", level=1)
    doc.add_paragraph(
        "The current repository is not the empty implementation described by its README. It contains a PULSE Formula 1 stream application, Kafka and Flink integrations, a React dashboard, captured data, tests, and an embedded SIA v3 integrity engine. "
        "CALIBRE v4 is therefore a platform migration: its durable archive, specification, pack, and verifier boundaries must be established before operational components are generalized."
    )
    doc.add_paragraph(
        "CALIBRE may support feed-health monitoring and human-led forensic review. It must not claim to replace the official measurement system, decide sporting liability, or automatically convert a measurement margin into a sanction."
    )

    doc.add_heading("Inputs and planning limitation", level=1)
    doc.add_paragraph(
        "The supplied Design Rationale v4.0, existing PULSE documentation, source, captures, Kafka implementation, tests, and SIA core were reviewed. The rationale cites a companion CALIBRE Blueprint v4 Durable Platform document. That file is not present in the supplied attachment or repository, so its section references must be reconciled before Spec v1.0 is frozen."
    )

    doc.add_heading("Present state compared with v4", level=1)
    add_table(doc, ["Area", "Current condition", "Required direction"], [
        ["Domain model", "F1 scope classes, roles, and provider aliases are embedded in contracts and bridge code.", "Move vocabulary into versioned domain packs; prove the boundary with a second pack."],
        ["History", "Kafka and capture folders serve as operational history; some raw topics have short retention.", "Archive immutable raw payloads and evidence metadata independently of transport."],
        ["Hash and time", "Bare SHA-256 values and implicit UTC assumptions exist in legacy paths.", "Use tagged digests and explicit time-scale/leap-table references at durable boundaries."],
        ["Rules", "Limits and calibration-like values are embedded in F1 contracts.", "Use effective-dated rule, layout, and calibration references bound at decision opening."],
        ["Execution", "Kafka/Flink are central implementation paths.", "Make deterministic batch replay mandatory and treat streaming as a replaceable profile."],
        ["Reproducibility", "Hash chains and tests exist, but no portable verifier/capsule requirement.", "Ship archive bundles with a standalone verifier and pinned evaluator capsule."],
    ], [1.2, 2.6, 2.6])

    doc.add_heading("Remediation register", level=1)
    add_table(doc, ["ID", "Issue", "Fix and status"], [
        ["V4-01", "README says implementation has not started.", "Reconcile README and legacy PULSE documents after approved migration inventory. Planned."],
        ["V4-03", "Companion Blueprint is absent.", "Obtain it and reconcile all rationale references before Spec v1.0. Blocked on supplied artifact."],
        ["V4-04", "Scope and default contracts are F1-shaped.", "Add DomainPack boundary now; migrate SIA contract schema after second-pack proof. Foundation implemented."],
        ["V4-05/06", "Provider aliases and public-feed corroboration are inconsistent.", "F1 source-pack lineage now blocks public independence claims; move bridge aliases and profile enforcement into it. In progress."],
        ["V4-07", "Kafka retention is not a durable record.", "Create immutable archive bundles with raw entries, evidence, and verifier. Foundation implemented."],
        ["V4-08/09", "Digests are bare and durable records lack time-scale declaration.", "Tagged sha256 plus required time scale and leap-table reference. Foundation implemented."],
        ["V4-10/11", "References are not consistently effective-dated and thresholds hide uncertainty.", "Fail-closed reference registry and policy-neutral threshold witness. Foundation implemented."],
        ["V4-12", "No clean-machine verifier/capsule.", "Bundle a standard-library verifier now; add pinned capsule in Phase 1b. Partially implemented."],
        ["V4-13", "Broad exception swallowing occurs in runtime modules.", "Replace with logged, bounded recovery or propagated failures and tests. Planned."],
        ["V4-14/15", "Full baseline suite needs infra and bridge mutates sys.path.", "Batch-v1 now verifies deterministic archive inputs; split CI jobs and package SIA behind a stable evaluator adapter. In progress."],
        ["V4-16/17", "Calibration tolerances and agent names are legacy assumptions.", "Require calibration evidence; migrate to functional archetypes through packs. Planned."],
    ], [0.7, 2.2, 3.5])

    doc.add_heading("Implemented Day 0 foundation", level=1)
    add_bullets(doc, [
        "Algorithm-tagged durable sha256 digests with explicit, opt-in support for reading legacy bare v3 hashes.",
        "Data-regime and time-scale types. Every v4 archive requires a leap-second-table identifier and version.",
        "Versioned domain packs that validate scope fields outside the F1-specific kernel.",
        "Effective-dated reference registry for rule regimes, layouts, and calibration records. Ambiguity fails closed.",
        "Policy-neutral threshold witness: observed value, threshold, margin, combined uncertainty, and below, above, or indeterminate classification.",
        "Immutable archive-bundle creator: safe paths, no silent overwrite, payload digests, manifest digest, and a copied standard-library verifier.",
        "F1 source-pack lineage that marks public feeds with a shared upstream and only permits institutional independence when distinct approved origins prove it.",
        "Batch-v1 deterministic archive replay for NDJSON input accounting, plus an explicit legacy-capture migrator that defaults old data to LAB.",
        "Automated coverage for legacy digest handling, guard bands, reference selection, clean-machine verifier invocation, and tampering.",
    ])

    doc.add_heading("Architecture target", level=1)
    doc.add_paragraph(
        "The long-lived compatibility waist is raw entries, archive manifest, pack and effective references, deterministic evaluator, assessments and revision chain, and verifier bundle. Kafka, Flink, FastAPI, React, provider adapters, advisory learning, and the present Python evaluator are execution-profile details outside that waist."
    )
    doc.add_paragraph(
        "Each archive will include immutable raw payloads; pack id and version; regime; time-scale/leap-table declaration; effective-reference bindings; capsule identity; outputs; and a verifier that needs neither network nor repository."
    )

    doc.add_heading("Delivery gates", level=1)
    add_table(doc, ["Phase", "Work", "Exit gate"], [
        ["0", "Source/licence inventory; Blueprint reconciliation; retain/adapt/migrate/retire inventory; two-person review assignment.", "G0: approved source register and no unsupported independence claims."],
        ["1a", "Archive one LAB and one approved historical capture; tamper and clean-machine verification; legacy mapping.", "G1: every produced archive has tagged digest, time scale, pack, regime, and verifier."],
        ["1b", "Freeze normative schemas/specs; golden corpus; bind reference versions; evaluator capsule and CI verification.", "G2: two reviewers approve Spec v1.0 and corpus/capsule checks pass."],
        ["2", "Mandatory deterministic batch profile; streaming adapter; source-pack lineage; F1 and second pack; regime profiles.", "G3: two packs run without kernel edits and public claims degrade correctly."],
        ["3", "Taxonomy benchmark, annual pack/calibration/corpus calendar, upgrade drills, adoption evidence.", "G4: living benchmark and governance process operate with visible limits."],
        ["Horizon 2", "Second evaluator from specification only; differential tests; digest renewal policy.", "G5: differences are explicit spec changes, never silent code drift."],
    ], [0.65, 3.7, 2.05])

    doc.add_heading("Nonnegotiable safeguards", level=1)
    add_bullets(doc, [
        "Do not rewrite historical SIA identifiers; preserve an explicit legacy mapping.",
        "Do not claim independent corroboration from PUBLIC feeds that share an upstream.",
        "Do not substitute synthetic observations for unavailable source evidence; LAB is always declared.",
        "Do not treat a threshold witness as a compliance decision or penalty.",
        "Do not retire PULSE, Kafka/Flink, or SIA until archive, corpus, and deterministic batch evidence prove the transition.",
        "Do not freeze v1.0 until the missing Blueprint and Day-0 records have independent review.",
    ])

    doc.add_heading("Verification and acceptance", level=1)
    doc.add_paragraph(
        "Every code change runs fast unit behavior checks. Every archive runs manifest, path-safety, payload, and tamper checks. Releases run a clean-machine verifier and evaluator-capsule replay. Semantic releases run the golden corpus and publish a versioned difference report. Source, rule, calibration, and execution-profile reviews are scheduled before their associated operational use."
    )
    doc.add_paragraph(
        "This increment is accepted when archive destinations cannot be overwritten; traversal paths and tampered payloads fail verification; new digests are tagged; archives require time-scale metadata; ambiguous effective references fail closed; a 0.1 km/h margin with 0.11 km/h uncertainty is indeterminate; the bundled verifier runs using only the standard library; and the v4 foundation tests pass.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
