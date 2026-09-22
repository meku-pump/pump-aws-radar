# pump-aws-radar

A fork of [aws-radar](https://github.com/gomorsmi/aws-radar) that adds a one-command **push** of
your AWS inventory and billing CSVs to Pump's self-serve onboarding endpoint — no standing
cross-account role required.

Everything upstream (`inventory`, `billing`, `diagram`, `run`) works unchanged. The only addition is
`run --upload-token`.

## Install

```bash
pip install pump-aws-radar
```

The console script is `pump-aws-radar`, so it installs alongside upstream `aws-radar` without
colliding.

## Pump onboarding

1. In the Pump app, mint an upload token (this calls `POST /api/v1/estimate/radar/mint`). Pump shows
   you a ready-to-paste command.
2. Run it against the AWS account you want to onboard:

   ```bash
   pump-aws-radar run --all-regions --tags --billing --upload-token <TOKEN>
   ```

   This inventories the account read-only, pulls Cost Explorer billing, and uploads both
   `inventory.csv` and `billing.csv` straight to Pump. No diagram is generated on this path.
3. Pump detects both files, runs its analysis, and surfaces the findings in the app.

### What leaves your machine

Only the two CSVs. The token carries no AWS credentials and no company id — Pump binds the company
and derives the S3 key server-side, so a token can only ever write its own upload's prefix. Each file
goes to S3 through a short-lived presigned `PUT` URL that Pump mints on demand.

### Pointing at a non-prod backend

The token exchange defaults to `https://api.pump.co`. Override it for local testing:

```bash
pump-aws-radar run --billing --upload-token <TOKEN> --api-base http://localhost:8001
# or
PUMP_API_BASE=http://localhost:8001 pump-aws-radar run --billing --upload-token <TOKEN>
```

## How the push works

`pump_aws_radar/upload.py`:

1. For each role (`inventory`, `billing`), `POST {api_base}/api/v1/estimate/radar/urls` with
   `{"token", "role"}` and receives a presigned S3 `PUT` URL.
2. `PUT`s the corresponding CSV with `Content-Type: text/csv` (the presigned URL signs the
   content-type, so it must match).

## Relationship to upstream

This is a derivative work of [aws-radar](https://github.com/gomorsmi/aws-radar), MIT-licensed, with
upstream copyright preserved in `LICENSE`. The scanning, billing, and diagram code is upstream's; the
Pump push is the fork's addition.
