# HuggingFace Spaces Keepalive

GitHub Actions workflow that keeps **every** Hugging Face Space owned by `Faruna01` awake.

## How it works

Every 4 hours the workflow:

1. Lists all Spaces for the user through the Hugging Face API, so new Spaces are picked up automatically.
2. Checks each Space's status. If one is **sleeping**, it restarts it through the API.
3. Sends a request to each Space's `*.hf.space` URL to register activity.
4. Re-enables itself via the GitHub API, so GitHub never turns the schedule off for "60 days of inactivity" (that's what broke the previous version).

A run **fails** (and GitHub emails you) if a Space can't be woken or is in an error state (build/runtime error), so you know something needs fixing.

## One-time setup (required)

1. Create a Hugging Face token with **Write** access: https://huggingface.co/settings/tokens
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `HF_TOKEN`
   - Value: the token
3. Go to **Actions → Keep HuggingFace Spaces Alive → Run workflow** to test it.

Without `HF_TOKEN` the workflow can only ping; it cannot wake Spaces that are already asleep.

## Optional settings (Actions → Variables)

| Variable       | Purpose                                                   |
|----------------|-----------------------------------------------------------|
| `HF_USERNAME`  | Different HF user/org (default `Faruna01`)                |
| `EXTRA_SPACES` | Comma-separated extra Space ids, e.g. `org/space-name`    |
| `SKIP_SPACES`  | Comma-separated Space ids to leave alone                  |
| `KEEP_SPACES`  | Only these Spaces are woken (default: igala-streamlit-app-02, igala-nmt-translator, lsr-dashboard, persona-collapse). Free accounts can only run ~4 CPU Spaces at once. |

## Local run

```bash
pip install -r requirements.txt
HF_TOKEN=hf_xxx python keepalive.py
```

## License

MIT
