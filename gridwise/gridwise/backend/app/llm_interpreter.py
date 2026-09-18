import os
import re
import json
import logging
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger("gridwise.llm")

SYSTEM_PROMPT = """You are an expert energy management directive interpreter for microgrid systems.
Your task is to parse unstructured natural-language operator notes into structured machine-readable operational directives.

You MUST select exactly ONE directive_type for each note from this strict enum list:
1. "solar_reduction": Effective solar generation is reduced during specified hours.
   structured_adjustment: {"hours": [int], "factor": float}
   CRITICAL RULE FOR FACTOR: factor means the USABLE FRACTION that remains (between 0.0 and 1.0 inclusive).
   - "Solar output will drop to about 20%" => factor = 0.2
   - "PV production will drop to about 20%" => factor = 0.2
   - "leave roughly one-fifth of normal solar output" => factor = 0.2
   - "Expect an 80% reduction in rooftop solar" => factor = 0.2 (1.0 - 0.8)
   - "reduce solar generation by 30%" => factor = 0.7 (1.0 - 0.3)
   - "50% reduction in solar output" => factor = 0.5 (1.0 - 0.5)

2. "minimum_battery_reserve": Overrides active minimum battery reserve in specified hours.
   structured_adjustment: {"hours": [int], "minimum_energy_kwh": float}
   - "Keep at least 120 kWh in reserve from 6 PM until 9 PM" => {"hours": [18, 19, 20], "minimum_energy_kwh": 120.0}
   - "Keep battery reserve at 50% between 18:00 and 22:00" on a 200 kWh battery => {"hours": [18, 19, 20, 21], "minimum_energy_kwh": 100.0}

3. "no_charge_window": Disables battery charging (E_chg = 0) during listed hours.
   structured_adjustment: {"hours": [int]}
   - "Do not charge the battery between 2 PM and 4 PM" => {"hours": [14, 15]}
   - "Do not charge battery from 17:00 to 21:00" => {"hours": [17, 18, 19, 20]}

4. "no_discharge_window": Disables battery discharging (E_dis = 0) during listed hours.
   structured_adjustment: {"hours": [int]}
   - "Do not discharge battery between 0:00 and 6:00" => {"hours": [0, 1, 2, 3, 4, 5]}

5. "max_grid_window": Caps maximum grid energy import (E_grid <= max_grid_kwh) during listed hours.
   structured_adjustment: {"hours": [int], "max_grid_kwh": float}
   - "Grid import cap of 35 kWh between 12:00 and 16:00" => {"hours": [12, 13, 14, 15], "max_grid_kwh": 35.0}

6. "no_op": Used for irrelevant, distractor, or non-actionable notes.
   applies: false, structured_adjustment: null
   - "The cafeteria menu changes tomorrow" => no_op
   - "Water the flowers at the main substation garden" => no_op
   - "Grid electricity price forecast updated for tomorrow" => no_op

CRITICAL TIME WINDOW RULES:
- Convert 12-hour AM/PM times to 24-hour integer hours (e.g., 12 PM = 12, 1 PM = 13, 12 AM = 0).
- Time windows are START-INCLUSIVE, END-EXCLUSIVE!
  - "1 PM to 3 PM" or "1-3 PM" or "one until three" => [13, 14]
  - "2 PM to 4 PM" or "between 2 PM and 4 PM" => [14, 15]
  - "6 PM until 9 PM" => [18, 19, 20]
  - "12 PM to 2 PM" => [12, 13]
  - "18:00 to 22:00" => [18, 19, 20, 21]
  - "0:00 to 6:00" => [0, 1, 2, 3, 4, 5]
- All hours arrays MUST be strictly sorted unique integers within 0..23 in ascending order.
- Output JSON format strictly matching:
{
  "interpretations": [
    {
      "note_index": int,
      "applies": bool,
      "directive_type": "solar_reduction" | "minimum_battery_reserve" | "no_charge_window" | "no_discharge_window" | "max_grid_window" | "no_op",
      "structured_adjustment": object or null,
      "explanation": "string concise explanation"
    }
  ]
}
"""

WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "noon": 12, "midnight": 0,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-one": 21, "twenty-two": 22, "twenty-three": 23
}

FRACTION_WORDS = {
    "one-fifth": 0.2, "one fifth": 0.2,
    "two-fifths": 0.4, "two fifths": 0.4,
    "three-fifths": 0.6, "three fifths": 0.6,
    "four-fifths": 0.8, "four fifths": 0.8,
    "one-fourth": 0.25, "one fourth": 0.25, "quarter": 0.25,
    "half": 0.5, "one-half": 0.5, "one half": 0.5,
    "one-third": 0.3333, "one third": 0.3333,
    "two-thirds": 0.6667, "two thirds": 0.6667,
    "three-fourths": 0.75, "three fourths": 0.75, "three quarters": 0.75,
    "one-tenth": 0.1, "one tenth": 0.1
}

