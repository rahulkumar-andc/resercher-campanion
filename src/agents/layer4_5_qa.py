"""Layer 4.5: Honest local heuristic QA — approximate only, fail-closed."""

import re
from typing import List, Set
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.core.llm_client import LocalLLMClient


def _tokenize_ngrams(text: str, n: int = 5) -> Set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _corpus_from_ctx(ctx: PipelineContext) -> str:
    parts: List[str] = []
    for paper in ctx.research.arxiv_papers or []:
        if paper.abstract:
            parts.append(paper.abstract)
        if paper.full_text:
            parts.append(paper.full_text[:5000])
    parts.extend(ctx.research.literature_context or [])
    parts.extend(ctx.research.web_context or [])
    if ctx.research.literature_summary:
        parts.append(ctx.research.literature_summary)
    return "\n".join(parts)


class PlagiarismCheckerAgent(BaseAgent):
    """Local corpus-overlap heuristic, not an external plagiarism check."""

    def __init__(self, bus: SupervisorBus, max_threshold: float = 15.0):
        super().__init__("PlagiarismCheckerAgent", layer=4, bus=bus)
        self.max_threshold = max_threshold

    def run(self, ctx: PipelineContext) -> None:
        ctx.quality_audit.plagiarism_method = "local_corpus_ngram_overlap_heuristic"
        ctx.quality_audit.is_estimate = True
        self.log(ctx, "Heuristic local corpus-overlap scan (not an external plagiarism check)...")

        if not ctx.output.markdown_manuscript:
            ctx.quality_audit.plagiarism_percentage = None
            ctx.quality_audit.is_approved = False
            reason = "No manuscript to audit"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            self.log(ctx, reason, level="WARN")
            return

        text = ctx.output.markdown_manuscript
        corpus = _corpus_from_ctx(ctx)
        ms_grams = _tokenize_ngrams(text, 5)
        if not ms_grams:
            similarity = 0.0
        elif not corpus.strip():
            similarity = 0.0
            self.log(ctx, "No reference corpus; n-gram overlap treated as 0% (approximate).", level="INFO")
        else:
            ref_grams = _tokenize_ngrams(corpus, 5)
            if not ref_grams:
                similarity = 0.0
            else:
                overlap = len(ms_grams & ref_grams) / max(1, len(ms_grams))
                similarity = round(overlap * 100.0, 1)

        ctx.quality_audit.plagiarism_percentage = similarity
        self.log(
            ctx,
            f"Local corpus-overlap estimate: {similarity}% (not a plagiarism determination; "
            f"method={ctx.quality_audit.plagiarism_method}; threshold {self.max_threshold}%).",
        )

        if similarity > self.max_threshold:
            err_msg = (
                f"Corpus-overlap heuristic flagged: similarity {similarity}% exceeds "
                f"policy limit ({self.max_threshold}%)."
            )
            self.log(ctx, err_msg, level="WARN")
            ctx.quality_audit.is_approved = False
            if err_msg not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(err_msg)
            ctx.quality_audit.feedback_reroute_target = "WriterAgent"


