# Getting Santo to the top of Google

No one can guarantee the #1 spot, and anyone who promises it is selling something. Rankings come from three things, in this order: **content that matches what people search**, **trust signals (links and reviews)**, and **a technically clean site**. The third is already built in. This guide covers the first two.

## Already built into the site
- `robots.txt` and `sitemap.xml` (automatic, include every page)
- A title, description, canonical link and social share image (`og-image.png`) on every page
- Structured data for Google: Organization, SoftwareApplication, FAQPage and breadcrumbs, which can earn rich results (FAQ dropdowns). Add prices to it when you launch plans
- **8 industry landing pages**, each aimed at one search phrase:
  `/for/restaurants`, `/for/online-stores`, `/for/clinics`, `/for/real-estate`, `/for/hr-helpdesk`, `/for/law-firms`, `/for/logistics`, `/for/software`
- Pages are server-rendered HTML, so Google reads them without running JavaScript
- Private pages (`/admin`, `/console`, `/api`) are hidden from Google
- Fast loading: self-hosted font, WebP images, no heavy frameworks, and mobile friendly

## Week 1: get indexed
1. **Google Search Console** (search.google.com/search-console): add `heysanto.ai` as a Domain property and verify it with the TXT record in Cloudflare DNS.
2. In Search Console > Sitemaps, submit `https://heysanto.ai/sitemap.xml`.
3. Use **URL Inspection > Request indexing** for the homepage and the 8 `/for/` pages.
4. Add the site to **Bing Webmaster Tools** (one click to import from Search Console). Bing results also power ChatGPT search and DuckDuckGo.
5. Test `https://heysanto.ai` and one `/for/` page in **PageSpeed Insights** and the **Rich Results Test**, and fix anything red.

## Weeks 2–4: trust signals (backlinks)
Google trusts sites that other sites link to. Start with these:
- **AI tool directories:** There's An AI For That, Futurepedia, Toolify, AI Tools Directory, TopAI.tools
- **Launch platforms:** Product Hunt (prepare a short demo GIF and launch on a Tuesday), BetaList, Indie Hackers, Hacker News "Show HN"
- **Software review sites:** G2, Capterra, GetApp, SaaSHub, AlternativeTo (list Santo as an alternative to Intercom Fin, Tidio and Chatbase)
- **Open source:** keep the GitHub repo public with a good README that links to heysanto.ai, and submit it to "awesome" lists for self-hosted AI and chatbots. Being keyless and open-source is a strong angle.
- **Your network:** LinkedIn posts and articles that link to the site, plus guest posts on small-business and restaurant blogs
- **Google Business Profile:** create one for Santo (service-area business, Dallas, TX). It helps local searches like "AI chatbot Dallas".

## Ongoing: content that ranks
Publish one helpful article a week. Target long, specific searches that small businesses type, where competition is lower:
| Article idea | Search phrase it targets |
|---|---|
| How to add an AI chatbot to your Shopify store (free) | add ai chatbot to shopify free |
| AI receptionist for dental offices: what it can and can't do | ai receptionist dental office |
| Free self-hosted alternative to Intercom Fin | intercom fin alternative free |
| How restaurants can take bookings 24/7 without hiring | restaurant online booking assistant |
| Run your own AI chatbot without an OpenAI key | ai chatbot without api key |
| ChatGPT vs a custom AI assistant for your business | custom ai assistant for business |

Rules for each article: one main search phrase, used in the title, the URL and the first paragraph. Answer the question in the first 2–3 sentences. Include a real screenshot. Link to the matching `/for/` page and to `/builder`. Write it yourself or edit AI drafts heavily, because Google rewards first-hand experience.

## What to watch monthly (Search Console > Performance)
- **Queries:** which searches show your site. Write more about the ones close to page 1 (positions 8–20).
- **Click-through rate:** if a page is seen but not clicked, rewrite its title to be more specific and appealing.
- **Pages:** make sure all 9 key pages show as "Indexed".

## Realistic timeline
New domains usually take **3–6 months** to rank for competitive terms. Long, specific phrases ("AI intake chatbot for law firms") can rank within weeks once indexed. Directories and Product Hunt bring visitors immediately while SEO builds.
