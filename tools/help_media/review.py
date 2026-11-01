"""Explicit editorial coverage; unreviewed clips must not be published."""

from review_family import VIDEO_REVIEW as FAMILY_REVIEW
from review_staff import VIDEO_REVIEW as STAFF_REVIEW


def apply_reviews(items, definitions):
    reviewed = {**FAMILY_REVIEW, **STAFF_REVIEW}
    if set(FAMILY_REVIEW) & set(STAFF_REVIEW):
        raise ValueError("Family/staff video reviews overlap")
    expected = {item["question"] for item in items if item.get("video")}
    if set(reviewed) != expected:
        raise ValueError(
            f"Video review coverage mismatch: missing {sorted(expected - set(reviewed))}; "
            f"extra {sorted(set(reviewed) - expected)}"
        )
    result = {}
    for question in expected:
        review = reviewed[question]
        if not review.get("review_note", "").strip():
            raise ValueError("Missing editorial rationale: " + question)
        steps = review.get("video_steps", [])
        if not 1 <= len(steps) <= 10:
            raise ValueError("A focused guide requires 1-10 steps: " + question)
        for step in steps:
            if not step.get("text", "").strip() or len(step["text"]) > 360:
                raise ValueError("Empty/overlong video caption: " + question)
            if not step.get("shot", "").count("@") == 1:
                raise ValueError("Missing precise video target: " + question)
            if step["shot"].startswith("account@"):
                raise ValueError("Fictitious MAX role picker is forbidden: " + question)
            if step.get("action", "observe") not in {"click", "observe"}:
                raise ValueError("Unknown instructional action: " + question)
        for previous, current in zip(steps, steps[1:], strict=False):
            if previous["shot"] == current["shot"] and previous["text"] == current["text"]:
                raise ValueError("Repeated video step: " + question)
        result[question] = {**definitions.get(question, {}), **review}
    return result
