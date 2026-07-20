#!/usr/bin/env python3
"""
מייצר data.js עבור סימולטור 4.65 מתוך קבצי 06_Knowledge_Vault.
אסור לערוך data.js ידנית — כל שינוי בתנאים/סכומים/רשימות נעשה במאגר,
ואז מריצים סקריפט זה מחדש.

הרצה: python sync_data.py  (מתוך תיקיית הסימולטור)
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
VAULT = HERE.parents[4] / "06_Knowledge_Vault"

TRACK_MD = VAULT / "מיצוי-משאבים" / "מסלולי-מענקים" / "משרד-הכלכלה_4.65-האצה-עסקית-גבול-לבנון.md"
VILLAGES_MD = VAULT / "מיצוי-משאבים" / "החלטות-ממשלה" / "3841_יישובי-גבול-לבנון.md"
INDUSTRY_MD = VAULT / "נתונים נוספים" / "סיווג-ענפי-כלכלה-הלמס.md"
TECH_TIER_MD = VAULT / "נתונים נוספים" / "סיווג-עצמה-טכנולוגית-תעשייה.md"

INDUSTRY_ORDER_CODES = ["C", "G", "H", "I", "J", "M", "N", "S"]
S_ELIGIBLE_BRANCH_CODES = ["95", "96"]


def section(text, heading_prefix, next_prefix="## "):
    """מחזיר את תוכן הסעיף שמתחיל בשורת כותרת שמתחילה ב-heading_prefix, עד לכותרת הבאה."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = i + 1
            break
    if start is None:
        raise ValueError(f"heading not found: {heading_prefix}")
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith(next_prefix):
            end = i
            break
    return "\n".join(lines[start:end]).strip()


def parse_numbered_list(block):
    """מפצל בלוק לפי פריטים ממוספרים '1. ...' (כולל שורות המשך שנעטפו)."""
    items = []
    current = []
    for line in block.splitlines():
        if re.match(r"^\d+\.\s+", line):
            if current:
                items.append(" ".join(current).strip())
            current = [re.sub(r"^\d+\.\s+", "", line)]
        elif line.strip():
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    return items


def parse_table(block):
    """מפרש טבלת Markdown '| a | b |' ומחזיר רשימת שורות (כל שורה = רשימת עמודות)."""
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^:?-+:?$", c) for c in cells):
            continue  # שורת מפריד ---|---
        rows.append(cells)
    return rows


