# Deploying RNAF to AWS (Beginner-Friendly Guide)

This guide puts the app **on the internet** using the simple, low-cost setup from
the project plan: **one EC2 server + one RDS database + one S3 bucket**
(≈ $70–95/month). No load balancers, no Kubernetes, nothing fancy.

Written assuming you have **never deployed anything before**. Take it slowly —
each step is small. Expect it to take an afternoon the first time.

> **Words you'll see** (plain English):
> - **EC2** = a rented computer in the cloud. Our app runs here.
> - **RDS** = a managed PostgreSQL database (AWS looks after backups/patching).
> - **S3** = cloud file storage for photos/documents.
> - **Security Group** = a firewall — decides what traffic is allowed in.
> - **Elastic IP** = a permanent internet address for your server.

---

## Overview: what we'll build

```
        Internet
           │
        (ports 80/443)
           ▼
   ┌────────────────────────┐        ┌──────────────┐
   │   EC2 server (Ubuntu)  │──────▶ │  RDS Postgres │
   │  Docker Compose runs:  │        └──────────────┘
   │   • Nginx (+ HTTPS)    │
   │   • Flask API (Gunicorn)│──────▶ ┌──────────────┐
   │   • Redis + Celery     │        │   S3 bucket   │
   │   • React website      │        └──────────────┘
   └────────────────────────┘
```

---

## Part A — One-time AWS account setup

1. Create an AWS account at https://aws.amazon.com (needs a credit card; this
   setup stays well under $100/month).
2. In the top-right, pick a **Region** near your users (e.g. *Asia Pacific
   (Mumbai) ap-south-1*). **Use the same region for every step below.**
3. **Don't use your root login for daily work.** Search for **IAM** →
   *Users* → *Create user* → give it *AdministratorAccess* → sign in as that user
   from now on. (For a first deploy this is acceptable; tighten later.)

---

## Part B — Create the S3 bucket (file storage)

1. In the AWS console search bar, type **S3** → open it → **Create bucket**.
2. **Bucket name:** something globally unique, e.g. `rnaf-media-yourname`.
3. **Region:** same as everything else.
4. Leave *Block all public access* **ON** (our app uses secure temporary links,
   files are never public).
5. Click **Create bucket**. Note the exact bucket name — you'll need it later.

---

## Part C — Create the RDS PostgreSQL database

1. Console search → **RDS** → **Create database**.
2. Choose **Standard create**, engine **PostgreSQL**.
3. **Templates:** choose **Free tier** if offered, otherwise **Dev/Test**.
4. **DB instance identifier:** `rnaf-db`.
5. **Master username:** `rnaf` · **Master password:** make a strong one and
   **save it somewhere safe** (a password manager).
6. **Instance size:** `db.t4g.small` (or the smallest available).
7. **Storage:** 20 GB, gp3.
8. **Public access:** **No** (only our server will reach it).
9. **VPC:** leave the default.
10. Click **Create database**. It takes ~5–10 minutes to become *Available*.
11. When ready, click it and copy the **Endpoint** (looks like
    `rnaf-db.xxxx.ap-south-1.rds.amazonaws.com`). Save it.

We'll open the firewall between the server and this database in Part E.

---

## Part D — Launch the EC2 server

1. Console search → **EC2** → **Launch instance**.
2. **Name:** `rnaf-server`.
3. **OS Image (AMI):** **Ubuntu Server 24.04 LTS**.
4. **Instance type:** `t3.medium`.
5. **Key pair:** *Create new key pair* → name it `rnaf-key` → download the
   `.pem` file and keep it safe (this is how you log into the server).
6. **Network settings → Edit → Security group** — create a new one named
   `rnaf-web` and add these **inbound rules**:
   | Type | Port | Source | Why |
   |------|------|--------|-----|
   | SSH | 22 | *My IP* | So you can log in |
   | HTTP | 80 | Anywhere (0.0.0.0/0) | Website |
   | HTTPS | 443 | Anywhere (0.0.0.0/0) | Secure website |
7. **Storage:** 30 GB gp3.
8. Click **Launch instance**.

### Give it a permanent address (Elastic IP)
1. EC2 left menu → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**.
2. Select it → **Actions → Associate** → choose your `rnaf-server` → **Associate**.
3. Copy this IP — it's your server's permanent address.

---

## Part E — Let the server talk to the database