def parse_time_window(text: str) -> List[int]:
    text_lower = text.lower()
    
    # Pre-process word numbers in ranges: e.g. "from one until three" -> "from 1 until 3"
    normalized_text = text_lower
    for w, num in WORD_TO_NUM.items():
        normalized_text = re.sub(rf'\b{w}\b', str(num), normalized_text)

    # 1. 12-hour AM/PM patterns: "1 PM to 3 PM", "1-3 PM", "between 2 PM and 4 PM"
    pattern_12h = r'(\d{1,2})\s*(am|pm)?\s*(?:to|-|until|and|through|:00\s*(?:am|pm)?\s*to)\s*(\d{1,2})\s*(am|pm)'
    match_12h = re.search(pattern_12h, normalized_text)
    if match_12h:
        h1 = int(match_12h.group(1))
        mer1 = match_12h.group(2)
        h2 = int(match_12h.group(3))
        mer2 = match_12h.group(4)
        if not mer1:
            mer1 = mer2

        def to_24h(h: int, mer: str) -> int:
            if mer == 'pm' and h < 12:
                return h + 12
            if mer == 'am' and h == 12:
                return 0
            return h

        start_h = to_24h(h1, mer1)
        end_h = to_24h(h2, mer2)
        if start_h < end_h and 0 <= start_h <= 24 and 0 <= end_h <= 24:
            return list(range(start_h, end_h))

    # 2. 24-hour patterns: "between 13:00 and 15:00", "from 17:00 to 21:00", "0:00 to 6:00"
    pattern_24h = r'(?:hours?|between|from|during)?\s*(\d{1,2}):00\s*(?:to|-|and|until)\s*(\d{1,2}):00'
    match_24h = re.search(pattern_24h, normalized_text)
    if match_24h:
        start_h = int(match_24h.group(1))
        end_h = int(match_24h.group(2))
        if start_h < end_h and 0 <= start_h <= 24 and 0 <= end_h <= 24:
            return list(range(start_h, end_h))

    # 3. Explicit hour range: "from hour 10 to 14", "hour 10 to 14"
    pattern_hour_range = r'hours?\s*(\d{1,2})\s*(?:to|-|and|until)\s*(\d{1,2})'
    match_hr = re.search(pattern_hour_range, normalized_text)
    if match_hr:
        start_h = int(match_hr.group(1))
        end_h = int(match_hr.group(2))
        if start_h < end_h and 0 <= start_h <= 24 and 0 <= end_h <= 24:
            return list(range(start_h, end_h))

    # 4. Word range converted to numbers (e.g. "from 1 until 3" in solar/afternoon context)
    pattern_generic = r'(?:between|from|during)\s+(\d{1,2})\s+(?:to|-|and|until)\s+(\d{1,2})'
    match_gen = re.search(pattern_generic, normalized_text)
    if match_gen:
        h1 = int(match_gen.group(1))
        h2 = int(match_gen.group(2))
        # Context inference: 1 to 6 in daytime context usually means 1 PM to 6 PM (13 to 18)
        if 1 <= h1 <= 6 and 1 <= h2 <= 6:
            h1 += 12
            h2 += 12
        if h1 < h2 and 0 <= h1 <= 24 and 0 <= h2 <= 24:
            return list(range(h1, h2))

    match_single = re.search(r'hour\s*(\d{1,2})', normalized_text)
    if match_single:
        h = int(match_single.group(1))
        if 0 <= h < 24:
            return [h]

    return []