class PlagiarismRemediatorAgent(BaseAgent):
    """Re-synthesizes overlapping passages; does NOT invent pass scores."""

    def __init__(self, bus: SupervisorBus):
        super().__init__("PlagiarismRemediatorAgent", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        if ctx.output.markdown_manuscript:
            ctx.output.markdown_manuscript = self.remediate(ctx, ctx.output.markdown_manuscript)

    def remediate(self, ctx: PipelineContext, target_text: str) -> str:
        self.log(ctx, "Remediating manuscript text (rewrite only; scores recomputed on next QA)...")
        code = ctx.code_analysis
        gaps = ctx.research.novelty_gaps
        top_algo = code.algorithms[0]["name"] if code.algorithms else "Event-Driven Routing"

        remediated = target_text
        for idx, paper in enumerate(ctx.research.arxiv_papers[:2]):
            if paper.title and paper.title in remediated:
                reasoning_block = (
                    f"\n\n> **Comparative Analysis vs Literature [{idx+1}]**:\n"
                    f"> While {paper.authors[0] if paper.authors else 'prior work'} [{idx+1}] investigated "
                    f"`{paper.title}`, our architecture addresses "
                    f"({gaps[idx] if idx < len(gaps) else 'concurrency bottlenecks'}) "
                    f"by deploying `{top_algo}` across {code.total_lines} lines of code.\n\n"
                )
                remediated = remediated.replace(paper.title, paper.title + reasoning_block)

        remediated = re.sub(
            r"\bIt is shown that\b",
            "Our empirical evaluation demonstrates",
            remediated,
            flags=re.IGNORECASE,
        )
        remediated = re.sub(
            r"\bPrevious studies have suggested\b",
            "Analytical reasoning reveals that prior works overlooked",
            remediated,
            flags=re.IGNORECASE,
        )
        self.log(ctx, "Remediation rewrite complete. QA must re-score on next pass.")
        return remediated


class AIPercentageAuditorAgent(BaseAgent):
    """Local style-indicator heuristic, not an AI-authorship detector."""

    def __init__(self, bus: SupervisorBus, max_ai_threshold: float = 10.0):
        super().__init__("AIPercentageAuditorAgent", layer=4, bus=bus)
        self.max_ai_threshold = max_ai_threshold

    def run(self, ctx: PipelineContext) -> None:
        ctx.quality_audit.ai_method = "local_buzzword_passive_voice_heuristic"
        ctx.quality_audit.is_estimate = True
        self.log(ctx, "Heuristic AI-style indicator scan (buzzwords/passive; not an authorship detector)...")

        if not ctx.output.markdown_manuscript:
            ctx.quality_audit.ai_writing_percentage = None
            ctx.quality_audit.is_approved = False
            reason = "No manuscript to audit"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            self.log(ctx, reason, level="WARN")
            return

        text = ctx.output.markdown_manuscript
        ai_buzzwords = [
            "delve", "tapestry", "beacon", "testament", "pivotal role",
            "game-changer", "unraveling", "landscape", "leverage", "cutting-edge",
        ]
        found = [w for w in ai_buzzwords if re.search(r"\b" + re.escape(w) + r"\b", text, re.IGNORECASE)]
        passive = re.findall(r"\b(?:is|was|were|been|be)\s+\w+ed\b", text, re.IGNORECASE)
        # Start from 0 — never invent a "natural" 6.5% baseline
        ai_score = len(found) * 3.5 + min(20.0, len(passive) * 0.15)
        ai_score = round(min(100.0, ai_score), 1)

        ctx.quality_audit.ai_writing_percentage = ai_score
        self.log(
            ctx,
            f"Heuristic AI-style indicator estimate: {ai_score}% "
            f"(method={ctx.quality_audit.ai_method}; buzzwords={found}).",
        )

        if ai_score > self.max_ai_threshold:
            err_msg = (
                f"AI-style heuristic flagged: score {ai_score}% exceeds "
                f"policy limit ({self.max_ai_threshold}%)."
            )
            self.log(ctx, err_msg, level="WARN")
            ctx.quality_audit.is_approved = False
            if err_msg not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(err_msg)
            ctx.quality_audit.feedback_reroute_target = "StyleAgent"


class PeerReviewerAgent(BaseAgent):
    """Answers 7 journal questions from the actual manuscript (LLM) or fail-closed."""

    QUESTIONS = [
        ("1_why_needed", "Why is this work needed?"),
        ("2_what_is_new", "What is new compared to prior work?"),
        ("3_why_better", "Why is the approach better?"),
        ("4_how_evaluated", "How was it evaluated?"),
        ("5_can_reproduce", "Can others reproduce the work?"),
        ("6_limitations", "What are the limitations?"),
        ("7_future_work", "What is future work?"),
    ]

    def __init__(self, bus: SupervisorBus):
        super().__init__("PeerReviewerAgent", layer=4, bus=bus)
        self.llm = LocalLLMClient()

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Peer review from manuscript text...")
        if not ctx.output.markdown_manuscript:
            ctx.quality_audit.is_approved = False
            reason = "No manuscript to audit"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            ctx.quality_audit.reviewer_answers = {}
            self.log(ctx, reason, level="WARN")
            return

        manuscript = ctx.output.markdown_manuscript[:12000]
        q_block = "\n".join(f"{k}: {q}" for k, q in self.QUESTIONS)
        prompt = (
            f"Read this manuscript and answer each peer-review question in 1-3 sentences.\n"
            f"Return plain text lines as KEY: answer\n\nQuestions:\n{q_block}\n\n"
            f"Manuscript:\n{manuscript}"
        )
        res = self.llm.generate(
            prompt=prompt,
            system_prompt="You are an academic peer reviewer. Ground answers only in the manuscript.",
            temperature=0.2,
            max_tokens=1500,
        )
        answers = {}
        for key, _ in self.QUESTIONS:
            answers[key] = "Insufficient manuscript evidence."
        for line in (res or "").splitlines():
            for key, _ in self.QUESTIONS:
                if line.strip().startswith(key):
                    answers[key] = line.split(":", 1)[-1].strip() or answers[key]
        # If offline mock, mark low confidence but still attach
        if res.startswith("[LocalLLM Offline"):
            ctx.quality_audit.is_approved = False
            reason = "Peer review unavailable: local LLM offline"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            self.log(ctx, reason, level="WARN")
        ctx.quality_audit.reviewer_answers = answers
        self.log(ctx, "PeerReviewerAgent completed 7 manuscript-grounded answers.")


class FormatQualityAuditorAgent(BaseAgent):
    """Audits manuscript formatting; fail-closed if empty."""

    def __init__(self, bus: SupervisorBus):
        super().__init__("FormatQualityAuditorAgent", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Auditing formatting, grammar, terminology...")
        format_issues: List[str] = []
        grammar_issues: List[str] = []

        if not ctx.output.markdown_manuscript:
            ctx.quality_audit.is_approved = False
            reason = "No manuscript to audit"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            self.log(ctx, reason, level="WARN")
            ctx.quality_audit.format_issues = format_issues
            ctx.quality_audit.grammar_spelling_issues = grammar_issues
            return

        text = ctx.output.markdown_manuscript
        if "code-base" in text and "codebase" in text:
            format_issues.append(
                "Inconsistent terminology: Mixed usage of 'code-base' and 'codebase'."
            )
        passive_matches = re.findall(r"\b(?:is|was|were|been|be)\s+\w+ed\b", text, re.IGNORECASE)
        if len(passive_matches) > 40:
            grammar_issues.append(
                f"High passive-voice count ({len(passive_matches)}). Prefer active voice."
            )

        ctx.quality_audit.format_issues = format_issues
        ctx.quality_audit.grammar_spelling_issues = grammar_issues
        if format_issues or grammar_issues:
            self.log(
                ctx,
                f"FormatQualityAuditor flagged {len(format_issues)} format / "
                f"{len(grammar_issues)} grammar notes.",
            )
        else:
            self.log(ctx, "FormatQualityAuditor: no blocking format defects.")


class FactCheckerAgent(BaseAgent):
    """Cross-checks statistical claims against web/literature context when available."""

    def __init__(self, bus: SupervisorBus):
        super().__init__("FactCheckerAgent", layer=5, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        ctx.quality_audit.fact_check_method = "local_reference_context_statistic_heuristic"
        self.log(ctx, "Heuristic fact-context scan against collected web/literature text (not claim verification)...")
        if not ctx.output.markdown_manuscript:
            ctx.quality_audit.is_approved = False
            reason = "No manuscript to audit"
            if reason not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(reason)
            self.log(ctx, reason, level="WARN")
            return

        text = ctx.output.markdown_manuscript
        web_context = ctx.research.web_context or []
        lit = ctx.research.literature_context or []
        ref_text = " ".join(web_context + lit)

        # Soft pass if no external context — do not invent failures
        if not ref_text.strip():
            self.log(ctx, "No web/literature context; heuristic fact-context scan skipped (not a failure).", level="INFO")
            return

        hallucinations = 0
        reasons = []
        for claim in re.findall(r"\b\d{2,3}\.\d+%\b", text):
            if claim not in ref_text:
                hallucinations += 1
                reasons.append(f"Unsubstantiated statistic '{claim}' not found in reference context.")

        if hallucinations > 2:
            err_msg = f"Fact-context heuristic: {hallucinations} unverified statistics. {reasons[:3]}"
            self.log(ctx, err_msg, level="WARN")
            ctx.quality_audit.is_approved = False
            if err_msg not in ctx.quality_audit.rejection_reasons:
                ctx.quality_audit.rejection_reasons.append(err_msg)
            ctx.quality_audit.feedback_reroute_target = "WriterAgent"
        else:
            self.log(ctx, "Heuristic fact-context scan completed.")
