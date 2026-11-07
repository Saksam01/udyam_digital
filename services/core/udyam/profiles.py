from __future__ import annotations
from dataclasses import dataclass, field

LABEL = {
    "P01": "Always-on shop and office internet", "P02": "Fast fibre internet", "P03": "Gigabit fibre for heavy work",
    "P04": "Wireless internet (5G AirFiber)", "P05": "Dedicated leased line", "P06": "High-capacity leased line",
    "P07": "Business mobile lines", "P08": "Business mobile lines (high data)", "P09": "Backup internet with auto failover",
    "P10": "One secure network across branches", "P11": "Fixed public IP address", "P12": "Business phone system",
    "P13": "Toll-free customer number", "P14": "Bulk SMS to customers", "P15": "WhatsApp for customers",
    "P16": "Business email and office apps", "P17": "Cloud backup (1 TB)", "P18": "Website and business domain",
    "P19": "Billing and POS", "P20": "Device protection", "P21": "Managed firewall", "P22": "Secure Wi-Fi with guest network",
    "P23": "Cloud CCTV cameras", "P24": "Machine monitoring", "P25": "Vehicle tracking",
}

NEED_TAGS = {
    "internet": "P01", "backup_internet": "P09", "mobile_lines": "P07", "phone_system": "P12", "toll_free": "P13",
    "sms": "P14", "whatsapp": "P15", "email": "P16", "cloud_backup": "P17", "website": "P18", "billing": "P19",
    "device_security": "P20", "firewall": "P21", "guest_wifi": "P22", "cctv": "P23", "machine_monitoring": "P24",
    "vehicle_tracking": "P25", "branch_network": "P10", "static_ip": "P11",
}


@dataclass(frozen=True)
class Spec:
    key: str
    name: str
    segment: str
    bundle: str
    tagline: str
    access: tuple
    lines: tuple
    core: tuple
    suggest: tuple
    why: str
    roles: tuple = ()
    data_types: tuple = ()
    lines_per_site: float = 0.0
    labels: dict = field(default_factory=dict)


def S(key, name, segment, bundle, tagline, access, lines, core, suggest, why, roles=(), data_types=(), lps=0.0, labels=None):
    return Spec(key, name, segment, bundle, tagline, tuple(access), tuple(lines), tuple(core), tuple(suggest), why,
                tuple(roles), tuple(data_types), lps, labels or {})


