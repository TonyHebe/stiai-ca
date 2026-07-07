# Deploy on GitHub + cron-job.org

Your project lives on GitHub. **GitHub stores the code** — it does not run it by itself.
To run it automatically in the cloud, use **GitHub Actions** (already configured).

You have **two ways** to trigger posts:

---

## Option A — Built-in schedule (easiest, no cron-job.org)

The workflow `.github/workflows/post.yml` already runs **3 times per day**:

| UTC time | Romania time |
|---|---|
| 06:00 | 09:00 |
| 10:00 | 13:00 |
| 16:00 | 19:00 |

Each run adds a **random 0–60 min delay** before posting.

**You only need to add secrets** (see below). No cron-job.org required.

---

## Option B — cron-job.org triggers GitHub

Yes, this works. cron-job.org calls the **GitHub API**, which starts the workflow.

### 1. Create a GitHub Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)**
3. Scope: check **`repo`** (full control of private repositories)
4. Copy the token (`ghp_...`)

### 2. Create a cron job on [cron-job.org](https://cron-job.org)

Create **3 jobs** (morning, afternoon, evening):

| Field | Value |
|---|---|
| **URL** | `https://api.github.com/repos/TonyHebe/stiai-ca/dispatches` |
| **Method** | `POST` |
| **Schedule** | 09:00 / 13:00 / 19:00 (your timezone) |

**Headers:**

```
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_TOKEN
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

**Body:**

```json
{"event_type": "cron-post"}
```

> If you use Option B, disable the `schedule:` block in `post.yml` to avoid double-posting.

---

## Required GitHub Secrets

Go to **github.com/TonyHebe/stiai-ca → Settings → Secrets and variables → Actions → New repository secret**

Add these 3 secrets:

| Secret name | Value |
|---|---|
| `FACEBOOK_PAGE_ID` | `1177328168801239` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | your permanent page token from `.env` |
| `OPENAI_API_KEY` | your OpenAI key from `.env` |

---

## Test manually

1. Go to [github.com/TonyHebe/stiai-ca/actions](https://github.com/TonyHebe/stiai-ca/actions)
2. Click **Stiai Ca Auto-Poster**
3. Click **Run workflow** → **Run workflow**

Check your Facebook page — a new post should appear within ~2 minutes (or up to 60 min if random delay kicks in).

---

## How it works

```
cron-job.org (optional)  ──►  GitHub API  ──►  GitHub Actions
        or
GitHub built-in cron     ──►  GitHub Actions
                                    │
                                    ▼
                              runs main.py
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              GPT writes      AI generates      Posts to
              curiosity         image          Facebook
                    │
                    ▼
         Saves state back to GitHub (curiosities.json)
```

Your PC can be **off**. Everything runs in the cloud for free.
