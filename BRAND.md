# Santo brand kit

## Name and idea
**Santo** is the brand and the name of the AI agent itself. The name comes from SANThOsh, the founder's name, without using it directly. Santosh also means contentment, which suits an agent whose job is to leave customers satisfied.

The visual idea is weaving: your FAQs, policies and business systems are the threads, and Santo is the cloth they make, one agent that answers on every channel.

Tagline: *Meet Santo, the AI agent woven from everything your business knows.*

Santo speaks in the first person as the product ("Hi, I'm Santo"). It greets visitors on the homepage (`agents/santo.yaml`, knowledge in `knowledge/santo/`).

## Domain
Suggested domains, in order of preference:

| Domain | Why |
|---|---|
| **heysanto.ai** | "Hey Santo" is how people will talk to the agent. Used in the site copy now |
| santo.ai | Shortest, but likely taken or sold at a premium price. Worth checking |
| getsanto.com | A good `.com` backup that builds trust with small-business buyers |
| santoagent.com | Clear and likely to be available |

I couldn't check availability from here. Check at a registrar (Cloudflare Registrar, Namecheap, Porkbun) and run a trademark search (USPTO for the US) before you commit. A small agency called Santos Labs also builds AI agents for businesses. Its name is different, but keep it in mind. If you pick a different domain, replace `heysanto.ai` in `static/index.html`, `agents/santo.yaml` and `knowledge/santo/product.md`.

**Connecting the domain:** point the domain's DNS at your host (on Render or Fly.io, add the custom domain in the dashboard and create the CNAME record they show you). Then set `CORS_ORIGINS=https://heysanto.ai`.

## Logo
| File | Use |
|---|---|
| `static/img/logo.svg` | Primary logo on light backgrounds |
| `static/img/logo-light.svg` | Logo on indigo or dark backgrounds |
| `static/img/mark.svg` | The woven mark on its own (avatars, app icons) |
| `static/img/favicon.svg` | Browser tab icon |

The mark is a real plain weave: three indigo warp threads crossed by madder, saffron and woad weft threads, each passing over, then under. The wordmark is Archivo at 125% width and weight 760, converted to outlines so it renders identically everywhere. To regenerate it:
```bash
pip install fonttools brotli
python scripts/make_logo.py static/fonts/archivo-var.woff2 static/img
```
The wordmark is "santo", always lowercase in the logo. In text, write Santo.

Keep clear space around the logo equal to the mark's height. Never recolour individual threads or stretch the logo.

## Colour: Indigo Pro
| Name | Hex | Use |
|---|---|---|
| Indigo | `#4F46E5` | Primary buttons, links, the brand colour |
| Violet | `#7C3AED` | Gradient middle |
| Cyan | `#06B6D4` | Gradient end, highlights |
| Night | `#1E1B4B` | Dark sections |
| Ink | `#0F172A` | Text, footer |
| Mist | `#F8F9FF` | Soft section backgrounds |

Signature gradient: `linear-gradient(135deg, #4F46E5, #7C3AED 55%, #06B6D4)`, used on icon tiles, the "24/7" highlight and the final call-to-action card.

Two other ready-made themes are in `static/css/themes/` (`saffron.css`, `emerald.css`). To switch, replace the "Active theme" block at the end of `static/css/site.css` with the contents of one of those files.

## Type
**Plus Jakarta Sans** (SIL Open Font License), self-hosted in `static/fonts/`. Headlines use weight 800 with tight letter-spacing, and body text uses weight 400. The logo wordmark uses Archivo Expanded, converted to outlines.

## Images
The homepage uses real screenshots of the product (`static/img/screens/`), a live chat demo inside a phone frame, and a matching line-icon set drawn inline. To refresh the screenshots after changing the product, take new ones of `/builder`, `/console` and `/admin`, and save them as WebP at 1600px wide.

## Voice
Friendly, plain and benefit-first, written for business owners rather than developers. Developer details live in the API docs.

Plain, specific, owner-to-owner. Name what the customer gets, not how the system works ("answers on your website", not "omnichannel deployment"). Use sentence case everywhere and button labels that say exactly what happens ("Publish agent", "Request my demo agent").
