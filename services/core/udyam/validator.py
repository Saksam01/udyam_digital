import json, re
from decimal import Decimal
DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
CUR = r"(?:₹|rs\.?|inr|rupees?|rupaye|rupay|रु\.?|रुपये|रुपए)"
MULT = {"k": 1000, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "हज़ार": 1000, "हजार": 1000, "lakh": 100000, "lac": 100000, "लाख": 100000}
NUM = r"(\d[\d,]*(?:\.\d+)?)"
MONEY = re.compile(rf"{CUR}\s*{NUM}\s*({'|'.join(MULT)})?|{NUM}\s*({'|'.join(MULT)})?\s*(?:/-|{CUR}|per month|/month|/mo\b|a month|mahina|mahine|महीना|महीने)", re.I)
PID = re.compile(r"\bP\s?-?0?([1-9]|1\d|2[0-5])\b")
PCT = re.compile(r"\d+(?:\.\d+)?\s*%")
BARE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w.])")

def _val(num, mult):
    d = Decimal(num.replace(",", "")); return d * MULT.get((mult or "").lower(), 1)

def harvest(tool_outputs: list[dict]) -> tuple[set, set]:
    nums, pids = set(), set()
    def walk(x):
        if isinstance(x, dict): [walk(v) for v in x.values()]
        elif isinstance(x, list): [walk(v) for v in x]
        elif isinstance(x, (int, float)) and not isinstance(x, bool): nums.add(Decimal(str(x)).normalize())
        elif isinstance(x, str):
            if re.fullmatch(r"P\d{2}", x): pids.add(x)
            elif re.fullmatch(r"-?\d+(\.\d+)?", x): nums.add(Decimal(x).normalize())
    for o in tool_outputs: walk(o)
    return nums, pids

def validate_reply(text: str, tool_outputs: list[dict], profile_numbers: set[int]) -> list[str]:
    t = text.translate(DEVANAGARI); nums, pids = harvest(tool_outputs); problems = []
    allowed = nums | {Decimal(n) for n in profile_numbers}
    for m in MONEY.finditer(t):
        num, mult = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        v = _val(num, mult).normalize()
        if mult:
            problems.append(f"approximate amount '{m.group(0).strip()}'")
        elif v not in nums: problems.append(f"amount {m.group(0).strip()} not returned by a tool")
    for m in PID.finditer(t):
        p = f"P{int(m.group(1)):02d}"
        if p not in pids: problems.append(f"product id {p} not returned by a tool")
    if PCT.search(t) and not any("discount" in json.dumps(o) for o in tool_outputs): problems.append("percentage/discount claim without tool basis")
    for m in BARE.finditer(t):
        v = Decimal(m.group(0).replace(",", "")).normalize()
        if v >= 100 and v not in allowed: problems.append(f"unverified number {m.group(0)}")
    return sorted(set(problems))

if __name__ == "__main__":
    q = {"lines": [{"product_id": "P01", "qty": 1, "line_monthly_list_inr": "1099.00"}, {"product_id": "P07", "qty": 2, "line_monthly_list_inr": "698.00"}],
         "monthly_inr": "1797.00", "monthly_range_inr": [1597, 1997], "setup_total_inr": 0, "contract_months": 12, "activation_eta_days": 5}
    for s in ["Aapka total ₹1,797 per month hoga, P01 fibre + 2 SIMs (P07).",
              "Bas ₹1,499 mahine mein mil jayega!", "Total around ₹1.8k/month", "Add P23 CCTV for safety",
              "मासिक शुल्क ₹१,७९७ है", "I can give you 20% off", "Your 3 employees get 2 lines, setup ₹0."]:
        print(repr(s), "->", validate_reply(s, [q], {3, 1, 2}))
