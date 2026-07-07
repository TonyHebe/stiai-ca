# cron-job.org Setup — 1 cron job, 7 posts/day

You only need **ONE cron job**. It fires every ~3 hours, and the script:
1. Waits a **random 8–42 minutes** before posting
2. Checks if **7 posts already went out today** — if yes, skips
3. Otherwise posts one curiosity

---

## Create ONE job on [cron-job.org](https://cron-job.org)

### COMMON tab

| Field | Value |
|---|---|
| **Title** | `StiaiCa` |
| **URL** | `https://api.github.com/repos/TonyHebe/stiai-ca/dispatches` |
| **Enable job** | ON |

**Schedule → Custom → Crontab:**

```
37 */3 * * *
```

This fires **8 times per day** at irregular `:37` minutes:
`00:37, 03:37, 06:37, 09:37, 12:37, 15:37, 18:37, 21:37`

The script caps at **7 posts/day**, so one run naturally skips.

Actual post times = trigger + **8–42 min random** → e.g. `10:04`, `13:21`, `19:58`

### ADVANCED tab

| Field | Value |
|---|---|
| **Request method** | `POST` |

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

---

## How it works

```
ONE cron (every 3h at :37)
    → GitHub Actions starts
    → sleeps 8-42 min randomly
    → checks: posted 7 times today?
        YES → skip
        NO  → generate + post 1 curiosity
```

---

## Cost: ~$15–18/month

7 posts/day × 30 days = 210 AI images/month.

---

## Test

Click **Execute now** on your cron job, then check:
[github.com/TonyHebe/stiai-ca/actions](https://github.com/TonyHebe/stiai-ca/actions)

Post appears after the random delay (8–42 min).
