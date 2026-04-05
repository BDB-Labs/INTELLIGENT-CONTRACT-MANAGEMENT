# Deployment Checklist

This checklist is the shortest path from the current repository to a live
public demo on Vercel and a live reference implementation on Render.

## Vercel demo

Target:

- public
- read-only
- sanitized

Root directory:

- `demo_site/`

Files used:

- [`demo_site/index.html`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/demo_site/index.html)
- [`demo_site/vercel.json`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/demo_site/vercel.json)
- [`demo_site/generated/manifest.json`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/demo_site/generated/manifest.json)

Steps:

1. Create a new Vercel project from this repository.
2. Set the project root to `demo_site/`.
3. Do not point Vercel at the repository root.
4. Deploy.
5. Attach the intended public demo domain, such as `demo.<your-domain>`.
6. Verify:
   - the landing page loads
   - the three demo cases render
   - each dashboard opens correctly

Refresh procedure:

```bash
python3 -m uv run python -m apps.contract_intelligence build-demo
```

## Render reference implementation

Target:

- real Python runtime
- sample cases bootstrapped on first start
- optional protection with Basic Auth

Files used:

- [`render.yaml`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/render.yaml)
- [`scripts/start_icm_reference.sh`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/scripts/start_icm_reference.sh)
- [`apps/contract_intelligence/api/app.py`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/apps/contract_intelligence/api/app.py)

Steps:

1. Create a new Render Blueprint from this repository.
   Do not create a Static Site for ICM. If Render shows an error like
   `Publish directory render.yaml does not exist!`, the service type is wrong.
2. Confirm the disk mount is present at `/var/data/icm`.
3. Deploy the `icm-reference` web service.
4. Set a stable internal or semi-private hostname, such as `internal.<your-domain>` or `icm.<your-domain>`.
5. Optional but recommended: add these environment variables manually in Render:
   - `ICM_REFERENCE_AUTH_USER`
   - `ICM_REFERENCE_AUTH_PASSWORD`
6. Verify:
   - `/health` returns `{"status":"ok"}`
   - `/` loads the reference landing page
   - `/reference/manifest` responds
   - `/reference/cases/<case_id>/dashboard` opens a dashboard

## Smoke test order

1. Vercel demo
2. Render health endpoint
3. Render landing page
4. Render reference manifest
5. One Render dashboard

## Post-deploy follow-up

After both surfaces are live:

1. decide whether the Render instance stays public or moves behind auth immediately
2. point the Vercel landing page and Render landing page at each other where appropriate
3. decide whether the next step is:
   - richer demo polish
   - upload flow
   - auth and access control
   - storage refactor
