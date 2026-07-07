# cron-job.org Setup — 7 posts/day, random timing

Create **7 separate cron jobs** on [cron-job.org](https://cron-job.org).

Each job fires at an **irregular base time** (~every 3 hours).  
Then GitHub Actions adds a **random 8–42 minute delay** before posting.

**Result:** posts land at unpredictable times like `10:51`, `14:17`, `21:03` — never sharp on the hour.

---

## Settings (same for all 7 jobs)

| Field | Value |
|---|---|
| **URL** | `https://api.github.com/repos/TonyHebe/stiai-ca/dispatches` |
| **Method** | `POST` |

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

## The 7 schedules (Romania time, Europe/Bucharest)

Use **irregular minutes** on purpose — avoids bot-like patterns.

| Job name | Base trigger time | Actual post window |
|---|---|---|
| StiaiCa_1 | **07:17** daily | 07:25 – 07:59 |
| StiaiCa_2 | **10:38** daily | 10:46 – 11:20 |
| StiaiCa_3 | **13:52** daily | 14:00 – 14:34 |
| StiaiCa_4 | **17:23** daily | 17:31 – 18:05 |
| StiaiCa_5 | **20:41** daily | 20:49 – 21:23 |
| StiaiCa_6 | **23:58** daily | 00:06 – 00:40 |
| StiaiCa_7 | **03:14** daily | 03:22 – 03:56 |

> Times in the right column are approximate (base + 8–42 min random delay).

---

## Cost estimate (7 posts/day)

| Item | ~Monthly |
|---|---|
| OpenAI images + text | **$14–18** |
| cron-job.org | Free (7 jobs) |
| GitHub Actions | Free |
| Facebook | Free |
| **Total** | **~$15–18/month** |

---

## Test

1. Create one job, click **Execute now**
2. Check [github.com/TonyHebe/stiai-ca/actions](https://github.com/TonyHebe/stiai-ca/actions) — workflow should start
3. Post appears on Facebook after the random delay (8–42 min)

---

## Prerequisites

Make sure these **GitHub Secrets** are set:

- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `OPENAI_API_KEY`

See `GITHUB_SETUP.md` for details.
