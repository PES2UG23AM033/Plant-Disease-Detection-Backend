"""
Treatment Recommendation Engine
=================================
3-step pipeline:
  Step 1 — Case Interpretation Layer
  Step 2 — Evidence Retrieval Layer
  Step 3 — Decision and Recommendation Layer

Usage:
  from treatment_recommendation import get_recommendation
  result = get_recommendation(
      disease="Canker",
      confidence=94.1,
      severity_score=42.5,
      severity_label="Moderate"
  )
  print(result)
"""

# ══════════════════════════════════════════════════════════════════════════════
# ❶  KNOWLEDGE BASE  (Evidence store for Step 2)
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = {

    "Canker": {
        "full_name":    "Citrus Canker (Xanthomonas axonopodis)",
        "type":         "Bacterial",
        "treatments": [
            {
                "product":   "Copper-based bactericide",
                "dose":      "2–3 g/L water",
                "timing":    "Apply at first symptom appearance",
                "interval":  "Repeat every 10–14 days",
                "method":    "Foliar spray",
                "warning":   "Do not spray during flowering. Avoid copper buildup in soil.",
                "organic":   True,
            },
            {
                "product":   "Streptomycin sulfate",
                "dose":      "200 ppm solution",
                "timing":    "Apply preventively before rainy season",
                "interval":  "Every 7 days during high-risk period",
                "method":    "Foliar spray",
                "warning":   "Check local regulations — restricted in some regions.",
                "organic":   False,
            },
        ],
        "cultural":   "Remove and destroy infected plant parts. Disinfect pruning tools with 10% bleach.",
        "monitoring": "Inspect weekly. Isolate infected trees to prevent spread.",
    },

    "Greening": {
        "full_name":    "Citrus Greening / Huanglongbing (HLB)",
        "type":         "Bacterial (phloem-limited)",
        "treatments": [
            {
                "product":   "Imidacloprid (systemic insecticide)",
                "dose":      "As per label — soil drench or foliar",
                "timing":    "Apply to control Asian citrus psyllid vector",
                "interval":  "Every 3 months",
                "method":    "Soil drench or foliar spray",
                "warning":   "No cure exists. Treatment controls the insect vector only.",
                "organic":   False,
            },
            {
                "product":   "Kaolin clay spray",
                "dose":      "25 g/L water",
                "timing":    "Apply before psyllid season",
                "interval":  "Every 2 weeks",
                "method":    "Foliar spray",
                "warning":   "Organic option — reduces psyllid settling.",
                "organic":   True,
            },
        ],
        "cultural":   "No cure. Remove and destroy severely infected trees immediately to prevent spread to healthy trees.",
        "monitoring": "Scout for Asian citrus psyllid weekly. Use yellow sticky traps.",
    },

    "Anthracnose": {
        "full_name":    "Anthracnose (Colletotrichum gloeosporioides)",
        "type":         "Fungal",
        "treatments": [
            {
                "product":   "Azoxystrobin",
                "dose":      "As per label — typically 0.8–1.0 mL/L",
                "timing":    "Apply at early symptom stage",
                "interval":  "Repeat after 7–10 days if required",
                "method":    "Foliar spray",
                "warning":   "Do not apply more than 3 times per season to avoid resistance.",
                "organic":   False,
            },
            {
                "product":   "Copper fungicide",
                "dose":      "2–3 g/L water",
                "timing":    "Apply during wet season preventively",
                "interval":  "Every 10–14 days",
                "method":    "Foliar spray",
                "warning":   "Avoid spraying before forecast rainfall.",
                "organic":   True,
            },
        ],
        "cultural":   "Improve air circulation by pruning. Remove fallen leaves and debris.",
        "monitoring": "Check after rainfall events. High humidity increases risk.",
    },

    "Melanose": {
        "full_name":    "Melanose (Diaporthe citri)",
        "type":         "Fungal",
        "treatments": [
            {
                "product":   "Copper oxychloride",
                "dose":      "3 g/L water",
                "timing":    "Apply before rainy season, after petal fall",
                "interval":  "Every 2–3 weeks during wet season",
                "method":    "Foliar spray",
                "warning":   "Do not apply in hot dry conditions.",
                "organic":   True,
            },
            {
                "product":   "Mancozeb",
                "dose":      "2.5 g/L water",
                "timing":    "Apply at fruit set stage",
                "interval":  "Every 14 days",
                "method":    "Foliar spray",
                "warning":   "Pre-harvest interval: 7 days.",
                "organic":   False,
            },
        ],
        "cultural":   "Remove dead wood and twigs. Prune to reduce canopy density.",
        "monitoring": "Inspect during wet weather. Spores spread via rain splash.",
    },

    "BlackSpot": {
        "full_name":    "Citrus Black Spot (Phyllosticta citricarpa)",
        "type":         "Fungal",
        "treatments": [
            {
                "product":   "Trifloxystrobin + tebuconazole",
                "dose":      "As per label",
                "timing":    "Apply from fruit set through summer",
                "interval":  "Every 6–8 weeks",
                "method":    "Foliar spray",
                "warning":   "Quarantine pest in some countries — check regulations.",
                "organic":   False,
            },
            {
                "product":   "Copper fungicide",
                "dose":      "2 g/L water",
                "timing":    "Preventive application before wet season",
                "interval":  "Every 3 weeks",
                "method":    "Foliar spray",
                "warning":   "Organic option. Less effective at high disease pressure.",
                "organic":   True,
            },
        ],
        "cultural":   "Remove fallen leaves (primary inoculum source). Avoid over-irrigation.",
        "monitoring": "Inspect fruit surface fortnightly from fruit set.",
    },

    "BacterialBlight": {
        "full_name":    "Bacterial Blight (Pseudomonas syringae)",
        "type":         "Bacterial",
        "treatments": [
            {
                "product":   "Copper hydroxide spray",
                "dose":      "2–3 g/L water",
                "timing":    "Apply before rainy season and after pruning",
                "interval":  "Every 10 days during wet conditions",
                "method":    "Foliar spray",
                "warning":   "Avoid overhead irrigation — promotes spread.",
                "organic":   True,
            },
        ],
        "cultural":   "Use copper-treated pruning cuts. Disinfect all tools. Avoid wounding plants.",
        "monitoring": "Monitor after storms or hail damage which creates entry wounds.",
    },

    "CurlVirus": {
        "full_name":    "Citrus Leaf Curl Virus",
        "type":         "Viral (aphid-transmitted)",
        "treatments": [
            {
                "product":   "Imidacloprid",
                "dose":      "As per label",
                "timing":    "Apply to control aphid vector population",
                "interval":  "Every 3–4 weeks during aphid season",
                "method":    "Foliar spray or soil drench",
                "warning":   "Controls vector, not the virus itself.",
                "organic":   False,
            },
            {
                "product":   "Neem oil",
                "dose":      "5 mL/L water + few drops dish soap",
                "timing":    "Apply when aphids are detected",
                "interval":  "Every 7 days",
                "method":    "Foliar spray (coat undersides of leaves)",
                "warning":   "Organic option. Do not spray in direct sun.",
                "organic":   True,
            },
        ],
        "cultural":   "Remove and destroy severely infected shoots. Control ant populations that protect aphids.",
        "monitoring": "Check new growth weekly for aphid colonies.",
    },

    "DeficiencyLeaf": {
        "full_name":    "Nutrient Deficiency (micronutrient)",
        "type":         "Abiotic",
        "treatments": [
            {
                "product":   "Chelated micronutrient fertilizer",
                "dose":      "As per soil test recommendation",
                "timing":    "Apply at start of growing season",
                "interval":  "Every 6–8 weeks",
                "method":    "Soil application or foliar spray",
                "warning":   "Conduct soil test first to identify specific deficiency.",
                "organic":   True,
            },
            {
                "product":   "Zinc sulfate (if zinc deficient)",
                "dose":      "2 g/L water for foliar",
                "timing":    "Apply when deficiency symptoms appear",
                "interval":  "Every 4 weeks until recovery",
                "method":    "Foliar spray",
                "warning":   "Excess zinc is toxic. Do not exceed recommended rate.",
                "organic":   False,
            },
        ],
        "cultural":   "Check soil pH — high pH locks out micronutrients. Adjust pH to 6.0–7.0.",
        "monitoring": "Compare leaf color against healthy reference. Test soil pH.",
    },

    "DryLeaf": {
        "full_name":    "Dry Leaf / Drought Stress",
        "type":         "Abiotic",
        "treatments": [
            {
                "product":   "Water / irrigation",
                "dose":      "Restore soil moisture to field capacity",
                "timing":    "Immediately upon detection",
                "interval":  "Daily until recovery, then regular schedule",
                "method":    "Drip or basin irrigation",
                "warning":   "Sudden overwatering after drought can cause root shock.",
                "organic":   True,
            },
            {
                "product":   "Seaweed-based biostimulant",
                "dose":      "2–3 mL/L water",
                "timing":    "Apply after rehydration",
                "interval":  "Every 2 weeks",
                "method":    "Foliar spray",
                "warning":   "Supports recovery — not a substitute for adequate irrigation.",
                "organic":   True,
            },
        ],
        "cultural":   "Mulch around base to retain soil moisture. Check irrigation system for blockages.",
        "monitoring": "Monitor soil moisture daily. Install drip irrigation if recurring.",
    },

    "SootyMould": {
        "full_name":    "Sooty Mould (Capnodium citri)",
        "type":         "Fungal (secondary — grows on insect honeydew)",
        "treatments": [
            {
                "product":   "Soap solution wash",
                "dose":      "5 mL mild dish soap per litre of water",
                "timing":    "Wash affected leaves immediately",
                "interval":  "Weekly until mould disappears",
                "method":    "Spray and wipe leaves",
                "warning":   "Treat underlying insect pest first or mould will return.",
                "organic":   True,
            },
            {
                "product":   "Imidacloprid (for scale/mealybug control)",
                "dose":      "As per label",
                "timing":    "Apply to control honeydew-producing insects",
                "interval":  "Every 4 weeks",
                "method":    "Foliar or soil drench",
                "warning":   "Target the insect pest — sooty mould is a symptom, not cause.",
                "organic":   False,
            },
        ],
        "cultural":   "Prune to improve airflow. Control scale insects and mealybugs which produce honeydew.",
        "monitoring": "Inspect undersides of leaves for scale, mealybug, whitefly colonies.",
    },

    "SpiderMites": {
        "full_name":    "Spider Mites (Panonychus citri / Tetranychus urticae)",
        "type":         "Pest (Arachnid)",
        "treatments": [
            {
                "product":   "Abamectin miticide",
                "dose":      "0.5–1.0 mL/L water",
                "timing":    "Apply when mite population exceeds threshold",
                "interval":  "Repeat after 7–10 days if needed",
                "method":    "Foliar spray — ensure full coverage of leaf undersides",
                "warning":   "Rotate with different chemistry to prevent resistance.",
                "organic":   False,
            },
            {
                "product":   "Neem oil",
                "dose":      "5 mL/L water",
                "timing":    "Apply at first mite detection",
                "interval":  "Every 5–7 days",
                "method":    "Foliar spray (coat leaf undersides thoroughly)",
                "warning":   "Organic option. Spray in cooler hours to avoid phytotoxicity.",
                "organic":   True,
            },
        ],
        "cultural":   "Increase humidity around plants. Avoid dusty conditions. Introduce predatory mites.",
        "monitoring": "Use hand lens to inspect leaf undersides. Look for fine webbing and stippling.",
    },

    "LeafMiner": {
        "full_name":    "Citrus Leaf Miner (Phyllocnistis citrella)",
        "type":         "Pest (Lepidoptera)",
        "treatments": [
            {
                "product":   "Spinosad",
                "dose":      "0.5 mL/L water",
                "timing":    "Apply when new leaf flushes are detected",
                "interval":  "Every 7–10 days during flush period",
                "method":    "Foliar spray on new growth",
                "warning":   "Effective against young larvae only — not adults.",
                "organic":   True,
            },
            {
                "product":   "Imidacloprid (systemic)",
                "dose":      "As per label",
                "timing":    "Soil drench before new flush emergence",
                "interval":  "Once per flush cycle",
                "method":    "Soil drench",
                "warning":   "Systemic — absorbed by plant and kills mining larvae.",
                "organic":   False,
            },
        ],
        "cultural":   "Remove severely mined leaves. Time pruning to avoid stimulating excessive new flushes.",
        "monitoring": "Monitor new growth flushes. Check for characteristic winding mines on young leaves.",
    },

    "Healthy": {
        "full_name":    "Healthy leaf — no disease detected",
        "type":         "None",
        "treatments":   [],
        "cultural":     "Continue regular fertilization, irrigation, and pest monitoring.",
        "monitoring":   "Inspect weekly as a preventive measure.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# ❷  STEP 1 — CASE INTERPRETATION LAYER
# ══════════════════════════════════════════════════════════════════════════════

CONFIDENCE_THRESHOLD = 60.0   # below this → low confidence warning
DISEASE_ALIASES = {
    "Greening":     "Greening",
    "HLB":          "Greening",
    "BlackSpot":    "BlackSpot",
    "Black_spot":   "BlackSpot",
    "BacterialBlight": "BacterialBlight",
}

def interpret_case(disease: str,
                   confidence: float,
                   severity_score: float,
                   severity_label: str) -> dict:
    """
    Step 1: Validate and structure the model output into a treatment case.

    Args:
      disease        : raw disease string from Stage 1 classifier
      confidence     : confidence % (0–100)
      severity_score : final hybrid severity score (0–100)
      severity_label : Mild / Moderate / Severe / Critical

    Returns:
      structured case dict
    """
    # Normalize disease name
    disease_norm = DISEASE_ALIASES.get(disease, disease)

    # Validate disease exists in knowledge base
    if disease_norm not in KNOWLEDGE_BASE:
        return {
            "valid":           False,
            "error":           f"Unknown disease: {disease}",
            "disease":         disease_norm,
            "confidence":      confidence,
            "severity_score":  severity_score,
            "severity_label":  severity_label,
            "treatment_need":  "Unknown",
        }

    # Low confidence warning
    low_confidence = confidence < CONFIDENCE_THRESHOLD

    # Map severity to treatment intent
    if disease_norm == "Healthy":
        treatment_need = "None"
    elif severity_label == "Mild":
        treatment_need = "Monitor"
    elif severity_label == "Moderate":
        treatment_need = "Treat"
    elif severity_label == "Severe":
        treatment_need = "Treat urgently"
    else:
        treatment_need = "Emergency — consult expert"

    return {
        "valid":           True,
        "disease":         disease_norm,
        "full_name":       KNOWLEDGE_BASE[disease_norm]["full_name"],
        "disease_type":    KNOWLEDGE_BASE[disease_norm]["type"],
        "confidence":      round(confidence, 1),
        "low_confidence":  low_confidence,
        "severity_score":  round(severity_score, 1),
        "severity_label":  severity_label,
        "treatment_need":  treatment_need,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ❸  STEP 2 — EVIDENCE RETRIEVAL LAYER
# ══════════════════════════════════════════════════════════════════════════════

def retrieve_evidence(case: dict) -> dict:
    """
    Step 2: Retrieve treatment candidates from knowledge base.

    Args:
      case : output from interpret_case()

    Returns:
      dict with treatment candidates, cultural advice, monitoring guidance
    """
    if not case["valid"]:
        return {"candidates": [], "cultural": "", "monitoring": ""}

    disease   = case["disease"]
    kb_entry  = KNOWLEDGE_BASE[disease]
    candidates = kb_entry.get("treatments", [])

    return {
        "candidates":  candidates,
        "cultural":    kb_entry.get("cultural", ""),
        "monitoring":  kb_entry.get("monitoring", ""),
        "source":      "Internal agricultural knowledge base",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ❹  STEP 3 — DECISION AND RECOMMENDATION LAYER
# ══════════════════════════════════════════════════════════════════════════════

def make_recommendation(case: dict, evidence: dict) -> dict:
    """
    Step 3: Select best treatment and generate severity-aware recommendation.

    Decision logic:
      Healthy   → no treatment
      Monitor   → cultural advice only, watch and wait
      Treat     → standard dose, first-line treatment
      Treat urgently → stronger option, upper label range if available
      Emergency → urgent + expert consultation warning

    Returns:
      final recommendation dict ready for API response / frontend display
    """
    treatment_need = case["treatment_need"]
    severity_label = case["severity_label"]
    candidates     = evidence["candidates"]

    # ── Healthy ───────────────────────────────────────────────────────────────
    if case["disease"] == "Healthy" or treatment_need == "None":
        return {
            "disease":                case["disease"],
            "full_name":              case["full_name"],
            "confidence":             case["confidence"],
            "severity_label":         "Healthy",
            "treatment_need":         "None",
            "recommended_treatment":  "No treatment required",
            "product":                None,
            "dose":                   None,
            "timing":                 None,
            "interval":               None,
            "method":                 None,
            "warning":                None,
            "cultural_advice":        evidence["cultural"],
            "monitoring":             evidence["monitoring"],
            "urgency_note":           None,
            "low_confidence_warning": case.get("low_confidence", False),
            "reason": "Leaf appears healthy. Continue regular care and monitoring.",
        }

    # ── No candidates ─────────────────────────────────────────────────────────
    if not candidates:
        return {
            "disease":                case["disease"],
            "full_name":              case["full_name"],
            "confidence":             case["confidence"],
            "severity_label":         severity_label,
            "treatment_need":         treatment_need,
            "recommended_treatment":  "Consult local agricultural extension officer",
            "product":                None,
            "dose":                   None,
            "timing":                 "As soon as possible",
            "interval":               None,
            "method":                 None,
            "warning":                "No standard treatment found in knowledge base.",
            "cultural_advice":        evidence["cultural"],
            "monitoring":             evidence["monitoring"],
            "urgency_note":           "Seek expert advice immediately.",
            "low_confidence_warning": case.get("low_confidence", False),
            "reason": f"No treatment candidates found for {case['disease']}.",
        }

    # ── Select treatment based on severity ────────────────────────────────────
    if treatment_need in ("Treat urgently", "Emergency — consult expert"):
        # Prefer non-organic (stronger) for severe cases
        non_organic = [c for c in candidates if not c.get("organic", True)]
        selected = non_organic[0] if non_organic else candidates[0]
    else:
        # Prefer organic for mild/moderate
        organic = [c for c in candidates if c.get("organic", False)]
        selected = organic[0] if organic else candidates[0]

    # ── Build urgency note ────────────────────────────────────────────────────
    urgency_map = {
        "Monitor":                 "Low urgency — monitor and treat if worsening.",
        "Treat":                   "Moderate urgency — apply treatment within 2–3 days.",
        "Treat urgently":          "High urgency — apply treatment today.",
        "Emergency — consult expert": "CRITICAL — apply emergency treatment and contact agronomist immediately.",
    }
    urgency_note = urgency_map.get(treatment_need, "")

    # ── Dose adjustment by severity ───────────────────────────────────────────
    dose_note = selected["dose"]
    if severity_label in ("Severe", "Critical"):
        dose_note = f"{selected['dose']} (use upper end of label range)"
    elif severity_label == "Mild":
        dose_note = f"{selected['dose']} (use lower end of label range)"

    # ── Reason string ─────────────────────────────────────────────────────────
    reason = (
        f"{severity_label} {case['disease']} infection detected "
        f"(score {case['severity_score']}%). "
        f"{selected['product']} selected as {'organic' if selected.get('organic') else 'standard'} "
        f"first-line treatment. {urgency_note}"
    )

    # ── Low confidence warning ────────────────────────────────────────────────
    lc_warning = None
    if case.get("low_confidence"):
        lc_warning = (
            f"Model confidence is {case['confidence']}% — below threshold. "
            "Visually verify the disease identification before applying treatment."
        )

    return {
        "disease":                case["disease"],
        "full_name":              case["full_name"],
        "disease_type":           case["disease_type"],
        "confidence":             case["confidence"],
        "severity_label":         severity_label,
        "severity_score":         case["severity_score"],
        "treatment_need":         treatment_need,
        "recommended_treatment":  selected["product"],
        "product":                selected["product"],
        "dose":                   dose_note,
        "timing":                 selected["timing"],
        "interval":               selected["interval"],
        "method":                 selected["method"],
        "warning":                selected["warning"],
        "organic":                selected.get("organic", False),
        "cultural_advice":        evidence["cultural"],
        "monitoring":             evidence["monitoring"],
        "urgency_note":           urgency_note,
        "low_confidence_warning": lc_warning,
        "reason":                 reason,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ❺  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def get_recommendation(disease: str,
                       confidence: float,
                       severity_score: float,
                       severity_label: str) -> dict:
    """
    Full 3-step pipeline.

    Args:
      disease        : disease name from Stage 1 (e.g. "Canker")
      confidence     : model confidence % (e.g. 94.1)
      severity_score : hybrid severity score 0–100 (e.g. 42.5)
      severity_label : "Mild" / "Moderate" / "Severe" / "Critical"

    Returns:
      complete recommendation dict
    """
    case      = interpret_case(disease, confidence, severity_score, severity_label)
    evidence  = retrieve_evidence(case)
    result    = make_recommendation(case, evidence)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ❻  QUICK TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    test_cases = [
        ("Canker",      94.1, 42.5, "Moderate"),
        ("Anthracnose", 61.2, 68.0, "Severe"),
        ("Healthy",     98.5,  0.0, "Mild"),
        ("Greening",    88.0, 80.0, "Critical"),
        ("SpiderMites", 55.0, 18.0, "Mild"),
    ]

    for disease, conf, score, label in test_cases:
        print(f"\n{'═'*60}")
        print(f"  Disease: {disease}  |  Confidence: {conf}%  |  Severity: {label}")
        print(f"{'═'*60}")
        rec = get_recommendation(disease, conf, score, label)
        print(f"  Treatment   : {rec['recommended_treatment']}")
        print(f"  Dose        : {rec['dose']}")
        print(f"  Timing      : {rec['timing']}")
        print(f"  Method      : {rec['method']}")
        print(f"  Urgency     : {rec['urgency_note']}")
        if rec.get("warning"):
            print(f"  Warning     : {rec['warning']}")
        if rec.get("low_confidence_warning"):
            print(f"  LOW CONF    : {rec['low_confidence_warning']}")
        print(f"  Reason      : {rec['reason']}")