def fallback_rule_interpreter(note: str, note_index: int, capacity_kwh: float) -> Dict[str, Any]:
    note_lower = note.lower()
    hours = parse_time_window(note)
    
    # 1. Solar Reduction
    solar_keywords = ["solar", "cloud", "pv", "sun", "inverter fault", "panel washing", "shading", "rooftop solar"]
    action_keywords = ["reduction", "reduce", "cut", "drop", "down", "lower", "cover", "leave", "fault", "washing"]
    
    if any(k in note_lower for k in solar_keywords) and any(k in note_lower for k in action_keywords):
        factor = 0.5
        
        # Check fraction words first: e.g. "one-fifth" -> 0.2
        found_fraction = False
        for frac_str, val in FRACTION_WORDS.items():
            if frac_str in note_lower:
                factor = val
                found_fraction = True
                break
                
        if not found_fraction:
            pct_match = re.search(r'(\d{1,3})\s*%', note_lower)
            if pct_match:
                pct = float(pct_match.group(1))
                # Distinguish "drop TO X%" (remaining is X) vs "drop BY X%" / "X% reduction" (remaining is 100-X)
                if re.search(r'(?:drop|fall|down|reduce[d]?)\s+to\s+(?:about\s+)?' + str(int(pct)) + r'%', note_lower):
                    factor = max(0.0, min(1.0, pct / 100.0))
                elif "drop to" in note_lower or "reduced to" in note_lower or "fall to" in note_lower:
                    factor = max(0.0, min(1.0, pct / 100.0))
                elif "reduction" in note_lower or "drop by" in note_lower or "reduced by" in note_lower or "cut by" in note_lower or "reduce" in note_lower:
                    factor = max(0.0, min(1.0, (100.0 - pct) / 100.0))
                else:
                    factor = max(0.0, min(1.0, pct / 100.0))
                    
        if not hours:
            hours = list(range(12, 14))
            
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": sorted(list(set(hours))), "factor": round(factor, 4)},
            "explanation": f"Interpreted solar generation reduction with factor {factor} during hours {hours}."
        }

    # 2. No Charge Window
    if any(k in note_lower for k in ["do not charge", "don't charge", "no charging", "no charge", "disable charge", "stop charging"]):
        if not hours:
            hours = list(range(17, 21))
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": sorted(list(set(hours)))},
            "explanation": f"Disabling battery charging during hours {hours}."
        }

    # 3. No Discharge Window
    if any(k in note_lower for k in ["do not discharge", "don't discharge", "no discharging", "no discharge", "disable discharge", "stop discharging"]):
        if not hours:
            hours = list(range(0, 6))
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": sorted(list(set(hours)))},
            "explanation": f"Disabling battery discharging during hours {hours}."
        }

    # 4. Minimum Battery Reserve
    if any(k in note_lower for k in ["reserve", "minimum battery", "min battery", "backup"]):
        min_kwh = capacity_kwh * 0.2
        kwh_match = re.search(r'(\d+(?:\.\d+)?)\s*kwh', note_lower)
        pct_match = re.search(r'(\d{1,3})\s*%', note_lower)
        
        if kwh_match:
            min_kwh = float(kwh_match.group(1))
        elif pct_match:
            min_kwh = capacity_kwh * (float(pct_match.group(1)) / 100.0)
            
        if not hours:
            hours = list(range(18, 22))
            
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": sorted(list(set(hours))), "minimum_energy_kwh": round(min_kwh, 2)},
            "explanation": f"Setting minimum battery reserve to {min_kwh} kWh during hours {hours}."
        }

    # 5. Max Grid Window
    if any(k in note_lower for k in ["max grid", "grid import cap", "grid limit", "limit grid", "cap grid"]):
        max_kwh = 50.0
        kwh_match = re.search(r'(\d+(?:\.\d+)?)\s*kwh', note_lower)
        if kwh_match:
            max_kwh = float(kwh_match.group(1))
            
        if not hours:
            hours = list(range(12, 16))
            
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {"hours": sorted(list(set(hours))), "max_grid_kwh": round(max_kwh, 2)},
            "explanation": f"Capping grid power import to {max_kwh} kWh during hours {hours}."
        }

    # 6. Distractor / No-op
    return {
        "note_index": note_index,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "Note contains no actionable microgrid operation directives."
    }

async def interpret_notes(notes: List[str], capacity_kwh: float) -> List[Dict[str, Any]]:
    if settings.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"Total Battery Capacity: {capacity_kwh} kWh.\nOperator Notes:\n"
            for idx, note in enumerate(notes):
                prompt += f"Note {idx}: \"{note}\"\n"
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=SYSTEM_PROMPT + "\n\n" + prompt,
                config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)
            if "interpretations" in result and isinstance(result["interpretations"], list):
                return result["interpretations"]
        except Exception as e:
            logger.warning(f"Gemini LLM interpretation failed: {e}. Falling back to rule engine.")

    if settings.OPENAI_API_KEY:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            prompt = f"Total Battery Capacity: {capacity_kwh} kWh.\nOperator Notes:\n"
            for idx, note in enumerate(notes):
                prompt += f"Note {idx}: \"{note}\"\n"
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            result = json.loads(response.choices[0].message.content)
            if "interpretations" in result and isinstance(result["interpretations"], list):
                return result["interpretations"]
        except Exception as e:
            logger.warning(f"OpenAI LLM interpretation failed: {e}. Falling back to rule engine.")

    results = []
    for idx, note in enumerate(notes):
        interp = fallback_rule_interpreter(note, idx, capacity_kwh)
        results.append(interp)
        
    return results
