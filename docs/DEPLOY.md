# Deploying Santo

Santo runs anywhere Docker runs. The AI model needs about 4 GB of RAM for the default `qwen2.5:3b` model (8 GB or more for 7B/8B models). On hosting without enough memory, Santo uses its built-in engine automatically.

| Option | Cost | AI model | Guide |
|---|---|---|---|
| **Oracle Cloud Always Free** (Arm, 2 OCPUs, 12 GB) | Free | Yes | [Any Ubuntu server](#any-ubuntu-server-oracle-aws-godaddy-vps-hetzner) |
| **AWS EC2** (`t4g.large`, 8 GB) | Paid (sign-up credits apply) | Yes | [AWS notes](#aws-ec2) |
| **GoDaddy VPS** (8 GB+) | Paid | Yes | [Any Ubuntu server](#any-ubuntu-server-oracle-aws-godaddy-vps-hetzner) |
| **Hetzner / DigitalOcean / Vultr** (8 GB) | Low-cost | Yes | [Any Ubuntu server](#any-ubuntu-server-oracle-aws-godaddy-vps-hetzner) |
| **GoDaddy Web Hosting (cPanel)** | Paid | No, built-in engine | [cPanel](#godaddy-web-hosting-cpanel) |
| GitHub Pages | Free | Not supported | Static files only, and GitHub doesn't allow business sites |

---

## Any Ubuntu server (Oracle, AWS, GoDaddy VPS, Hetzner)

**1. Open ports 80 and 443** in your provider's firewall or security group. Allow SSH (22) only from your IP.
On Oracle Cloud you also need to open them on the server:
```bash
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

**2. Install Docker and get the code**
```bash
curl -fsSL https://get.docker.com | sudo sh
git clone git@github.com:santhosh-dataops/santo.git && cd santo
```
For a private repo, first create a key on the server (`ssh-keygen -t ed25519`, then `cat ~/.ssh/id_ed25519.pub`). Add it under **Repo > Settings > Deploy keys**.

**3. Configure and start**
```bash
cp .env.example .env
nano .env    # API_KEYS=<long password>  SITE_URL=https://heysanto.ai  CORS_ORIGINS=https://heysanto.ai,https://www.heysanto.ai
sudo docker compose up -d
curl localhost:8000/health    # wait a few minutes for the model; expect "ai_engine": "ollama"
```

**4. Point your domain** at the server: create `A` records for `@` and `www` with the server's IP. In GoDaddy, edit the "Parked" `@` record. In Cloudflare, set the records to "DNS only".

**5. HTTPS with Caddy** (free, auto-renewing certificates):
```bash
sudo apt install -y caddy
echo 'heysanto.ai, www.heysanto.ai {
  reverse_proxy localhost:8000
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

**6. Auto-deploy from GitHub.** Go to **Repo > Settings > Secrets and variables > Actions** and add:
| Secret | Value |
|---|---|
| `SERVER_HOST` | Server IP (Elastic IP on AWS) |
| `SERVER_USER` | `ubuntu` (Oracle, AWS) or `root` (GoDaddy VPS) |
| `SERVER_SSH_KEY` | Your private SSH key (for AWS, the contents of the `.pem` file) |

Every push to `main` now runs the tests (`.github/workflows/ci.yml`). If they pass, it runs `git pull && docker compose up -d --build` on the server (`.github/workflows/deploy.yml`).

---

## AWS EC2
- Choose the **Paid plan** at sign-up. Sign-up credits still apply, and Free-plan accounts close after 6 months or when the credits run out.
- **Instance:** Ubuntu Server 24.04 LTS **Arm**, `t4g.large` (8 GB), 30 GB gp3 disk. For a lower cost, use `t4g.medium` (4 GB) with `OLLAMA_MODEL=qwen2.5:1.5b`.
- **Security group:** SSH from My IP, HTTP and HTTPS from Anywhere.
- Allocate an **Elastic IP** and associate it with the instance. Use it for DNS and `SERVER_HOST`.
- **Login:** `chmod 400 santo-key.pem && ssh -i santo-key.pem ubuntu@<elastic-ip>`, then follow the Ubuntu steps above.
- **Backups:** EC2 > Lifecycle Manager > daily snapshot policy, keeping 7 days. Also set a monthly AWS Budget alert.

---

## GoDaddy Web Hosting (cPanel)
Shared hosting can't run Docker or an AI model. Santo runs with its **built-in engine**: answers from your documents, general facts via Wikipedia/DuckDuckGo, math, dates, bookings and leads. Your plan needs "Setup Python App" with **Python 3.10+**.

1. **Get the code:** cPanel > **Git Version Control** > Create. Clone `https://github.com/santhosh-dataops/santo.git` into `santo`, or upload and extract the zip with File Manager.
2. **Create the app:** cPanel > **Setup Python App** > Create Application. Use Python 3.10+, root `santo`, URL `/`, startup file `passenger_wsgi.py`, entry point `application`.
3. **Configure:** add environment variables `API_KEYS`, `SITE_URL` and `CORS_ORIGINS`. Click **Run Pip Install** with `requirements.txt`, then **Restart**.
4. **HTTPS:** cPanel > **SSL/TLS Status** > Run AutoSSL.
5. **Updates:** Git Version Control > Manage > **Update from Remote**, then Setup Python App > **Restart**.

---

## After launch
- Submit `https://heysanto.ai/sitemap.xml` in Google Search Console. See [SEO.md](../SEO.md).
- Back up `data/` (database), `agents/` and `knowledge/`.
- Logs: `sudo docker compose logs -f santo`
- Update: `git pull && sudo docker compose up -d --build`, or just push to GitHub if auto-deploy is set up.
