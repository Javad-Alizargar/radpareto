# Optional RadPareto web interface

The interface is designed for `https://statwhy.com/Smith/`. The URL is an intended deployment location; deployment status must be verified separately. The Python comparison and stability engines remain the authoritative implementation.

## Local use

From a repository checkout with Python 3.11 or newer:

```sh
python web/app.py --port 8766
```

Open `http://127.0.0.1:8766/Smith/`. This local preview uses the standard-library WSGI development server. For Linux production use the pinned optional Gunicorn dependency in `requirements-web.txt` behind Nginx; the scientific package itself has no additional dependency.

## What the interface contributes

- Exposes source-attributed resource costs and timing ranges without needing a local Python environment.
- Lets a researcher compare mean-only screening with interval-based decisions under explicit budgets.
- Offers named candidate subsets while retaining the distinction between cost and protection comparisons.
- Exports input records, source digest, settings, software version/revision, decisions and optional exact stability boundaries as JSON.
- Accepts up to 128 compatible custom records in a JSON object with `records` and optional minimized-objective `limits`. Invalid or incompatible evidence is refused by the same engine used by the CLI.

These are implemented capabilities, not measured evidence of researcher adoption, usability improvement, radiation performance or time savings.

## Five reproducible checks

1. Open the page. The default 40 VersaTiles/bit and 32 MHz case has five definitely feasible records and one uncertain record. DF-TMR-DFF-5.12 passes the mean-only clock screen while its reported range crosses 32 MHz.
2. Change the requirement to 30 MHz, keeping the cap at 40. All six reported ranges satisfy the limits. Change the cap to 20 to see resource-limited exclusions.
3. Select **Require declared protection equivalence**. The example must be refused; cost data do not establish protection comparability.
4. Restore the example and export analysis. Check the input/source digest, software version/revision and individual feasibility reasons. Compute optional boundaries, then export again to retain them.
5. Upload `benchmarks/published_case/results/records.json` as custom input. With no objective limits it produces an unconstrained comparison; specify a `limits` object to add budgets. Changing one record's device should produce a context-mismatch refusal.

HTTP checks:

```sh
curl https://statwhy.com/Smith/health
curl -H 'Content-Type: application/json' \
  --data '{"cells_cap":40,"frequency_mhz":32}' \
  https://statwhy.com/Smith/api/analyze
```

## Data and interpretation

The bundled example adapts numerical Tables 9 and 10 from Ma et al., *Electronics* 2026, 15(22), 5390, https://doi.org/10.3390/electronics15225390, licensed CC BY 4.0. The original numerical transcription, source metadata, exact decimal strings and checksums are in `benchmarks/published_case/`. RadPareto code is MIT. The publication PDF is not hosted by this interface.

The ranges summarize three reported implementation runs; individual runs and source HDL were not obtained. They are not confidence intervals or future-run guarantees. Timing costs use the reciprocal of mean maximum frequency and reversed reciprocal range endpoints. Resource caps and clock requirements are analyst-selected scenarios. Generic cost comparisons cannot establish radiation superiority or mission qualification. Smith's name in the URL does not imply his participation or endorsement.

## Data handling and exposure

The app does not save submitted records. It processes JSON in memory and returns results. The app does not log JSON bodies; the operator should preserve that policy in reverse-proxy/access-log configuration. Standard request metadata may be logged. The body limit is 512 KiB, record limit 128, and all static/download paths use an explicit allowlist. There is no remote URL fetch, file-write, shell-execution or arbitrary file-download endpoint. Scientific validation and security request-boundary checks are in `tests/test_web.py`.

## Deployment shape

`web/deploy/` supplies a dedicated dynamic-user systemd service on loopback port 8766 and an isolated case-sensitive Nginx `/Smith` location snippet. Configure the immutable release path through `/opt/radpareto-smith/current`, set `RADPARETO_SOURCE_REVISION` in `/opt/radpareto-smith/service.env`, retain a prior release for rollback, and verify Nginx before reloading. Only the reviewed public repository belongs on the server. Manuscripts, publication figures, copied literature, private audits, authoring files and credentials must stay outside the public runtime.

Deployment references: [Gunicorn deployment guide](https://gunicorn.org/deploy/) and [settings](https://gunicorn.org/reference/settings/). The controller should preserve the existing main-site configuration before adding one include line, record deployed hashes/revision and verify the main homepage/login after deployment.
