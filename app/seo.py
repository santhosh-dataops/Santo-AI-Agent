"""SEO: robots.txt, sitemap.xml and server-rendered industry landing pages (/for/<slug>).

Each landing page targets one search phrase (e.g. "AI chatbot for restaurants") and is plain HTML,
so Google can read it without running JavaScript.
"""
from __future__ import annotations

import html
import json
import os
from datetime import date

SITE_URL = os.getenv("SITE_URL", "https://heysanto.ai").rstrip("/")
BRAND = "Santo"

INDUSTRIES: dict[str, dict] = {
    "restaurants": {
        "template": "restaurant", "noun": "restaurants and cafés", "keyword": "AI chatbot for restaurants",
        "title": "AI Chatbot for Restaurants: Answer Questions and Take Bookings 24/7",
        "h1": "An AI assistant that answers your guests and books tables, day and night",
        "intro": "Santo answers menu, hours, parking and allergen questions on your restaurant website and collects table bookings, so your staff can focus on the guests in front of them.",
        "tasks": ["Shares your menu, prices and daily specials", "Answers allergen and dietary questions from your own notes", "Collects table bookings with name, party size, date and phone", "Sends large parties and private events to your events contact"],
        "questions": ["What time do you open on Sunday?", "Do you have vegan options?", "Can I book a table for 6 on Friday at 7pm?"],
        "faq": [("Can the AI take restaurant reservations?", "Yes. Santo collects the guest's name, party size, date, time and phone number, confirms them back, and sends the booking to your reservation tool or email."),
                ("Will it give wrong allergen information?", "Santo only answers from the allergen notes you provide. If something isn't covered, it tells the guest to check with your staff.")],
    },
    "online-stores": {
        "template": "retail", "noun": "online stores", "keyword": "AI customer service chatbot for ecommerce",
        "title": "AI Customer Service Chatbot for Online Stores | Shopify, WooCommerce and More",
        "h1": "Answer every shopper's question instantly, without growing your support team",
        "intro": "Santo handles the shipping, returns, sizing and order status questions that fill your inbox, right on your store, at any hour.",
        "tasks": ["Explains shipping times, costs and countries", "Walks customers through returns and exchanges", "Looks up order status from your order system", "Hands refunds outside your policy to a person"],
        "questions": ["How long does shipping take?", "What is your return policy?", "Where is my order A-10023?"],
        "faq": [("Does it work with Shopify?", "Yes. Add one line of code to your theme and the chat appears on every page of your Shopify store. It works the same way on WooCommerce, Wix and other platforms."),
                ("Can it check order status?", "Yes. Connect your order system's web address and Santo looks up orders when a customer gives their order number.")],
    },
    "clinics": {
        "template": "clinic", "noun": "clinics and dental offices", "keyword": "AI receptionist for clinics",
        "title": "AI Receptionist for Clinics and Dental Offices: 24/7 Patient Questions",
        "h1": "A front desk assistant that answers patients after hours",
        "intro": "Santo answers questions about your services, insurance accepted, hours and visit preparation, and collects appointment requests. It never gives medical advice.",
        "tasks": ["Explains services and prices", "Lists the insurance plans you accept", "Shares preparation steps before visits", "Collects appointment requests for your staff to confirm"],
        "questions": ["Do you accept Delta Dental?", "How much is a cleaning without insurance?", "Can I request an appointment next week?"],
        "faq": [("Does the AI give medical advice?", "No. Santo is set up to answer only administrative questions from your own information. Anything medical goes to your staff, and emergencies get your phone number."),
                ("Can it book appointments?", "It collects the patient's details and preferred times and sends them to your team or scheduling tool to confirm.")],
    },
    "real-estate": {
        "template": "realty", "noun": "real estate agents and brokerages", "keyword": "AI chatbot for real estate",
        "title": "AI Chatbot for Real Estate Agents: Qualify Buyers and Book Viewings",
        "h1": "Turn listing visitors into qualified buyers while you're out showing homes",
        "intro": "Santo answers listing questions, asks buyers about budget, area and timing, and books viewings, so every lead arrives ready for a conversation.",
        "tasks": ["Answers questions about your listings", "Qualifies buyers by budget, area and timeline", "Books viewings and open house visits", "Sends hot leads to your phone or CRM"],
        "questions": ["What homes do you have under $400k?", "Is 12 Oak Lane still available?", "Can I see it on Saturday?"],
        "faq": [("Can it qualify leads?", "Yes. Santo asks about budget, preferred areas, timeline and financing, then passes a summary to you."),
                ("Does it connect to my CRM?", "Santo can send leads to any CRM or tool with a web address, including through Zapier.")],
    },
    "hr-helpdesk": {
        "template": "hr", "noun": "HR and IT teams", "keyword": "AI HR helpdesk chatbot",
        "title": "AI HR and IT Helpdesk Chatbot: Instant Answers for Employees",
        "h1": "Answer employee questions about leave, pay and passwords in seconds",
        "intro": "Santo answers routine HR and IT questions from your handbook and policies, so your team spends less time repeating the same answers.",
        "tasks": ["Explains leave, payroll and benefits policies", "Guides password resets and access requests", "Names the exact policy behind each answer", "Keeps sensitive cases with your HR team"],
        "questions": ["How many PTO days do I get?", "When is payday?", "How do I reset my password?"],
        "faq": [("Is employee information kept private?", "Santo answers from your policies, not personal records. Sensitive cases are directed to your HR team."),
                ("Can it be private to employees only?", "Yes. Internal assistants can require a key so only your staff can use them.")],
    },
    "law-firms": {
        "template": "legal", "noun": "law firms", "keyword": "AI intake chatbot for law firms",
        "title": "AI Client Intake Chatbot for Law Firms: Capture Cases 24/7",
        "h1": "Capture new client inquiries at any hour, without giving legal advice",
        "intro": "Santo explains your practice areas and fees, collects case details for intake, and books consultations, so no potential client goes to another firm overnight.",
        "tasks": ["Explains practice areas and consultation fees", "Collects contact details and a case summary", "Books consultations with your attorneys", "Never gives legal advice"],
        "questions": ["Do you handle tenant disputes?", "How much is a consultation?", "Can I book a call this week?"],
        "faq": [("Will the chatbot give legal advice?", "No. Santo is set up to explain your services and collect intake details only. An attorney reviews every case."),
                ("Where do intake details go?", "To your email, case management system or CRM, whichever you connect.")],
    },
    "logistics": {
        "template": "logistics", "noun": "logistics and freight companies", "keyword": "AI chatbot for logistics",
        "title": "AI Chatbot for Logistics and Freight: Shipment Tracking and Quotes",
        "h1": "Give shippers instant tracking updates and answers, around the clock",
        "intro": "Santo tracks shipments by reference number, explains standard rates and opens damage claims, reducing calls and emails to your customer desk.",
        "tasks": ["Tracks shipments by reference number", "Explains standard rates and service areas", "Opens damage claims with the right details", "Routes custom quotes to your sales team"],
        "questions": ["Where is shipment TW-4471?", "How do I file a damage claim?", "Do you ship to Canada?"],
        "faq": [("Can it connect to our tracking system?", "Yes. Connect your tracking system's web address and Santo looks up shipments live."),
                ("Can it give custom quotes?", "Santo quotes standard rates from your rate sheet and sends custom requests to your sales team.")],
    },
    "software": {
        "template": "saas", "noun": "software and SaaS companies", "keyword": "AI support chatbot for SaaS",
        "title": "AI Support Chatbot for SaaS: Answer How-To Questions from Your Docs",
        "h1": "Answer product questions from your docs before they become tickets",
        "intro": "Santo answers how-to questions with step-by-step help from your documentation, checks account details and files clear bug reports.",
        "tasks": ["Answers how-to questions from your docs", "Gives numbered step-by-step instructions", "Checks account and plan details", "Files bug reports with steps to reproduce"],
        "questions": ["How do I export invoices?", "Can I add another user?", "The export button isn't working"],
        "faq": [("Can it learn from our documentation?", "Yes. Paste or upload your help articles and Santo answers from them."),
                ("Does it replace our help desk?", "It works alongside it. Santo answers routine questions and passes complex ones to your team.")],
    },
}

