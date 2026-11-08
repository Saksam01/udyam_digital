from udyam import advisor


def test_one_sentence_fills_several_answers():
    p = advisor.keyword_profile("I have a 2-doctor clinic in Jaipur and need fast Wi-Fi and WhatsApp reminders")
    assert p["business_type"] == "clinic"
    assert p["employees"] == 2
    assert p["city"] == "Jaipur"
    assert {"internet", "whatsapp"} <= set(p["need_tags"])


def test_sites_and_staff_are_told_apart():
    p = advisor.keyword_profile("restaurant chain with 5 outlets in Mumbai, around 60 staff, want CCTV and billing")
    assert (p["num_sites"], p["employees"]) == (5, 60)
    assert {"cctv", "billing"} <= set(p["need_tags"])


def test_no_gst_and_city_alias():
    p = advisor.keyword_profile("kirana in Bangalore, 3 log, no GST yet")
    assert p["city"] == "Bengaluru"
    assert p["gstin_status"] == "none"


def test_understand_works_without_the_language_model(monkeypatch):
    monkeypatch.setattr(advisor.llm, "parse_profile", lambda *a, **k: None)
    u = advisor.understand("salon with 6 staff in Pune, we have GST", "en")
    assert u["business_type"] == "salon" and u["segment"] == "micro"
    assert u["employees"] == 6 and u["city"] == "Pune" and u["gstin_status"] == "active"
