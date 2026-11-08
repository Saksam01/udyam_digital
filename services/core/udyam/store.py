from __future__ import annotations
import collections, hashlib, json, os, sqlite3, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("UDYAM_DB", os.path.normpath(os.path.join(HERE, "..", "data", "udyam.db")))

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_ready = threading.Event()

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads(
  lead_id TEXT PRIMARY KEY, origin TEXT, created_at REAL, updated_at REAL,
  business TEXT, business_type TEXT, bt_key TEXT, segment TEXT, city TEXT, state TEXT, language TEXT, source TEXT,
  stage TEXT, status TEXT, drop_reason TEXT, employees INT, sites INT, gstin TEXT, gst_status TEXT,
  contact TEXT, phone TEXT, spend REAL, interest TEXT, p_activate REAL, signals TEXT, action TEXT, action_done TEXT,
  bundle TEXT, partner_id TEXT, session_id TEXT);
CREATE INDEX IF NOT EXISTS ix_leads_rank ON leads(status, p_activate DESC);
CREATE TABLE IF NOT EXISTS orders(
  order_id TEXT PRIMARY KEY, lead_id TEXT, created_at REAL, updated_at REAL, status TEXT,
  quote TEXT, lines TEXT, kyc TEXT, partner_id TEXT, business TEXT, city TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, lead_id TEXT, order_id TEXT, kind TEXT, text TEXT, actor TEXT);
CREATE INDEX IF NOT EXISTS ix_events_order ON events(order_id, id);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(id DESC);
CREATE TABLE IF NOT EXISTS consents(
  consent_id TEXT PRIMARY KEY, order_id TEXT, lead_id TEXT, created_at REAL, artifact TEXT, artifact_sha256 TEXT,
  status TEXT, withdrawn_at REAL);
CREATE INDEX IF NOT EXISTS ix_consents_order ON consents(order_id);
CREATE TABLE IF NOT EXISTS partners(
  partner_id TEXT PRIMARY KEY, name TEXT, kind TEXT, city TEXT, phone TEXT);
"""

FIRST = ["Ravi", "Anil", "Suresh", "Mahesh", "Imran", "Vikram", "Karthik", "Rohit", "Sanjay", "Deepak", "Arjun", "Naveen",
         "Priya", "Sunita", "Kavita", "Meena", "Anjali", "Farah", "Lakshmi", "Pooja"]
LAST = ["Kumar", "Sharma", "Patil", "Reddy", "Nair", "Singh", "Khan", "Iyer", "Gupta", "Das", "Mehta", "Rao", "Joshi", "Pillai"]


def db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.executescript(SCHEMA)
            cols = {r[1] for r in _conn.execute("PRAGMA table_info(orders)")}
            if "access_key" not in cols:
                _conn.execute("ALTER TABLE orders ADD COLUMN access_key TEXT")
            if "resume_hash" not in cols:
                _conn.execute("ALTER TABLE orders ADD COLUMN resume_hash TEXT")
        return _conn


def reset_connection():
    """Used by tests to point at a fresh database file."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _ready.clear()


def q(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in db().execute(sql, args).fetchall()]


def one(sql: str, args: tuple = ()) -> dict | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def x(sql: str, args: tuple = ()):
    with _lock:
        return db().execute(sql, args)


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def loads(s, default=None):
    if s in (None, ""):
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def log(kind: str, text: str, lead_id: str | None = None, order_id: str | None = None, actor: str = "system"):
    x("INSERT INTO events(ts, lead_id, order_id, kind, text, actor) VALUES (?,?,?,?,?,?)",
      (time.time(), lead_id, order_id, kind, text, actor))
    publish(kind, lead_id, order_id)


_seq = 0
_recent: "collections.deque[dict]" = collections.deque(maxlen=1000)
_cond = threading.Condition()


def publish(kind: str, lead_id: str | None = None, order_id: str | None = None):
    global _seq
    with _cond:
        _seq += 1
        _recent.append({"seq": _seq, "kind": kind, "lead_id": lead_id, "order_id": order_id, "ts": time.time()})
        _cond.notify_all()