1. Go to **RDS** → your `rnaf-db` → **Connectivity & security** → click its
   **VPC security group**.
2. **Inbound rules → Edit → Add rule:**
   - Type: **PostgreSQL** (port 5432)
   - Source: start typing `rnaf-web` and select the EC2 security group.
3. **Save**. Now only your EC2 server can reach the database.

---

## Part F — Log into the server and install Docker

Open a terminal on your own computer. Go to where the `.pem` file is, then:

```bash
# Mac/Linux: lock down the key file (required once)
chmod 400 rnaf-key.pem

# Connect (replace with YOUR Elastic IP)
ssh -i rnaf-key.pem ubuntu@YOUR_ELASTIC_IP
```

> Windows users: use the same command in PowerShell, or use PuTTY.

Once you're logged into the server (the prompt changes to `ubuntu@...`), install
Docker:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker ubuntu      # lets you run docker without sudo
```

Log out and back in for that to take effect:

```bash
exit
ssh -i rnaf-key.pem ubuntu@YOUR_ELASTIC_IP
```

---

## Part G — Get the code and configure secrets

On the server:

```bash
git clone <your-repo-url> rnaf
cd rnaf
```

Create the production settings file `.env.prod` in the project root:

```bash
nano .env.prod
```

Paste this and fill in **your** values (RDS endpoint, RDS password, S3 bucket,
and long random secrets — you can generate secrets with
`python3 -c "import secrets; print(secrets.token_hex(32))"`):

```env
FLASK_ENV=production
SECRET_KEY=paste-a-long-random-string-here
JWT_SECRET_KEY=paste-a-different-long-random-string-here

# Database — use YOUR RDS endpoint and password
DATABASE_URL=postgresql+psycopg2://rnaf:YOUR_DB_PASSWORD@rnaf-db.xxxx.ap-south-1.rds.amazonaws.com:5432/rnaf

# Redis (runs inside Docker on this server)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# S3 — real bucket. Leave S3_ENDPOINT_URL blank so it uses real AWS S3.
S3_ENDPOINT_URL=
S3_BUCKET=rnaf-media-yourname
S3_REGION=ap-south-1
S3_ACCESS_KEY=your-iam-access-key
S3_SECRET_KEY=your-iam-secret-key

# Your domain (or the Elastic IP for now)
CORS_ORIGINS=https://yourdomain.com
```

Save in nano: **Ctrl+O**, **Enter**, then **Ctrl+X**.

> **About S3 keys:** the cleanest way is to attach an **IAM Role** to the EC2
> instance so no keys are needed. For a first deploy it's simpler to create an
> **IAM user** with *AmazonS3FullAccess*, generate an access key, and paste it
> above. You can switch to a role later with no code change.

> The `RDS…` database has no `rnaf` database inside it yet by default — RDS
> creates one only if you set an initial DB name. If your connection fails with
> "database rnaf does not exist", connect once and create it, or set the initial
> database name to `rnaf` when creating RDS. Easiest: in Part C step 4 expand
> *Additional configuration* and set **Initial database name = `rnaf`**.

---

## Part H — Start the app

Still on the server, in the `rnaf` folder:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The first build takes several minutes. Then create the database tables and (once)
the demo/admin data:

```bash
docker compose -f docker-compose.prod.yml exec backend flask db upgrade
docker compose -f docker-compose.prod.yml exec backend flask seed
```

Now open **http://YOUR_ELASTIC_IP** in your browser — the login page should
appear. 🎉 Log in with `sa@rnaf.demo` / `Password@123` and **immediately change
that password** from the app.

> **Security:** the seed creates demo accounts with a known password. For a real
> deployment, log in as Super Admin, create your real admin user, then delete the
> demo users.

---

## Part I — Add your domain name + HTTPS (padlock)

Skip if you only need the IP for now. To use `https://yourdomain.com`:

1. **Point the domain at the server.** In your domain registrar (GoDaddy,
   Namecheap, etc.) create an **A record** for `yourdomain.com` → **YOUR
   Elastic IP**. Wait a few minutes for it to take effect.

2. **Get a free HTTPS certificate** using Certbot. On the server:

```bash
# stop the web container briefly so Certbot can use port 80
docker compose -f docker-compose.prod.yml stop web

sudo apt install -y certbot
sudo certbot certonly --standalone -d yourdomain.com

# copy the certificate where our containers expect it
sudo mkdir -p certbot/conf
sudo cp -rL /etc/letsencrypt/* certbot/conf/
```