SPECS = {s.key: s for s in [
    S("kirana", "kirana store", "micro", "Kirana Counter Pack", "Billing and UPI that never stop at the counter",
      ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters")], ["P23", "P15", "P22", "P18", "P17"],
      "A kirana lives on UPI and billing, so the internet cannot drop at the counter. This pairs reliable fibre with cloud billing and business lines for you and your helper.",
      data_types=("Kirana store",), labels={"P19": "Billing and GST invoices", "P15": "WhatsApp order desk", "P23": "Shop CCTV"}),
    S("salon", "salon", "micro", "Salon Studio Pack", "Bookings, billing and a Wi-Fi your clients will use",
      ["P01", "P04"], ("P07", 0.5, 1, 3), [("P19", "counters"), ("P22", "sites")], ["P15", "P18", "P23", "P14"],
      "A salon runs on appointments and card or UPI payments. This keeps billing online, gives clients secure guest Wi-Fi, and leaves room for WhatsApp appointment reminders.",
      data_types=("Salon",), labels={"P19": "Salon billing and bookings", "P22": "Client Wi-Fi (guest network)", "P15": "WhatsApp appointment reminders", "P18": "Booking website"}),
    S("pharmacy", "pharmacy", "micro", "Pharmacy Care Pack", "Fast billing and safe records for a busy chemist",
      ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters"), ("P23", "cams")], ["P17", "P15", "P22", "P18"],
      "A chemist needs quick billing, stock records that are never lost and a camera on the counter. Internet, billing and CCTV come together, with backup for your bills and records.",
      data_types=("Pharmacy",), labels={"P19": "Pharmacy billing and stock", "P17": "Backup for bills and records", "P15": "WhatsApp refill reminders"}),
    S("retail", "retail shop", "micro", "Retail Shop Pack", "Billing, security and customers in one plan",
      ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters"), ("P23", "cams")], ["P22", "P15", "P18", "P17"],
      "A shop needs billing that always works and eyes on the floor. This covers fibre, cloud billing and CCTV, and you can add WhatsApp offers or a website when you are ready.",
      data_types=("Stationery shop", "Hardware store", "Optician")),
    S("bakery", "bakery or sweet shop", "micro", "Bakery and Sweets Pack", "Counter billing plus a way for customers to order",
      ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters")], ["P15", "P18", "P23", "P22"],
      "Counter billing is the backbone, and festival orders arrive on WhatsApp and calls. This keeps billing online and makes it easy to add a WhatsApp order desk and an order website.",
      data_types=("Bakery", "Sweet shop"), labels={"P15": "WhatsApp order desk", "P18": "Order website"}),
    S("apparel", "boutique or apparel shop", "micro", "Boutique Pack", "Billing, CCTV and a catalogue your customers can reach",
      ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters"), ("P23", "cams")], ["P15", "P18", "P22"],
      "Apparel sells on trust and on repeat customers. This covers billing and store security, with WhatsApp catalogue and offers as the natural next step.",
      data_types=("Boutique",), labels={"P15": "WhatsApp catalogue and offers"}),
    S("mobile_repair", "mobile repair shop", "micro", "Repair Shop Pack", "Reliable internet and extra lines for a customer-facing workshop",
      ["P01", "P04"], ("P07", 0.7, 2, 4), [("P19", "counters")], ["P18", "P15", "P23", "P22", "P17"],
      "A repair shop depends on downloads, calls to customers and billing. You get fibre, more business lines than a typical shop, and cloud billing.",
      data_types=("Mobile repair shop",), labels={"P19": "Job cards and billing"}),

    S("clinic", "clinic", "prof", "Clinic Care Pack", "Patient records, reception billing and reminders that never go offline",
      ["P02", "P01"], ("P07", 0.3, 2, 6), [("P16", "seats"), ("P09", "sites")], ["P15", "P17", "P23", "P20", "P22", "P12"],
      "A clinic cannot afford the internet dropping at reception. This gives fast fibre with automatic 4G or 5G backup, email for doctors and staff, and room for appointment reminders and record backup.",
      roles=(("Doctors", 0.25, 1), ("Reception and billing", 0.15, 1), ("Clinical staff", 0.2, 0)),
      data_types=("Dental clinic", "Physiotherapy clinic"),
      labels={"P09": "Backup internet so reception never goes offline", "P16": "Doctor and staff email", "P15": "WhatsApp appointment reminders",
              "P17": "Secure backup for patient records", "P22": "Waiting-room Wi-Fi (guest network)"}),
    S("dental", "dental clinic", "prof", "Dental Clinic Pack", "Scans, recalls and billing on a connection that stays up",
      ["P02", "P01"], ("P07", 0.3, 2, 5), [("P16", "seats"), ("P09", "sites")], ["P15", "P17", "P23", "P22", "P20"],
      "Dental practices move large scans and rely on recall reminders. This gives fast fibre with backup, email for dentists and staff, and storage and WhatsApp options for scans and patient recalls.",
      roles=(("Dentists", 0.25, 1), ("Reception", 0.15, 1), ("Dental assistants", 0.2, 0)),
      data_types=("Dental clinic",),
      labels={"P09": "Backup internet so reception never goes offline", "P16": "Dentist and staff email", "P15": "WhatsApp recall reminders",
              "P17": "Backup for scans and patient records", "P22": "Waiting-room Wi-Fi (guest network)"}),
    S("diagnostic", "diagnostic lab", "prof", "Diagnostic Lab Pack", "Reports delivered on time, records always backed up",
      ["P02", "P01"], ("P07", 0.25, 2, 6), [("P16", "seats"), ("P09", "sites"), ("P17", "1")], ["P12", "P15", "P14", "P20", "P23"],
      "Labs deliver reports and handle sample bookings by phone. This pairs fibre with automatic backup, report-safe cloud storage and staff email, with a phone system and WhatsApp report alerts as add-ons.",
      roles=(("Technicians and pathologists", 0.3, 1), ("Front desk", 0.15, 1), ("Reports and billing", 0.15, 0)),
      data_types=("Diagnostic lab",), labels={"P17": "Backup for patient reports", "P15": "WhatsApp report-ready alerts", "P12": "Booking and enquiry phone lines"}),
    S("ca", "CA or accounting firm", "prof", "CA Office Pack", "Client data kept safe, filing season handled",
      ["P02", "P01"], ("P07", 0.4, 2, 6), [("P16", "seats"), ("P17", "1"), ("P20", "devs")], ["P09", "P12", "P14", "P18"],
      "A CA office holds sensitive client data and peaks at filing deadlines. This gives fast fibre, professional email, client-data backup and protected laptops.",
      roles=(("Partners", 0.1, 1), ("Audit and accounts staff", 0.7, 1), ("Admin", 0.1, 0)),
      data_types=("CA firm", "Insurance agency"), labels={"P17": "Client data backup", "P20": "Protection for client-data laptops"}),
    S("coaching", "coaching centre", "prof", "Coaching Centre Pack", "Student Wi-Fi, parent updates and faculty email",
      ["P02", "P01"], ("P07", 0.2, 2, 4), [("P16", "seats"), ("P22", "sites")], ["P15", "P18", "P23", "P14", "P17"],
      "A coaching centre needs reliable Wi-Fi for students and staff and a simple way to reach parents. This covers fibre, faculty email and a guest network, with WhatsApp parent updates ready to add.",
      roles=(("Faculty", 0.5, 1), ("Admin and counsellors", 0.2, 1)),
      data_types=("Coaching centre",), labels={"P22": "Student Wi-Fi (guest network)", "P15": "WhatsApp updates to parents", "P16": "Faculty and admin email"}),
    S("law", "law office", "prof", "Chambers Pack", "Case files safe, clients reachable",
      ["P02", "P01"], ("P07", 0.4, 2, 6), [("P16", "seats"), ("P17", "1"), ("P20", "devs")], ["P09", "P12", "P23"],
      "A law office lives on case files and client confidentiality. This gives fast fibre, professional email, secure backup of case files and protected devices.",
      roles=(("Advocates", 0.4, 1), ("Juniors and clerks", 0.4, 1), ("Admin", 0.1, 0)),
      data_types=("Law office",), labels={"P17": "Case-file backup", "P16": "Chambers email"}),
    S("software", "software or IT company", "prof", "Tech Team Pack", "Fast, fixed-IP connectivity with protected laptops",
      ["P03", "P02", "P01"], ("P08", 0.3, 2, 8), [("P16", "seats"), ("P09", "sites"), ("P20", "devs"), ("P11", "1")], ["P21", "P17", "P12", "P22"],
      "A tech team needs bandwidth, a fixed IP for VPN and servers, and laptops that are protected. This delivers fast fibre with automatic backup, a static IP, email and device protection.",
      roles=(("Engineers", 0.7, 1), ("Operations and admin", 0.2, 1)),
      data_types=(), labels={"P11": "Fixed IP for VPN and servers", "P20": "Developer laptop protection", "P09": "Backup internet for uninterrupted work"}),
    S("consulting", "consulting firm", "prof", "Consulting Desk Pack", "Always reachable, client files protected",
      ["P02", "P01"], ("P08", 0.4, 2, 6), [("P16", "seats"), ("P20", "devs")], ["P17", "P09", "P12", "P18", "P22"],
      "Consultants work from client sites and rely on email and calls. This gives fast fibre, professional email, high-data mobile lines and protected devices.",
      roles=(("Consultants", 0.6, 1), ("Admin and finance", 0.15, 1)), data_types=("Architecture studio",)),
    S("agency", "agency (insurance, travel or real estate)", "prof", "Agency Desk Pack", "Calls, WhatsApp and leads handled in one place",
      ["P02", "P01"], ("P08", 0.6, 2, 8), [("P16", "seats")], ["P15", "P14", "P18", "P13", "P12"],
      "Agencies win on how quickly they reply to enquiries. This gives fast fibre, plenty of business lines, email, and WhatsApp and SMS options to follow up with customers.",
      roles=(("Agents and advisors", 0.5, 1), ("Back office", 0.2, 1)),
      data_types=("Real estate agency", "Travel agency"), labels={"P13": "Toll-free enquiry number", "P15": "WhatsApp lead follow-up"}),

    S("restaurant", "restaurant or cafe", "multi", "Restaurant Outlet Pack", "Every outlet billing, ordering and online",
      ["P01", "P02"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P19", "counters"), ("P22", "sites")], ["P13", "P15", "P10", "P23", "P25", "P18"],
      "For restaurants, a dropped link at one outlet means lost orders. Each outlet gets its own fibre with automatic backup, cloud billing and guest Wi-Fi, with central options for reservations and delivery.",
      lps=0.5, data_types=("Restaurant chain", "Bakery chain"),
      labels={"P19": "Restaurant billing (POS)", "P22": "Guest Wi-Fi", "P13": "Reservations toll-free number", "P15": "WhatsApp orders and reservations", "P25": "Delivery vehicle tracking"}),
    S("multistore", "multi-store retailer", "multi", "Multi-Store Retail Pack", "Every store billing on one reliable network",
      ["P01", "P02"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P19", "counters"), ("P23", "cams")], ["P10", "P15", "P13", "P22", "P20"],
      "A store chain needs every counter online and every shop watched. Each store gets fibre with automatic backup, cloud billing and CCTV, with a single network across branches as a next step.",
      lps=0.5, data_types=("Electronics retail chain", "Apparel retail chain"), labels={"P19": "Store billing (POS)"}),
    S("hotel", "hotel or guesthouse group", "multi", "Hospitality Group Pack", "Guest Wi-Fi, reservations and always-on front desk",
      ["P02", "P01"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P22", "sites"), ("P23", "cams"), ("P13", "1")], ["P10", "P12", "P15", "P21", "P18"],
      "Guests judge a hotel by its Wi-Fi and how easily they can book. This gives each property fast fibre with backup, guest Wi-Fi, CCTV and a toll-free reservations number.",
      lps=0.5, data_types=("Budget hotel group",), labels={"P22": "Guest Wi-Fi", "P13": "Reservations toll-free number", "P23": "Lobby and corridor CCTV"}),
    S("gym", "gym or fitness chain", "multi", "Fitness Club Pack", "Memberships, Wi-Fi and safety across every club",
      ["P02", "P01"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P22", "sites"), ("P19", "counters"), ("P23", "cams")], ["P15", "P10", "P13", "P18", "P14"],
      "Gyms run on memberships and renewals. Each club gets fibre with backup, member Wi-Fi, membership billing and CCTV, with WhatsApp renewal reminders as an easy add-on.",
      lps=0.5, data_types=("Gym chain",), labels={"P19": "Membership billing", "P22": "Member Wi-Fi", "P15": "WhatsApp renewal reminders"}),
    S("preschool", "pre-school or school chain", "multi", "Pre-School Pack", "Safe campuses and instant parent updates",
      ["P02", "P01"], ("P08", 0.0, 1, 12), [("P22", "sites"), ("P23", "cams"), ("P16", "seats")], ["P15", "P14", "P09", "P10", "P18"],
      "Parents want to know the campus is safe and to hear from the school quickly. This covers fibre, campus CCTV, Wi-Fi and admin email, with WhatsApp parent updates ready to add.",
      roles=(("Principals and admin", 0.15, 1),), lps=0.5, data_types=("Pre-school chain",),
      labels={"P23": "Classroom and gate CCTV for safety", "P15": "WhatsApp updates to parents", "P22": "Campus Wi-Fi"}),
    S("pharmacy_chain", "pharmacy chain", "multi", "Pharmacy Chain Pack", "Every counter billing, home delivery tracked",
      ["P01", "P02"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P19", "counters"), ("P23", "cams")], ["P25", "P15", "P10", "P17"],
      "A pharmacy chain needs every counter online and its delivery riders visible. Each outlet gets fibre with backup, billing and CCTV, with delivery tracking as a natural add-on.",
      lps=0.5, data_types=("Pharmacy chain",), labels={"P19": "Pharmacy billing and stock", "P25": "Home-delivery tracking"}),

    S("autoparts", "auto-parts unit", "mfg", "Auto-Parts Unit Pack", "Dedicated link for ERP and customer orders, safe shop floor",
      ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P21", "sites", ("P20", "devs")), ("P23", "cams4"), ("P11", "1")], ["P24", "P25", "P17", "P09"],
      "Auto-parts suppliers exchange orders and drawings with large customers every day. This gives a dedicated line with a fixed IP, managed security, shop-floor CCTV and office email.",
      roles=(("Management and accounts", 0.1, 1), ("Stores and dispatch", 0.1, 1), ("Supervisors", 0.05, 1)), data_types=("Auto-parts unit",),
      labels={"P11": "Fixed IP for customer ERP and EDI links", "P23": "Shop-floor and gate CCTV", "P21": "Managed firewall"}),
    S("textile", "textile unit", "mfg", "Textile Unit Pack", "Reliable link, protected network, watched premises",
      ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P21", "sites", ("P20", "devs")), ("P23", "cams4")], ["P25", "P24", "P17", "P09"],
      "Textile units coordinate buyers, designs and dispatch. This gives a dependable dedicated link, managed network security, office email and CCTV across the premises.",
      roles=(("Management and accounts", 0.1, 1), ("Merchandising and dispatch", 0.1, 1), ("Supervisors", 0.05, 1)), data_types=("Textile unit",),
      labels={"P23": "Premises and godown CCTV"}),
    S("factory", "small factory", "mfg", "Small Factory Pack", "A dependable link with security and monitoring for the floor",
      ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P21", "sites", ("P20", "devs")), ("P23", "cams4")], ["P24", "P25", "P17", "P09", "P11"],
      "A factory needs a dependable link, a protected network and cameras on the floor. This delivers all three with email for the office team, and machine monitoring as a next step.",
      roles=(("Management and accounts", 0.1, 1), ("Stores and dispatch", 0.1, 1), ("Supervisors", 0.05, 1)),
      data_types=("Furniture workshop", "Plastic moulding unit"), labels={"P23": "Shop-floor and gate CCTV"}),
    S("printing", "printing press", "mfg", "Print Shop Pack", "Heavy artwork files, safely backed up",
      ["P03", "P02", "P01"], ("P08", 0.1, 2, 6), [("P16", "seats"), ("P17", "1"), ("P20", "devs")], ["P09", "P18", "P23", "P25"],
      "Print shops send and receive large artwork files all day. This gives a fast gigabit or fibre link, backup for artwork, email for the office team and protected design machines.",
      roles=(("Management and accounts", 0.15, 1), ("Design and prepress", 0.2, 1)), data_types=("Printing press",), labels={"P17": "Artwork file backup"}),
    S("packaging", "packaging unit", "mfg", "Packaging Unit Pack", "Dedicated link with machine monitoring",
      ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P24", "devs4"), ("P23", "cams4")], ["P25", "P21", "P17", "P09"],
      "Packaging lines lose money when a machine stops unnoticed. This gives a dedicated link, machine monitoring, floor CCTV and office email.",
      roles=(("Management and accounts", 0.1, 1), ("Dispatch", 0.1, 1)), data_types=("Packaging unit",), labels={"P24": "Machine uptime monitoring"}),
    S("food_processing", "food processing unit", "mfg", "Food Processing Pack", "Dedicated link, delivery tracking, floor security",
      ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P25", "vehicles"), ("P23", "cams4")], ["P24", "P21", "P17", "P12"],
      "Food units need on-time deliveries and a watched premises. This provides a dependable link, vehicle tracking for dispatch, floor CCTV and office email.",
      roles=(("Management and accounts", 0.1, 1), ("Dispatch and stores", 0.1, 1)), data_types=("Food processing unit",), labels={"P25": "Dispatch vehicle tracking"}),
]}

GENERIC = {
    "micro": S("generic_micro", "business", "micro", "Starter Shop Pack", "Internet, business lines and billing",
               ["P01", "P04"], ("P07", 0.5, 2, 3), [("P19", "counters")], ["P23", "P15", "P22", "P18"],
               "For a small shop, reliable internet and billing come first. This pairs fibre with business mobile lines and cloud billing."),
    "prof": S("generic_prof", "office", "prof", "Office Essentials Pack", "Fast internet and email for your team",
              ["P02", "P01"], ("P07", 0.4, 2, 6), [("P16", "seats")], ["P17", "P09", "P20", "P12", "P22"],
              "For a professional office, uptime, business email and safe client data matter most. This gives fast fibre, email for your team and business mobile lines."),
    "multi": S("generic_multi", "multi-site business", "multi", "Multi-Location Pack", "Every location online with backup",
               ["P01", "P02"], ("P08", 0.0, 1, 12), [("P09", "sites"), ("P19", "counters")], ["P10", "P23", "P15", "P13"],
               "With several locations, one link going down should not stop the business. Each site gets its own fibre with automatic backup and cloud billing.", lps=0.5),
    "mfg": S("generic_mfg", "manufacturing unit", "mfg", "Factory Starter Pack", "A dependable link and email for the office",
             ["P05", "P03", "P02", "P01"], ("P08", 0.08, 3, 10), [("P16", "seats"), ("P21", "sites", ("P20", "devs"))], ["P23", "P24", "P25", "P17"],
             "A manufacturing unit needs a dependable link and protected systems. This gives dedicated bandwidth, security and email for the office team.",
             roles=(("Management and accounts", 0.1, 1), ("Stores and dispatch", 0.1, 1))),
}


def spec_for(business_type: str | None, segment: str | None) -> Spec:
    key = (business_type or "").strip().lower()
    if key in SPECS:
        return SPECS[key]
    return GENERIC.get(segment or "micro", GENERIC["micro"])


def role_seats(emp: int, roles: tuple) -> list[tuple[str, int]]:
    if not roles:
        return [("Staff", max(1, round(0.7 * emp)))]
    seats = [[label, max(mn, round(share * emp))] for label, share, mn in roles]
    while sum(n for _, n in seats) > max(1, emp):
        for row in reversed(seats):
            if row[1] > 0:
                row[1] -= 1
                break
    out = [(l, n) for l, n in seats if n > 0]
    return out or [(roles[0][0], 1)]