def seq() -> int:
    return _seq


def changes_since(after: int) -> list[dict]:
    with _cond:
        return [e for e in _recent if e["seq"] > after]


def wait_for_change(after: int, timeout: float) -> int:
    with _cond:
        if _seq <= after:
            _cond.wait(timeout)
        return _seq


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


CITY_ALIAS = {"bangalore": "Bengaluru", "bengaluru": "Bengaluru", "mysore": "Mysuru", "bombay": "Mumbai", "calcutta": "Kolkata",
              "madras": "Chennai", "poona": "Pune", "baroda": "Vadodara", "cochin": "Kochi", "vizag": "Visakhapatnam",
              "new delhi": "Delhi", "nasik": "Nashik", "gurgaon": "Gurugram"}
TEAM = {"Field engineer": 3, "Channel partner": 2}


def canon_city(city: str | None) -> str:
    c = " ".join((city or "").split()).strip(" .,")
    return CITY_ALIAS.get(c.lower(), c.title())


def _add_city(city: str):
    for kind, n in TEAM.items():
        for i in range(n):
            h = _h(f"{city}|{kind}|{i}")
            name = f"{FIRST[h % len(FIRST)]} {LAST[(h // 7) % len(LAST)]}"
            phone = "+91 9" + str(h % 10**9).zfill(9)
            pid = "PT-" + hashlib.sha1(f"{city}|{kind}|{i}".encode()).hexdigest()[:6].upper()
            db().execute("INSERT OR IGNORE INTO partners VALUES (?,?,?,?,?)", (pid, name, kind, city, phone))


def seed_partners(cities: list[str]):
    with _lock:
        for city in sorted({canon_city(c) for c in cities if c}):
            have = one("SELECT COUNT(*) AS n FROM partners WHERE city=?", (city,))["n"]
            if have < sum(TEAM.values()):
                _add_city(city)


def partner_for(city: str | None, kind: str = "Field engineer") -> dict | None:
    city = canon_city(city)
    if not city:
        return None
    with _lock:
        if not one("SELECT 1 AS n FROM partners WHERE city=? AND kind=?", (city, kind)):
            _add_city(city)
        col = "partner_id"
        return one(f"""SELECT p.*, (SELECT COUNT(*) FROM orders o WHERE o.{col}=p.partner_id AND o.status NOT IN ('live','cancelled'))
                         + (SELECT COUNT(*) FROM leads l WHERE l.{col}=p.partner_id AND l.status IN ('open','review')) AS load
                       FROM partners p WHERE p.city=? AND p.kind=? ORDER BY load, p.partner_id LIMIT 1""", (city, kind))


def fix_partner_cities():
    for r in q("""SELECT l.lead_id, l.city, p.city AS pc, p.kind FROM leads l JOIN partners p ON p.partner_id=l.partner_id
                  WHERE l.origin='live'"""):
        if canon_city(r["city"]) and canon_city(r["city"]) != r["pc"]:
            np = partner_for(r["city"], r["kind"])
            if np:
                x("UPDATE leads SET partner_id=? WHERE lead_id=?", (np["partner_id"], r["lead_id"]))
    for r in q("SELECT o.order_id, o.city, p.city AS pc FROM orders o JOIN partners p ON p.partner_id=o.partner_id"):
        if canon_city(r["city"]) and canon_city(r["city"]) != r["pc"]:
            np = partner_for(r["city"], "Field engineer")
            if np:
                x("UPDATE orders SET partner_id=? WHERE order_id=?", (np["partner_id"], r["order_id"]))


def partner(pid: str | None) -> dict | None:
    return one("SELECT * FROM partners WHERE partner_id=?", (pid,)) if pid else None


def ready() -> bool:
    return _ready.is_set()


def mark_ready():
    _ready.set()


def wait_ready(timeout: float = 60.0) -> bool:
    return _ready.wait(timeout)