def parse_subsections(block):
    """מפצל בלוק לפי כותרות משנה '### ...' ומחזיר רשימת (heading, content_lines)."""
    sections = []
    current_heading = None
    current_lines = []
    for line in block.splitlines():
        if line.startswith("### "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading = line[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections.append((current_heading, current_lines))
    return sections


def parse_bullets(block):
    """מפצל בלוק לפי בולטים '- ...' (כולל שורות המשך שנעטפו). מתעלם מטקסט מקדים שאינו בולט."""
    items = []
    current = []
    for line in block.splitlines():
        if line.strip().startswith("- "):
            if current:
                items.append(" ".join(current).strip())
            current = [re.sub(r"^-\s+", "", line.strip())]
        elif line.strip() and current:
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    return items


def build_track_data():
    track_text = TRACK_MD.read_text(encoding="utf-8")
    villages_text = VILLAGES_MD.read_text(encoding="utf-8")
    industry_text = INDUSTRY_MD.read_text(encoding="utf-8")
    tech_tier_text = TECH_TIER_MD.read_text(encoding="utf-8")

    # תנאי סף (סעיף 4) — 6 פריטים לפי סדר המקור
    threshold_items = parse_numbered_list(section(track_text, "## תנאי סף להשתתפות"))
    (revenue_text, location_text, industry_text_condition,
     active_business_text, management_text, insolvency_text) = threshold_items[:6]

    # מדרגות מענק (סעיף 8) — דילוג על שורת הכותרת
    funding_rows = parse_table(section(track_text, "## שיעור ותקרת הסיוע"))[1:]
    funding_tiers = [{"revenueRange": r[0], "cap": r[1]} for r in funding_rows]

    # אמות מידה (סעיף 7) — כותרות משנה "קריטריון — משקל%" + הסבר/בולטים
    scoring_criteria = []
    for heading, lines in parse_subsections(section(track_text, "## דירוג בקשות")):
        m = re.match(r"^(.*?)\s*—\s*(\d+%)$", heading)
        criterion, weight = (m.group(1).strip(), m.group(2)) if m else (heading, "")
        intro_lines = []
        for line in lines:
            if line.strip().startswith("- "):
                break
            if line.strip():
                intro_lines.append(line.strip())
        entry = {"criterion": criterion, "weight": weight}
        intro = " ".join(intro_lines).strip()
        if intro:
            entry["intro"] = intro
        items = parse_bullets("\n".join(lines))
        if items:
            entry["items"] = items
        scoring_criteria.append(entry)

    # הוצאות מוכרות (סעיף 9) — כותרות משנה = קטגוריות, בולטים = פריטים
    eligible_expenses = [
        {"category": heading, "items": parse_bullets("\n".join(lines))}
        for heading, lines in parse_subsections(section(track_text, "## הוצאות מוכרות"))
    ]
    not_eligible_expenses = section(track_text, "## הוצאות שאינן מוכרות").strip()

    # יישובים
    village_rows = parse_table(section(villages_text, '## רשימת יישובים'))[1:]
    villages = [{"name": r[0], "authority": r[1]} for r in village_rows]

    # סיווג ענפי כלכלה — סינון לסדרים כשירים בלבד
    industry_orders = []
    industry_branches = {}
    for m in re.finditer(r"^## סדר (\w) — (.+)$", industry_text, re.MULTILINE):
        code, name = m.group(1), m.group(2).strip()
        if code not in INDUSTRY_ORDER_CODES:
            continue
        industry_orders.append({"code": code, "name": name})
        block = section(industry_text, m.group(0), next_prefix="## ")
        rows = parse_table(block)[1:]
        industry_branches[code] = [{"code": r[0], "name": r[1]} for r in rows]

    # עצמה טכנולוגית (סדר C בלבד)
    tier_names = ["טכנולוגיה עילית", "טכנולוגיה מעורבת עילית",
                  "טכנולוגיה מעורבת מסורתית", "טכנולוגיה מסורתית"]
    industry_tech_tiers = []
    for tier in tier_names:
        block = section(tech_tier_text, f"## {tier}", next_prefix="## ")
        rows = parse_table(block)[1:]
        for r in rows:
            industry_tech_tiers.append({
                "code": r[0],
                "name": r[1],
                "tier": tier.replace("טכנולוגיה ", ""),
                "eligible": tier != "טכנולוגיה עילית",
            })

    return {
        "meta": {
            "name": 'סימולטור תנאי סף ואמות מידה — הוראת מנכ"ל 4.65',
            "sourceFiles": [
                str(TRACK_MD.relative_to(VAULT.parent)),
                str(VILLAGES_MD.relative_to(VAULT.parent)),
                str(INDUSTRY_MD.relative_to(VAULT.parent)),
                str(TECH_TIER_MD.relative_to(VAULT.parent)),
            ],
        },
        "revenueCapILS": 100_000_000,
        "conditionText": {
            "revenue": revenue_text,
            "location": location_text,
            "industry": industry_text_condition,
            "activeBusiness": active_business_text,
            "management": management_text,
            "insolvency": insolvency_text,
        },
        "villages": villages,
        "fundingTiers": funding_tiers,
        "scoringCriteria": scoring_criteria,
        "minScore": 60,
        "eligibleExpenses": eligible_expenses,
        "notEligibleExpensesText": not_eligible_expenses,
        "industryOrders": industry_orders,
        "industryBranches": industry_branches,
        "sEligibleBranchCodes": S_ELIGIBLE_BRANCH_CODES,
        "industryTechTiers": industry_tech_tiers,
    }


def main():
    data = build_track_data()
    out_path = HERE / "data.js"
    header = (
        "// קובץ מיוצר אוטומטית ע\"י sync_data.py — אין לערוך ידנית.\n"
        "// מקור: " + ", ".join(data["meta"]["sourceFiles"]) + "\n"
        "// לעדכון: לתקן במאגר (06_Knowledge_Vault) ואז להריץ מחדש sync_data.py.\n"
    )
    body = "const TRACK_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    out_path.write_text(header + body, encoding="utf-8")
    print(f"נכתב: {out_path}")
    print(f"תנאי סף: 6, יישובים: {len(data['villages'])}, סדרים כשירים: {len(data['industryOrders'])}, "
          f"ענפי עצמה טכנולוגית: {len(data['industryTechTiers'])}, מדרגות מענק: {len(data['fundingTiers'])}, "
          f"קריטריוני דירוג: {len(data['scoringCriteria'])}")


if __name__ == "__main__":
    main()