3. Tell Nginx to use HTTPS. Edit `frontend/nginx.conf` to add a TLS server block
   (a ready-to-use HTTPS example is in the comments at the bottom of that file's
   documentation, or ask your developer). At minimum, start the web container again:

```bash
docker compose -f docker-compose.prod.yml up -d web
```

4. Set `CORS_ORIGINS=https://yourdomain.com` in `.env.prod` and restart:
   `docker compose -f docker-compose.prod.yml up -d`.

> Certificates auto-expire every 90 days. Renew with `sudo certbot renew` (set up
> a monthly cron job to do it automatically).

---

## Part J — Keep it healthy (recommended, ~10 minutes)

These match the reliability plan (spec 7.11) and are mostly free:

1. **Auto-restart on crash** — already built in (`restart: unless-stopped` in the
   compose file). A crashed container restarts itself.

2. **Auto-recover the server** — EC2 → your instance → **Actions → Monitor and
   troubleshoot → Manage CloudWatch alarms → Create alarm** → enable *"Recover
   the instance"* on system-status-check failure.

3. **Free uptime monitor** — sign up at https://uptimerobot.com (free), add a
   monitor for `http://yourdomain.com/health`. It emails you if the site goes down.

4. **Database backups** — RDS already takes daily automated backups. Confirm under
   RDS → your DB → *Maintenance & backups* that the retention is 7 days.

---

## Updating the app later (new version)

On the server:

```bash
cd rnaf
git pull
docker compose -f docker-compose.prod.yml up -d --build

# apply any database changes the update brought with it (safe to re-run -
# it does nothing when there is nothing new):
docker compose -f docker-compose.prod.yml exec backend flask db upgrade
```

That rebuilds and restarts only what changed. If something breaks, you can roll
back with `git checkout <previous-version>` then the same `up -d --build`.

> **Note on database changes:** every schema change ships as a numbered
> **migration** in `backend/migrations/versions/`, and `flask db upgrade`
> applies whichever ones this database has not seen yet. It is safe to re-run:
> with nothing new, it does nothing. A test (`tests/test_migrations.py`) fails
> the build if a developer changes a model without writing the migration for
> it, so the two cannot drift apart.
>
> **Back up before upgrading** — `pg_dump` is in *Everyday server commands*
> below. A migration that drops or narrows a column loses whatever was in it,
> and `flask db downgrade` cannot bring the data back.
>
> **Upgrading a database that predates migrations** (its schema is current but
> it has no migration history): run `flask db stamp 0001_baseline` once to
> record where it stands, then `flask db upgrade` as normal.

---

## Everyday server commands

| Task | Command (run inside the `rnaf` folder on the server) |
|------|------|
| See running containers | `docker compose -f docker-compose.prod.yml ps` |
| View backend logs | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Restart everything | `docker compose -f docker-compose.prod.yml restart` |
| Stop everything | `docker compose -f docker-compose.prod.yml down` |

---

## Rough monthly cost

| Item | Approx |
|------|--------|
| EC2 `t3.medium` | ~$30 |
| RDS `db.t4g.small` | ~$25 |
| Storage + backups | ~$5 |
| S3 + data transfer | ~$5–15 |
| **Total** | **~$70–95 / month** |

Check the [AWS Pricing Calculator](https://calculator.aws) and your first bill to
confirm for your region and usage.

---

## Common problems

**Browser can't reach the site**
Check the EC2 **Security Group** allows ports 80/443 from *Anywhere*, and that the
`web` container is running (`docker compose ... ps`).

**Backend logs show "could not connect to database"**
Double-check `DATABASE_URL` in `.env.prod` (endpoint, password, and that the RDS
security group allows port 5432 from the EC2 security group — Part E).

**"database rnaf does not exist"**
Set the initial DB name to `rnaf` when creating RDS, or create it manually.

**Uploads fail**
Check the S3 bucket name/region and the IAM key in `.env.prod`, and that
`S3_ENDPOINT_URL` is **blank** in production (blank = real AWS S3).

**Ran out of disk / memory**
Resize the EC2 instance (EC2 → *Instance settings → Change instance type* →
`t3.large`) — a few minutes of downtime, no code changes.
