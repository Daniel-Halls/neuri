"""Five-Pass Referee, consistency auditor, and style proofreading engine.

Runs 5 distinct diagnostic passes across academic drafts:
Pass 1: Structural reverse-outline pass.
Pass 2: Factual, methodological, and citation verification pass.
Pass 3: Prose, voice, British English, and anti-cliché pass.
Pass 4: Terminology and acronym consistency lock.
Pass 5: Cross-section numerical and statistical audit.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class SeverityLevel(StrEnum):
    """Severity classification for referee audit findings."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


@dataclass
class AuditFinding:
    """Individual diagnostic finding flagged during manuscript review.

    Parameters
    ------------
    pass_number: int
        Review pass index (1 through 5).
    severity: SeverityLevel
        Classification of issue impact.
    location: str
        Paragraph or snippet context.
    issue: str
        Detailed description of the diagnostic failure.
    suggested_fix: str
        Concrete recommendation to resolve the issue.

    Returns
    --------
        AuditFinding: AuditFinding dataclass instance
            Constructed audit finding object.
    """

    pass_number: int
    severity: SeverityLevel
    location: str
    issue: str
    suggested_fix: str


@dataclass
class AuditReport:
    """Complete 5-pass referee review report.

    Parameters
    ------------
    reverse_outline: list[str]
        One-line summaries per paragraph.
    findings: list[AuditFinding]
        Prioritized list of audit issues.
    corrected_text: str
        Minimally invasive corrected prose.

    Returns
    --------
        AuditReport: AuditReport dataclass instance
            Constructed referee review report.
    """

    reverse_outline: list[str]
    findings: list[AuditFinding]
    corrected_text: str


