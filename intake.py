"""
Rule-based structured intake extraction (no LLM).

Merges new utterances into existing session intake: new values fill empty
fields; non-empty existing scalars are preserved. Lists are unioned.
"""

from __future__ import annotations

import re
from typing import Any


_NAME_STOP = frozenset(
    {
        "here",
        "not",
        "fine",
        "good",
        "sick",
        "able",
        "having",
        "still",
        "very",
        "okay",
        "ok",
        "sorry",
        "worried",
        "experiencing",
        "feeling",
        "doing",
        "seeing",
        "trying",
    }
)

_WORD_NUM = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _norm_str(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(str(s).split()).strip()


def _uniq_ci(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        t = _norm_str(x)
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _merge_scalar(old: Any, new: Any) -> Any:
    if old not in (None, "", []):
        return old
    return new if new not in (None, "", []) else old


def _merge_list(old: list[str] | None, new: list[str] | None) -> list[str]:
    return _uniq_ci(list(old or []) + list(new or []))


_SEVERITY_RANK_SWELL: dict[str | None, int] = {
    None: 0,
    "none": 1,
    "mild": 2,
    "moderate": 3,
    "severe": 4,
}
_SEVERITY_RANK_BRUISE: dict[str | None, int] = {
    None: 0,
    "none": 1,
    "mild": 2,
    "moderate": 3,
    "significant": 4,
}
_RISK_RANK = {"unknown": 0, "self_care": 1, "routine": 1, "urgent": 2, "emergency": 3}


def _walking_status_label(intake: dict[str, Any]) -> str | None:
    c = intake.get("can_bear_weight")
    w = intake.get("walking_painful")
    if c is True and w is True:
        return "can walk but painful"
    if c is False:
        return "cannot bear weight / unable to walk"
    if c is True and w is not True:
        return "able to walk with tolerable pain"
    return None


def _merge_severity(
    key: str, old: str | None, new: str | None, rank_map: dict[str | None, int]
) -> str | None:
    if new is None:
        return old
    if old is None:
        return new
    return new if rank_map.get(new, 0) > rank_map.get(old, 0) else old


def _parse_name(text: str) -> str | None:
    t = text.strip()
    m = re.search(r"\bmy\s+name\s+is\s+([A-Za-z][A-Za-z'\-]{0,39})\b", t, re.I)
    if m:
        return m.group(1).strip("'\"").title()
    m = re.search(r"\b(?:call\s+me|i\s*'?m\s+called)\s+([A-Za-z][A-Za-z'\-]{0,39})\b", t, re.I)
    if m:
        return m.group(1).strip("'\"").title()
    m = re.search(r"\bi\s*'?m\s+([A-Za-z][a-z]{1,29})\b", t, re.I)
    if m:
        w = m.group(1)
        if w.lower() in _NAME_STOP:
            return None
        return w[0].upper() + w[1:]
    m = re.search(r"\bi\s+am\s+([A-Za-z][a-z]{1,29})\b", t, re.I)
    if m:
        w = m.group(1)
        if w.lower() in _NAME_STOP:
            return None
        return w[0].upper() + w[1:]
    return None


def _parse_age(text: str) -> str | None:
    m = re.search(r"\b(\d{1,3})\s*years?\s*old\b", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\bage\s*[:is]?\s*(\d{1,3})\b", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\bi\s*'?m\s+(\d{1,3})(?:\s*years?\s*old)?\b", text, re.I)
    if m:
        return m.group(1)
    return None


def _parse_duration(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bsince\s+yesterday\b", low):
        return "1 day"
    if re.search(r"\bsince\s+last\s+week\b", low):
        return "1 week"
    m = re.search(
        r"\b(?:for|about|over)\s+((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}))\s+"
        r"(day|days|week|weeks|month|months|hour|hours)\b",
        low,
    )
    if m:
        q = m.group(1)
        unit = m.group(2)
        n = int(q) if q.isdigit() else _WORD_NUM.get(q, 1)
        return f"{n} {unit}"
    m = re.search(
        r"\b(two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+(day|days|week|weeks)\s+ago\b",
        low,
    )
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _WORD_NUM.get(m.group(1), 1)
        return f"{n} {m.group(2)}"
    return None


def _parse_side(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bleft\b", low) and not re.search(r"\bleft\s+over\b", low):
        return "left"
    if re.search(r"\bright\b", low):
        return "right"
    if re.search(r"\bbilateral\b|\bboth\s+(?:sides|legs|arms)\b", low):
        return "bilateral"
    return None


def _parse_body_part(text: str) -> str | None:
    low = text.lower()
    pairs = [
        ("ankle", "ankle"),
        ("wrist", "wrist"),
        ("knee", "knee"),
        ("elbow", "elbow"),
        ("shoulder", "shoulder"),
        ("neck", "neck"),
        ("back", "back"),
        ("chest", "chest"),
        ("abdomen", "abdomen"),
        ("stomach", "abdomen"),
        ("belly", "abdomen"),
        ("throat", "throat"),
        ("head", "head"),
        ("skin", "skin"),
    ]
    for pat, label in pairs:
        if pat in low:
            return label
    return None


def _parse_mechanism(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\btwist(?:ed|ing)?\b", low):
        return "twisting injury"
    if re.search(r"\bfell|fall\b", low):
        return "fall"
    if re.search(r"\bhit|struck|banged\b", low):
        return "direct blow"
    return None


def _parse_severity(text: str) -> str | None:
    low = text.lower()
    m = re.search(r"\b(?:pain|severity)\s*(?:of|:)?\s*(\d{1,2})\s*/\s*10\b", low)
    if m:
        return f"{m.group(1)}/10"
    m = re.search(r"\b(\d{1,2})\s*/\s*10\b", low)
    if m and "pain" in low:
        return f"{m.group(1)}/10"
    if re.search(r"\bsevere\b", low):
        return "severe"
    if re.search(r"\bmild\b", low):
        return "mild"
    return None


def _parse_allergies_line(text: str) -> list[str]:
    out: list[str] = []
    m = re.search(r"\ballergic\s+to\s+([A-Za-z0-9][A-Za-z0-9\s\-]{1,48})\b", text, re.I)
    if m:
        out.append(_norm_str(m.group(1)).rstrip(".,;"))
    return out


def _parse_chronic(text: str) -> list[str]:
    low = text.lower()
    out: list[str] = []
    if "diabetes" in low or "diabetic" in low:
        out.append("diabetes")
    if "hypertension" in low or "high blood pressure" in low:
        out.append("hypertension")
    if "asthma" in low:
        out.append("asthma")
    return out


def _parse_meds(text: str) -> list[str]:
    # Minimal placeholder — avoid dosing
    if re.search(r"\btaking\s+(\w+(?:\s+\w+){0,3})\b", text, re.I):
        m = re.search(r"\btaking\s+([A-Za-z][A-Za-z\s\-]{2,40})\b", text, re.I)
        if m and "birth" not in m.group(1).lower():
            return [_norm_str(m.group(1)).rstrip(".,;")[:60]]
    return []


def _detect_red_flags(text: str) -> list[str]:
    low = text.lower()
    flags: list[str] = []
    if "chest pain" in low:
        flags.append("chest pain")
    if re.search(r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing|can'?t\s+breathe)\b", low):
        flags.append("breathing difficulty")
    if "chest pain" in low and re.search(
        r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing)\b", low
    ):
        flags.append("possible cardiac or pulmonary emergency pattern")
    if re.search(r"\b(slurred\s+speech|face\s+drooping|one[- ]sided\s+weakness)\b", low):
        flags.append("possible stroke warning signs")
    if "worst headache" in low or "thunderclap" in low:
        flags.append("sudden severe headache")
    if re.search(r"\b(stiff\s+neck|fever)\b", low) and "confusion" in low:
        flags.append("fever with confusion or neck stiffness")
    return _uniq_ci(flags)


def _detect_symptoms(text: str) -> list[str]:
    low = text.lower()
    found: list[str] = []
    rules: list[tuple[str, str]] = [
        ("fever", r"\bfever\b|\bfebrile\b"),
        ("cough", r"\bcough(?:ing)?\b"),
        ("chest pain", r"\bchest\s+pain\b"),
        ("shortness of breath", r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing)\b"),
        ("headache", r"\bheadache\b|\bmigraine\b"),
        ("rash", r"\brush\b|\bhives\b"),
        ("nausea", r"\bnausea\b|\bnauseous\b"),
        ("vomiting", r"\bvomit(?:ing)?\b|\bthrew\s+up\b"),
        ("diarrhea", r"\bdiarrhea\b|\bloose\s+stool\b"),
        ("dizziness", r"\bdizz(?:y|iness)\b|\blightheaded\b"),
        ("sore throat", r"\bsore\s+throat\b"),
        ("abdominal pain", r"\b(stomach|abdominal|belly)\s+pain\b"),
        ("anxiety", r"\banxious\b|\banxiety\b"),
        ("insomnia", r"\b(can'?t|cannot)\s+sleep\b|\binsomnia\b|\btrouble\s+sleeping\b"),
        (
            "ankle injury",
            r"\bankle\b.*\b(twist|sprain|injur)|\b(twist|sprain|twisted).*\bankle\b|\bankle\b.*\btwisted\b",
        ),
    ]
    for label, pat in rules:
        if re.search(pat, low):
            found.append(label)
    if "peanut" in low and "rash" in low:
        if "possible allergic reaction" not in [x.lower() for x in found]:
            found.append("possible allergic reaction")
    return _uniq_ci(found)


def _chief_complaint_from(text: str, body: str | None, side: str | None, symptoms: list[str]) -> str | None:
    low = text.lower()
    if "rash" in low and "peanut" in low:
        return "rash after eating peanuts"
    if body == "ankle" and ("twist" in low or "sprain" in low or "ankle" in low):
        loc = f"{(side + ' ') if side else ''}{body} injury".strip()
        return loc
    if symptoms:
        return ", ".join(symptoms[:4])
    return None


def _likely_department(symptoms: list[str], body: str | None, text: str) -> str | None:
    low = text.lower()
    sl = " ".join(symptoms).lower()
    if body == "ankle" or "ankle injury" in sl:
        return "Orthopedics"
    if "chest pain" in sl or "shortness of breath" in sl:
        return "Emergency / Cardiology"
    if "rash" in sl or "hives" in low or "peanut" in low:
        return "Dermatology / Allergy"
    if "anxiety" in sl or "insomnia" in sl:
        return "Mental Health / Primary Care"
    if "fever" in sl or "cough" in sl:
        return "Internal Medicine"
    if "headache" in sl:
        return "Neurology / Primary Care"
    return "Primary Care"


def _risk_level_hint(text: str, red: list[str], symptoms: list[str]) -> str:
    low = text.lower()
    if red and ("possible cardiac or pulmonary emergency pattern" in red or (
        "chest pain" in low and re.search(r"\b(shortness\s+of\s+breath|trouble\s+breathing)\b", low)
    )):
        return "emergency"
    if red and any("stroke" in r for r in red):
        return "emergency"
    if "chest pain" in low and "shortness of breath" in " ".join(symptoms).lower():
        return "emergency"
    if "severe" in low and ("bleeding" in low or "can't breathe" in low or "cannot breathe" in low):
        return "emergency"
    if "peanut" in low and "rash" in low and re.search(r"\b(swelling|wheeze|throat|can'?t\s+breathe)\b", low):
        return "emergency"
    if "ankle injury" in " ".join(symptoms).lower() or ("ankle" in low and "twist" in low):
        return "routine"
    return "routine"


def _is_ankle_intake(merged: dict[str, Any]) -> bool:
    if merged.get("body_part") == "ankle":
        return True
    sl = " ".join(merged.get("symptoms") or []).lower()
    return "ankle injury" in sl or "ankle" in sl


def _parse_multiturn_clinical(message: str, existing: dict[str, Any]) -> dict[str, Any]:
    """
    Extract follow-up fields (EN/CN) for musculoskeletal and progression reporting.
    """
    text = _norm_str(message)
    if not text:
        return {}
    low = text.lower()
    tcn = text  # keep original for CJK

    out: dict[str, Any] = {}
    red_add: list[str] = []

    # —— Chinese: severity / course ——
    if re.search(
        r"肿胀(很|得)?严重|肿得(很)?严重|严重肿胀|脚踝.*肿胀(很|得)?(严重|厉害)", tcn
    ) or re.search(
        r"肿(得)?很厉害", tcn
    ):
        out["swelling"] = "severe"
    if re.search(r"淤青(很)?多|大面积淤青|很多淤青|大片淤青", tcn) or re.search(
        r"青紫(很)?多", tcn
    ):
        out["bruising"] = "significant"
    if re.search(
        r"比(受伤|当时|开始)(时)?(更疼|更痛)|更疼了|越来越疼|越来越痛|比.*更疼|恶化",
        tcn,
    ) or re.search(
        r"getting worse|worse than before|more painful than (before|when)",
        low,
    ):
        out["worsening_pain"] = True
    if re.search(r"能走但疼|能走路但(疼|痛)|可以走几步(但|，)(是)?(很)?疼|走几步(很)?疼", tcn) or re.search(
        r"能走.*(疼|痛)", tcn
    ):
        out["can_bear_weight"] = True
        out["walking_painful"] = True
    if re.search(r"不能走|走不了|无法行走|不能承重|不能著力", tcn) or re.search(
        r"走不动", tcn
    ):
        out["can_bear_weight"] = False
        if "unable_to_bear_weight" not in (existing.get("red_flags") or []):
            red_add.append("unable_to_bear_weight")

    # —— English: weight-bearing, walking, worsening, bruise/swelling ——
    if re.search(
        r"\b(yeah|yes),?\s*but\s+it['']?s\s+painful\b|\bbut\s+it['']?s\s+painful\b",
        low,
    ) or re.search(
        r"\bcan (walk|walk on it|put weight) but (it['']?s )?(painful|hurts?)\b",
        low,
    ) or re.search(r"\bwalk(ing)? (is )?painful\b|\bpainful to walk\b", low):
        if "can't walk" not in low and "cannot walk" not in low:
            out["can_bear_weight"] = True
        out["walking_painful"] = True
    if re.search(
        r"\bcan'?t (walk|stand|bear weight|put weight)\b|"
        r"\bcannot (walk|stand|bear weight|put weight)\b|"
        r"\bunable to (walk|stand|bear weight)\b|"
        r"don'?t (think )?i can (walk|put weight)",
        low,
    ):
        out["can_bear_weight"] = False
        if "unable_to_bear_weight" not in (existing.get("red_flags") or []):
            red_add.append("unable_to_bear_weight")

    if re.search(
        r"\b(severe|very|a lot of) (ankle )?swelling|swelling (is )?(severe|very bad)\b|"
        r"\bvery swollen\b|\bso swollen\b|badly swollen",
        low,
    ) or re.search(
        r"肿胀(的)?(很)?(严重|厉害)|肿(得)?(很)?(严重|厉害)|严重肿胀|肿胀(很)?重", tcn
    ):
        out["swelling"] = "severe"
    if re.search(
        r"\b(a lot of|a lot|significant|heavy|dark) (of )?bruis(e|ing)\b|"
        r"\bbruise(s)? around my ankle\b|"
        r"\bsee a lot of bruise\b|"
        r"\bconsiderable bruising\b",
        low,
    ) or re.search(
        r"青紫(很)?(多|重)|很(大)?片(淤)?青|大面积淤青|明显淤青|淤青明显", tcn
    ):
        out["bruising"] = "significant"
    if re.search(
        r"\b(more painful than|worse than (when|before)|getting worse|worsening|"
        r"pain is worse)\b",
        low,
    ) or re.search(
        r"更疼|更痛|比.*疼|加重|恶化|越来越(疼|痛)", tcn
    ):
        out["worsening_pain"] = True

    # Deformity / neuro (ankle) — English + simple CN
    if re.search(
        r"\b(deform|bent the wrong|bones out of place|snapped)\b|"
        r"畸形|明显变形|肿成奇怪的形状|骨头凸出来",
        low + tcn,
    ):
        red_add.append("possible_deformity")
    if re.search(
        r"\b(numb(ness)?|cold toes?|toes? (are )?numb|blue toes?)\b|"
        r"脚(趾)?(发)?麻|脚(趾)?(冰)?冷|脚趾发紫",
        low + tcn,
    ):
        red_add.append("numb_or_cold_toes")
    if re.search(
        r"\brapidly worsening|pain suddenly much worse|can'?t tolerate the pain\b", low
    ):
        red_add.append("rapid_worsening_severe_pain")

    dash = r"[\-–\u2013\u2014]"
    m_p = re.search(
        r"(?:roughly|how strong|pain|from)\s+[^?\n]{0,40}?1\s*" + dash + r"\s*10\s*\??\s*[:：]?\s*(\d{1,2})",
        text,
        re.I,
    ) or re.search(
        r"1\s*" + dash + r"\s*10\s*\??\s*(\d{1,2})\s*\.?(?:\s*$|\Z)",
        text,
        re.I,
    ) or re.search(
        r"10\s*\?\s*(\d{1,2})\s*\.?(?:\s*$|\Z)",
        text,
        re.I,
    ) or re.search(
        r"(?:1\s*" + dash + r"\s*10|评分)\s*[^\d]{0,6}(\d{1,2})",
        tcn,
    )
    if m_p:
        n = int(m_p.group(1))
        if 0 <= n <= 10:
            out["pain_score"] = n
    m2 = re.search(r"\bpain(?:\s*level)?\s*(?:is|[:=])?\s*(\d{1,2})(?:\s*/\s*10)?\b", low) or re.search(
        r"疼痛(?:评分|是)?[：:\s]*(\d{1,2})",
        tcn,
    )
    if m2:
        n = int(m2.group(1))
        if 0 <= n <= 10:
            out["pain_score"] = n
    _cn_num = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    m3 = re.search(r"疼痛[：:\s]*(\d{1,2})\s*分?", tcn)
    if m3:
        n = int(m3.group(1))
        if 0 <= n <= 10:
            out["pain_score"] = n
    m4 = re.search(r"([一二三四五六七八九十])分", tcn)
    if m4 and m4.group(1) in _cn_num:
        out["pain_score"] = _cn_num[m4.group(1)]

    st = text.strip()
    if len(st) <= 4 and re.fullmatch(r"[\d\s/\.]+", st) and _is_ankle_intake(existing):
        m5 = re.search(r"(\d{1,2})", st)
        if m5:
            n = int(m5.group(1))
            if 0 <= n <= 10:
                out["pain_score"] = n

    af: list[str] = []
    if re.search(
        r"(?:take a few steps|walk on it|can you (walk| stand))",
        low,
    ) and (
        re.search(r"yeah|yes|i can|but|painful|hurts|walk a few", low)
        or re.search(
            r"能走|可以走|能站|走几步|承重", tcn
        )
    ):
        af.append("walking")
    if re.search(
        r"swell|bruis|青紫|淤青|肿胀", low + tcn, re.I
    ) and (
        re.search(
            r"a lot|severe|very|see|很多|明显|严重|大量", low + tcn, re.I
        )
    ):
        af.append("swelling_or_bruising")
    if out.get("pain_score") is not None or re.search(
        r"1[-–\s]10|/10|pain (level|score|is)|\bpain\b.*\d", low
    ) or re.search(
        r"疼.*\d|痛.*\d|评分", tcn
    ):
        if out.get("pain_score") is not None:
            af.append("pain_score")

    if af:
        out["answered_followups"] = _uniq_ci(af)

    if red_add:
        out["red_flags"] = _uniq_ci(red_add)
    return out


def _ankle_risk_from_state(merged: dict[str, Any]) -> str | None:
    if not _is_ankle_intake(merged):
        return None
    rf = " ".join(merged.get("red_flags") or []).lower()
    rflags = [str(x).lower() for x in (merged.get("red_flags") or [])]
    dlm = (merged.get("duration") or "").lower()
    days_2_plus = "2" in dlm and "day" in dlm
    s = (merged.get("swelling") or "").lower()
    b = (merged.get("bruising") or "").lower()
    ps = merged.get("pain_score")
    wp = merged.get("worsening_pain")
    cando = merged.get("can_bear_weight")
    wpain = merged.get("walking_painful")

    if cando is False or "unable_to_bear_weight" in rflags:
        return "emergency"
    if "possible_deformity" in rflags or "deform" in rf:
        return "emergency"
    if "numb_or_cold_toes" in rflags or "rapid_worsening_severe_pain" in rflags:
        return "emergency"

    urgent = False
    if s == "severe" or b == "significant":
        urgent = True
    if wp is True:
        urgent = True
    if wpain is True and ps is not None and int(ps) >= 6:
        urgent = True
    if days_2_plus and wp is True:
        urgent = True
    if _SEVERITY_RANK_SWELL.get(s, 0) >= 3 and (wp is True or wpain is True):
        urgent = True

    if urgent:
        return "urgent"

    if cando is True and s in (None, "none", "mild") and b in (None, "none", "mild") and not wp and (ps is None or int(ps) < 5):
        return "routine"
    if merged.get("mechanism") == "twisting injury" and merged.get("duration"):
        return "routine"
    return "routine"


def _merge_risk(a: str | None, b: str | None) -> str:
    ra = (a or "routine").lower()
    rb = (b or "routine").lower()
    if _RISK_RANK.get(rb, 0) > _RISK_RANK.get(ra, 0):
        return rb
    return ra


def _apply_clinical_overlays(merged: dict[str, Any], clin: dict[str, Any]) -> dict[str, Any]:
    if not clin:
        return merged
    for k in ("can_bear_weight", "walking_painful"):
        if k in clin and clin[k] is not None:
            merged[k] = bool(clin[k])
    if clin.get("worsening_pain") is True or merged.get("worsening_pain") is True:
        merged["worsening_pain"] = True
    for fld, rmap in (
        ("swelling", _SEVERITY_RANK_SWELL),
        ("bruising", _SEVERITY_RANK_BRUISE),
    ):
        if fld in clin and clin[fld] is not None:
            merged[fld] = _merge_severity(
                fld, merged.get(fld), str(clin[fld]), rmap
            )
    if clin.get("pain_score") is not None:
        merged["pain_score"] = int(clin["pain_score"])
    if clin.get("red_flags"):
        merged["red_flags"] = _merge_list(merged.get("red_flags"), clin["red_flags"])
    if clin.get("answered_followups"):
        merged["answered_followups"] = _merge_list(
            merged.get("answered_followups", []), clin["answered_followups"]
        )
    return merged


def _confidence(merged: dict[str, Any]) -> float:
    keys = [
        "name",
        "age",
        "chief_complaint",
        "symptoms",
        "body_part",
        "duration",
        "side_or_location",
    ]
    score = 0.0
    for k in keys:
        v = merged.get(k)
        if v is None or v == "" or v == []:
            continue
        score += 1.0 / len(keys)
    return round(min(1.0, score + 0.15), 2)


def _empty_intake() -> dict[str, Any]:
    return {
        "name": None,
        "age": None,
        "sex_or_gender": None,
        "chief_complaint": None,
        "symptoms": [],
        "body_part": None,
        "side_or_location": None,
        "duration": None,
        "mechanism": None,
        "severity": None,
        "allergies": [],
        "chronic_conditions": [],
        "medications": [],
        "red_flags": [],
        "likely_department": None,
        "risk_level_hint": "routine",
        "food_trigger": None,
        "can_bear_weight": None,
        "walking_painful": None,
        "swelling": None,
        "bruising": None,
        "pain_score": None,
        "worsening_pain": None,
        "answered_followups": [],
        "confidence": 0.0,
    }


def _parse_message_only(message: str) -> dict[str, Any]:
    text = _norm_str(message)
    low = text.lower()
    symptoms = _detect_symptoms(text)
    body = _parse_body_part(text)
    side = _parse_side(text)
    duration = _parse_duration(text)
    mechanism = _parse_mechanism(text)
    red = _detect_red_flags(text)
    food_trigger = None
    if re.search(r"\b(?:after\s+eating|from)\s+peanuts\b", low) or ("peanut" in low and "rash" in low):
        food_trigger = "peanuts"
    chief = _chief_complaint_from(text, body, side, symptoms)
    dept = _likely_department(symptoms, body, text)
    risk = _risk_level_hint(text, red, symptoms)
    if food_trigger and "possible allergic reaction" not in [s.lower() for s in symptoms]:
        symptoms = _uniq_ci(symptoms + ["possible allergic reaction"])

    return {
        "name": _parse_name(text),
        "age": _parse_age(text),
        "sex_or_gender": None,
        "chief_complaint": chief,
        "symptoms": symptoms,
        "body_part": body,
        "side_or_location": side,
        "duration": duration,
        "mechanism": mechanism,
        "severity": _parse_severity(text),
        "allergies": _parse_allergies_line(text),
        "chronic_conditions": _parse_chronic(text),
        "medications": _parse_meds(text),
        "red_flags": red,
        "likely_department": dept,
        "risk_level_hint": risk,
        "food_trigger": food_trigger,
    }


def _merge_intake(existing: dict[str, Any] | None, parsed: dict[str, Any]) -> dict[str, Any]:
    base = _empty_intake()
    if existing:
        for k, v in existing.items():
            if k in base:
                base[k] = v
    # scalars
    for key in (
        "name",
        "age",
        "sex_or_gender",
        "chief_complaint",
        "body_part",
        "side_or_location",
        "duration",
        "mechanism",
        "severity",
        "likely_department",
        "risk_level_hint",
        "food_trigger",
        "can_bear_weight",
        "walking_painful",
    ):
        base[key] = _merge_scalar(base.get(key), parsed.get(key))
    # lists
    base["symptoms"] = _merge_list(base.get("symptoms"), parsed.get("symptoms"))
    base["allergies"] = _merge_list(base.get("allergies"), parsed.get("allergies"))
    base["chronic_conditions"] = _merge_list(base.get("chronic_conditions"), parsed.get("chronic_conditions"))
    base["medications"] = _merge_list(base.get("medications"), parsed.get("medications"))
    base["red_flags"] = _merge_list(base.get("red_flags"), parsed.get("red_flags"))
    pr = (parsed.get("risk_level_hint") or "routine").lower()
    br = (base.get("risk_level_hint") or "routine").lower()
    rank = {"routine": 1, "self_care": 1, "urgent": 2, "emergency": 3, "unknown": 0}
    if rank.get(pr, 1) > rank.get(br, 1):
        base["risk_level_hint"] = parsed.get("risk_level_hint")
    elif not base.get("risk_level_hint"):
        base["risk_level_hint"] = parsed.get("risk_level_hint") or "routine"
    base["confidence"] = _confidence(base)
    return base


def extract_patient_intake(message: str, existing_state: dict | None = None) -> dict[str, Any]:
    """
    Extract and merge structured intake from natural language.

    Returns a stable dict (unknowns as None or []).
    """
    parsed = _parse_message_only(message)
    merged = _merge_intake(existing_state, parsed)
    clin = _parse_multiturn_clinical(message, merged)
    merged = _apply_clinical_overlays(merged, clin)
    ar = _ankle_risk_from_state(merged)
    if ar:
        merged["risk_level_hint"] = _merge_risk(merged.get("risk_level_hint"), ar)
    if _is_ankle_intake(merged) and (merged.get("risk_level_hint") or "").lower() == "urgent":
        merged["likely_department"] = "Orthopedics / Urgent Care"
    merged["confidence"] = _confidence(merged)
    return merged


def build_patient_summary_for_response(
    intake: dict[str, Any],
    *,
    guardrail_triggered: bool,
    guardrail_severity: str | None,
    triage_level: str | None,
) -> dict[str, Any]:
    """Shape for /chat `patient_summary` (UI + clients)."""
    risk = "unknown"
    if guardrail_triggered and guardrail_severity == "emergency":
        risk = "emergency"
    elif guardrail_triggered and guardrail_severity == "urgent":
        risk = "urgent"
    elif (intake.get("risk_level_hint") or "").lower() == "emergency":
        risk = "emergency"
    elif (intake.get("risk_level_hint") or "").lower() == "urgent":
        risk = "urgent"
    elif triage_level == "emergency":
        risk = "emergency"
    elif triage_level == "urgent":
        risk = "urgent"
    elif triage_level in {"routine", "self_care"}:
        risk = str(triage_level)
    elif intake.get("risk_level_hint"):
        risk = str(intake.get("risk_level_hint"))

    loc_parts = [p for p in (intake.get("side_or_location"), intake.get("body_part")) if p]
    body_loc = " ".join(loc_parts) if loc_parts else None

    pain_display = None
    if intake.get("pain_score") is not None:
        pain_display = f"{int(intake['pain_score'])}/10"

    return {
        "name": intake.get("name"),
        "age": intake.get("age"),
        "chief_complaint": intake.get("chief_complaint"),
        "symptoms": intake.get("symptoms") or [],
        "duration": intake.get("duration"),
        "body_part": intake.get("body_part"),
        "side_or_location": intake.get("side_or_location"),
        "mechanism": intake.get("mechanism"),
        "allergies": intake.get("allergies") or [],
        "chronic_conditions": intake.get("chronic_conditions") or [],
        "likely_department": intake.get("likely_department"),
        "risk_level": risk,
        "body_location_label": body_loc,
        "swelling": intake.get("swelling"),
        "bruising": intake.get("bruising"),
        "pain_score": intake.get("pain_score"),
        "pain_display": pain_display,
        "walking_status": _walking_status_label(intake),
        "worsening_pain": intake.get("worsening_pain"),
    }
