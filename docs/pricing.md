# Pricing

The numbers live in `studio/plans.py` and are **placeholders**: replace them
with your own costs before selling anything.

| Plan | Credits / month | Projects at once | Clips kept | Price |
|---|---|---|---|---|
| Free | 30 | 1 | 1 day | 0 |
| Starter | 300 | 2 | 14 days | $12 / 299,000 VND |
| Pro | 1,200 | 3 | 60 days | $39 / 999,000 VND |

Top-ups (never expire): 100 credits for $5 / 129,000 VND, 500 credits for $20 / 499,000 VND.

Features: every plan has clips, subtitles, hooks and thumbnails. Starter adds
dubbing, effects and publishing. Pro adds AI Shorts and API access.

## Setting a price

For each action, estimate what the server pays (Gemini tokens, fal.ai per video,
ElevenLabs minutes, compute), then choose a credit price so that
`credit price x credits >= API cost x (1 + margin)`. The AI Shorts cost on the UI
(0.8 to 2 USD per video) must be re-checked against the current fal.ai invoice.
Set `DAILY_AI_BUDGET_CREDITS` so one bad day has a bounded cost.