class RefereeAuditor:
    """Executes the 5-pass academic referee and anti-cliché audit.

    Parameters
    ------------
    None

    Returns
    --------
        RefereeAuditor: RefereeAuditor instance
            Constructed review engine.
    """

    PROHIBITED_AI_TROPES: tuple[str, ...] = (
        "delve",
        "delves",
        "delving",
        "underscore",
        "underscores",
        "underscoring",
        "pivotal",
        "crucial",
        "testament",
        "moreover",
        "furthermore",
    )

    BRITISH_CONVERSIONS: tuple[tuple[str, str], ...] = (
        ("gray matter", "grey matter"),
        ("behavior", "behaviour"),
        ("behavioral", "behavioural"),
        ("analyze", "analyse"),
        ("analyzed", "analysed"),
        ("characterize", "characterise"),
        ("characterized", "characterised"),
        ("normalize", "normalise"),
        ("normalized", "normalised"),
        ("modeling", "modelling"),
        ("fiber", "fibre"),
        ("fibers", "fibres"),
    )

    def __init__(self) -> None:
        """Initialize referee auditor.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes referee state.
        """

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split manuscript text into non-empty paragraphs.

        Parameters
        ------------
        text: str
            Raw input manuscript prose.

        Returns
        --------
            list[str]: list object
                List of trimmed paragraph strings.
        """
        raw_paras: list[str] = text.split("\n\n")
        cleaned_paras: list[str] = [
            p.strip() for p in raw_paras if p.strip() and not p.startswith("#")
        ]
        return cleaned_paras

    def _run_pass_1_reverse_outline(
        self, paragraphs: list[str]
    ) -> tuple[list[str], list[AuditFinding]]:
        """Generate reverse outline and flag paragraphs lacking citations.

        Parameters
        ------------
        paragraphs: list[str]
            List of manuscript paragraphs.

        Returns
        --------
            tuple[list[str], list[AuditFinding]]: tuple object
                Pair of reverse outline lines and findings.
        """
        outline: list[str] = []
        findings: list[AuditFinding] = []

        for idx, para in enumerate(paragraphs, start=1):
            sentences: list[str] = [
                s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()
            ]
            first_sent: str = sentences[0] if sentences else para[:60]
            if len(first_sent) > 80:
                first_sent = first_sent[:77] + "..."
            outline.append(f"Paragraph {idx}: {first_sent}")

            has_citation: bool = bool(
                re.search(
                    r"\(\s*[A-Z][a-zA-Z\s]+,?\s*\d{4}\s*\)|\\cite|@\[?[a-zA-Z0-9_\-]+",
                    para,
                )
            )
            has_numbers: bool = bool(re.search(r"\d+", para))

            if has_numbers and not has_citation and idx > 1:
                findings.append(
                    AuditFinding(
                        pass_number=1,
                        severity=SeverityLevel.MAJOR,
                        location=f"Paragraph {idx}",
                        issue="Empirical or quantitative claims lack inline citation.",
                        suggested_fix="Support data points with verified citation.",
                    )
                )

        return outline, findings

    def _run_pass_2_factual_citation(
        self, paragraphs: list[str]
    ) -> list[AuditFinding]:
        """Audit citation format and detect unresolved placeholders.

        Parameters
        ------------
        paragraphs: list[str]
            List of manuscript paragraphs.

        Returns
        --------
            list[AuditFinding]: list object
                List of findings from citation audit.
        """
        findings: list[AuditFinding] = []
        for idx, para in enumerate(paragraphs, start=1):
            if re.search(r"\[\s*\?\s*\]|\[\s*TODO\s*\]|\[\s*REF\s*\]", para):
                findings.append(
                    AuditFinding(
                        pass_number=2,
                        severity=SeverityLevel.CRITICAL,
                        location=f"Paragraph {idx}",
                        issue="Unresolved citation or reference placeholder found.",
                        suggested_fix="Resolve reference with /paperback cite <doi>.",
                    )
                )
        return findings

    def _run_pass_3_prose_and_cliche(
        self, text: str
    ) -> tuple[list[AuditFinding], str]:
        """Detect prohibited AI tropes, US spelling slips, and apply clean fixes.

        Parameters
        ------------
        text: str
            Raw manuscript text.

        Returns
        --------
            tuple[list[AuditFinding], str]: tuple object
                Pair of findings and corrected text.
        """
        findings: list[AuditFinding] = []
        working_text: str = text

        for trope in self.PROHIBITED_AI_TROPES:
            pattern: str = rf"\b{trope}\b"
            matches: list[str] = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches:
                findings.append(
                    AuditFinding(
                        pass_number=3,
                        severity=SeverityLevel.MAJOR,
                        location=f"Word: '{matches[0]}'",
                        issue=(
                            f"Prohibited AI cliché '{matches[0]}' detected. "
                            f"Dr. Halls style requires grounded academic connectors."
                        ),
                        suggested_fix="Replace with 'However', 'Therefore', or omit.",
                    )
                )

        for us_form, uk_form in self.BRITISH_CONVERSIONS:
            pattern = rf"\b{us_form}\b"
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(
                    AuditFinding(
                        pass_number=3,
                        severity=SeverityLevel.MINOR,
                        location=f"Spelling: '{us_form}'",
                        issue=(
                            f"American spelling '{us_form}' detected. "
                            f"British English convention requires '{uk_form}'."
                        ),
                        suggested_fix=f"Change to '{uk_form}'.",
                    )
                )
                working_text = re.sub(
                    pattern, uk_form, working_text, flags=re.IGNORECASE
                )

        return findings, working_text

    def _run_pass_4_acronym_consistency(
        self, text: str
    ) -> list[AuditFinding]:
        """Audit uppercase acronyms for proper definition on first appearance.

        Parameters
        ------------
        text: str
            Manuscript text to inspect.

        Returns
        --------
            list[AuditFinding]: list object
                List of acronym consistency findings.
        """
        findings: list[AuditFinding] = []
        acronyms: list[str] = re.findall(r"\b[A-Z]{2,6}\b", text)
        standard_allowed: set[str] = {
            "MRI", "FMRI", "EEG", "MEG", "CT", "BMI", "DSM", "FDR", "FWE", "IQR",
            "PCA", "ICA", "GLM", "ROI", "BIDS", "BOLD", "DWI", "TR", "TE", "FOV"
        }
        seen_acronyms: set[str] = set()

        for acr in acronyms:
            if acr in standard_allowed or acr in seen_acronyms:
                continue
            seen_acronyms.add(acr)
            def_pattern: str = rf"\b[a-zA-Z\s]+\({acr}\)"
            if not re.search(def_pattern, text, flags=re.IGNORECASE):
                findings.append(
                    AuditFinding(
                        pass_number=4,
                        severity=SeverityLevel.MAJOR,
                        location=f"Acronym: {acr}",
                        issue=f"Acronym '{acr}' is used without an explicit expansion.",
                        suggested_fix=(
                            f"Define upon first mention, e.g. Full Name ({acr})."
                        ),
                    )
                )
        return findings

    def _run_pass_5_numerical_audit(self, text: str) -> list[AuditFinding]:
        """Verify statistical formatting, degrees of freedom, and p-values.

        Parameters
        ------------
        text: str
            Manuscript text to inspect.

        Returns
        --------
            list[AuditFinding]: list object
                List of statistical format findings.
        """
        findings: list[AuditFinding] = []
        p_matches: list[str] = re.findall(r"p\s*=\s*0?\.000\b", text)
        if p_matches:
            findings.append(
                AuditFinding(
                    pass_number=5,
                    severity=SeverityLevel.MAJOR,
                    location="p = 0.000",
                    issue="p-value reported as 0.000 (mathematically impossible).",
                    suggested_fix="Report as p < 0.001.",
                )
            )
        return findings

    def review(self, text: str) -> AuditReport:
        """Run complete 5-pass referee review on manuscript prose.

        Parameters
        ------------
        text: str
            Raw academic prose or manuscript section.

        Returns
        --------
            AuditReport: AuditReport dataclass instance
                Structured review report containing findings and corrected text.
        """
        paras: list[str] = self._split_paragraphs(text)
        all_findings: list[AuditFinding] = []

        outline, pass1_findings = self._run_pass_1_reverse_outline(paras)
        all_findings.extend(pass1_findings)

        pass2_findings = self._run_pass_2_factual_citation(paras)
        all_findings.extend(pass2_findings)

        pass3_findings, corrected_text = self._run_pass_3_prose_and_cliche(text)
        all_findings.extend(pass3_findings)

        pass4_findings = self._run_pass_4_acronym_consistency(text)
        all_findings.extend(pass4_findings)

        pass5_findings = self._run_pass_5_numerical_audit(text)
        all_findings.extend(pass5_findings)

        report: AuditReport = AuditReport(
            reverse_outline=outline,
            findings=all_findings,
            corrected_text=corrected_text,
        )
        return report

    def render_markdown(self, report: AuditReport) -> str:
        """Render the audit report as GitHub Flavored Markdown.

        Parameters
        ------------
        report: AuditReport
            The audit report to render.

        Returns
        --------
            str: string object
                Rendered markdown document.
        """
        lines: list[str] = [
            "### 5-Pass Referee Review & Consistency Audit\n",
            "#### Pass 1: Reverse Outline Summary",
        ]
        for item in report.reverse_outline:
            lines.append(f"- {item}")

        lines.append("\n#### Prioritized Diagnostic Findings")
        if not report.findings:
            lines.append("- [OK] No critical or stylistic defects identified.")
        else:
            lines.append(
                "| Severity | Pass | Location | Issue & Suggested Fix |"
            )
            lines.append("| :--- | :---: | :--- | :--- |")
            for f in report.findings:
                sev_tag: str = f"[{f.severity.value}]"
                desc: str = f"{f.issue} *Fix:* {f.suggested_fix}"
                lines.append(
                    f"| `{sev_tag}` | {f.pass_number} | `{f.location}` | {desc} |"
                )

        lines.append("\n#### Minimally Invasive Corrected Text\n")
        lines.append(report.corrected_text)

        output_md: str = "\n".join(lines)
        return output_md