PAGES = ["/", "/builder"] + [f"/for/{s}" for s in INDUSTRIES]


def robots_txt() -> str:
    return (f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /console\nDisallow: /api/\nDisallow: /mcp\n\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n")


def sitemap_xml() -> str:
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{SITE_URL}{p}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{'weekly' if p == '/' else 'monthly'}</changefreq>"
        f"<priority>{'1.0' if p == '/' else '0.8'}</priority></url>" for p in PAGES)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


def industry_page(slug: str) -> str | None:
    d = INDUSTRIES.get(slug)
    if not d:
        return None
    e = html.escape
    url = f"{SITE_URL}/for/{slug}"
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in d["faq"]]}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": BRAND, "item": SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": f"For {d['noun']}", "item": url}]}
    others = "".join(f'<li><a href="/for/{s}">AI assistant for {e(o["noun"])}</a></li>' for s, o in INDUSTRIES.items() if s != slug)
    tasks = "".join(f'<li><svg class="ico" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>{e(t)}</li>' for t in d["tasks"])
    qs = "".join(f'<div class="q">{e(q)}</div>' for q in d["questions"])
    faq = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in d["faq"])
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(d['title'])} | {BRAND}</title>
<meta name="description" content="{e(d['intro'])}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(d['title'])}"><meta property="og:description" content="{e(d['intro'])}">
<meta property="og:url" content="{url}"><meta property="og:type" content="website"><meta property="og:site_name" content="{BRAND}">
<meta property="og:image" content="{SITE_URL}/static/img/og-image.png"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#4F46E5">
<link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/static/css/site.css">
<script type="application/ld+json">{json.dumps(faq_ld)}</script>
<script type="application/ld+json">{json.dumps(crumbs)}</script>
<style>
 body{{background:#fff}} .ico{{width:20px;height:20px;fill:none;stroke:#16A34A;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round;flex:none;margin-top:3px}}
 .lp-hero{{background:radial-gradient(36rem 24rem at 85% 10%,rgba(124,58,237,.14),transparent 60%),#F8F9FF;padding:64px 0 72px}}
 .lp-hero .wrap{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr);gap:48px;align-items:center}}
 .crumbs{{font-size:var(--t-sm);color:var(--muted);margin-bottom:18px}} .crumbs a{{color:var(--muted)}}
 .lp-hero h1{{font-size:clamp(2.2rem,4.4vw,3.4rem);margin-bottom:18px}} .lp-hero .lede{{margin-bottom:28px}}
 .chatcard{{background:#fff;border-radius:20px;padding:20px;box-shadow:0 24px 60px -24px rgba(30,27,75,.35)}}
 .chatcard b{{display:block;margin-bottom:12px}} .q{{background:#4F46E5;color:#fff;border-radius:14px 14px 4px 14px;padding:9px 13px;margin:0 0 8px auto;width:fit-content;max-width:90%;font-size:var(--t-sm)}}
 .lp ul.tasks{{list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:14px 28px;margin:24px 0 0}} .lp ul.tasks li{{display:flex;gap:10px}}
 .lp h2{{font-size:clamp(1.6rem,3vw,2.2rem);margin-bottom:12px}} .lp section{{padding:56px 0;border-top:1px solid var(--line)}}
 .lp details{{border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin-bottom:10px}} .lp summary{{font-weight:700;cursor:pointer}} .lp details p{{margin:10px 0 0;color:var(--muted)}}
 .others{{columns:2;padding-left:18px}} .cta{{background:linear-gradient(135deg,#4F46E5,#7C3AED 55%,#06B6D4);color:#fff;border-radius:24px;padding:40px;text-align:center}}
 .cta h2{{color:#fff}} .cta .btn{{background:#fff;color:#4338CA;margin-top:10px}}
 @media(max-width:860px){{.lp-hero .wrap{{grid-template-columns:minmax(0,1fr)}} .lp ul.tasks{{grid-template-columns:1fr}} .others{{columns:1}}}}
</style></head>
<body>
<nav class="nav" aria-label="Main"><div class="wrap">
 <a class="brand" href="/"><img src="/static/img/logo.svg" alt="Santo" width="115" height="30"></a>
 <ul><li><a href="/#features">Features</a></li><li><a href="/#how">How it works</a></li><li><a href="/#faq">FAQ</a></li></ul>
 <div class="actions"><a class="btn btn-primary" href="/builder?template={d['template']}">Get started</a></div>
</div></nav>
<main class="lp">
 <div class="lp-hero"><div class="wrap">
  <div>
   <p class="crumbs"><a href="/">Santo</a> / For {e(d['noun'])}</p>
   <h1 class="display">{e(d['h1'])}</h1>
   <p class="lede">{e(d['intro'])}</p>
   <a class="btn btn-primary" href="/builder?template={d['template']}">Create your assistant</a>
  </div>
  <div class="chatcard" aria-label="Example questions"><b>Questions Santo answers for {e(d['noun'])}</b>{qs}</div>
 </div></div>
 <div class="wrap">
  <section><h2 class="display">What Santo does for {e(d['noun'])}</h2><ul class="tasks">{tasks}</ul></section>
  <section><h2 class="display">Set up in minutes, no coding</h2>
   <p>Start from the ready-made template for {e(d['noun'])}, paste in your own information, test the answers, then add one line of code to your website. Santo works on Shopify, WordPress, Wix, Squarespace and custom sites.</p></section>
  <section><h2 class="display">Frequently asked questions</h2>{faq}</section>
  <section><h2 class="display">Santo for other industries</h2><ul class="others">{others}</ul></section>
  <section style="border:0"><div class="cta"><h2 class="display">Try Santo for your business</h2><p>No coding and no AI key needed. Live on your website today.</p>
   <a class="btn" href="/builder?template={d['template']}">Create your assistant</a></div></section>
 </div>
</main>
<footer class="footer"><div class="wrap">
 <div><img src="/static/img/logo-light.svg" alt="Santo" width="107" height="28"><p style="max-width:34ch">The AI assistant that answers your customers 24/7.</p></div>
 <div><h3>Industries</h3><ul>{"".join(f'<li><a href="/for/{s}">{e(o["noun"].capitalize())}</a></li>' for s, o in list(INDUSTRIES.items())[:4])}</ul></div>
 <div><h3>More</h3><ul>{"".join(f'<li><a href="/for/{s}">{e(o["noun"].capitalize())}</a></li>' for s, o in list(INDUSTRIES.items())[4:])}</ul></div>
 <div><h3>Company</h3><ul><li><a href="/#start">Contact us</a></li><li><a href="/#how">How it works</a></li></ul></div>
 <p class="legal">© 2026 Santo. heysanto.ai</p>
</div></footer>
</body></html>"""
