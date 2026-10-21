"""AI services behind protocols — stub-first, like SimulatedAnchor.

StubReviewer is deterministic and offline: it scores plausibility from
reasoning/proof signals only. A real LLM reviewer drops in behind the
same `review()` shape (AI_MODE=llm in a future deployment).
"""
from __future__ import annotations

import re
from typing import Protocol


class Reviewer(Protocol):
    def review(self, skill: dict, reasoning: str, proof_links: list[str],
               method: str, test_score: int | None) -> dict: ...


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 3}


class StubReviewer:
    model = "stub-plausibility-v1"

    def review(self, skill: dict, reasoning: str, proof_links: list[str],
               method: str, test_score: int | None) -> dict:
        reasoning = reasoning or ""
        overlap = _words(reasoning) & _words(
            f"{skill.get('skillName','')} {skill.get('skillDescription','')} {skill.get('skillCategory','')}")
        score = 20
        score += min(30, len(reasoning.strip()) // 4)          # substantive reasoning
        score += min(20, len(overlap) * 5)                     # mentions the skill domain
        score += 15 if proof_links else 0                      # evidence attached
        score += 15 if method == "TEST" else 0
        if test_score is not None:
            score = max(score, test_score)
        score = max(0, min(100, score))
        bits = []
        bits.append("detailed reasoning" if len(reasoning.strip()) >= 40 else "brief reasoning")
        bits.append(f"{len(overlap)} skill-domain terms matched")
        bits.append("proof link provided" if proof_links else "no proof link")
        if method == "TEST":
            bits.append(f"test score {test_score}%")
        verdict = "Plausible" if score >= 60 else "Needs closer human review" if score >= 35 else "Weakly supported"
        return {"score": score, "model": self.model,
                "summary": f"{verdict}: {'; '.join(bits)}."}


class StubExplainer:
    model = "stub-explainer-v1"

    def explain(self, skill: dict, question: str = "") -> dict:
        name = skill.get("skillName", "This skill")
        desc = skill.get("skillDescription", "")
        cat = skill.get("skillCategory", "")
        answer = (f"{name} ({cat}) at BTU covers: {desc} " if desc else f"{name} ({cat}). ")
        answer += ("In plain language, the holder has demonstrated this competency in a BTU-recognised "
                   "learning experience, and BTU has verified and blockchain-anchored that record. ")
        if question:
            answer += (f"Regarding your question ({question.strip()}): judge relevance by matching the "
                       f"description above against the tasks in the role — the skill name and category "
                       f"({cat}) indicate the depth and format of the assessed work.")
        return {"answer": answer, "model": self.model}


class StubSkillExtractor:
    model = "stub-extractor-v1"

    def extract(self, text: str, catalogue: list[dict]) -> list[dict]:
        """Keyword extraction: a catalogue skill is 'required' when its name
        or distinctive description terms appear in the job text."""
        hay = _words(text) | {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())}
        found = []
        for item in catalogue:
            name_words = _words(item.get("skillName", ""))
            desc_words = _words(item.get("skillDescription", ""))
            name_hit = item.get("skillName", "").lower() in (text or "").lower()
            overlap = len(name_words & hay) + len((desc_words & hay))
            if name_hit or overlap >= 2:
                found.append(item)
        return found


def make_reviewer(mode: str = "stub") -> StubReviewer:
    return StubReviewer()  # future: AI_MODE=llm returns a real LLM reviewer


def make_explainer(mode: str = "stub") -> StubExplainer:
    return StubExplainer()


def make_extractor(mode: str = "stub") -> StubSkillExtractor:
    return StubSkillExtractor()
