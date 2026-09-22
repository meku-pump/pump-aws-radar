"""
Entry point for:
    python -m pump_aws_radar
    pump-aws-radar      (after pip install)

This is a fork of gomorsmi/aws-radar. The only functional addition is the
`run --upload-token` path, which pushes the inventory and billing CSVs to Pump's
self-serve onboarding endpoint (see pump_aws_radar.upload).
"""

import argparse
import os
import sys

# Mirrors pump_aws_radar.billing.METRICS. Duplicated here so `--help` works without
# boto3 installed — importing billing pulls in boto3 at module scope.
# tests/test_pump_aws_radar.py keeps the two lists in sync.
METRICS = [
    "UnblendedCost", "AmortizedCost", "BlendedCost",
    "NetUnblendedCost", "NetAmortizedCost", "UsageQuantity",
]

# Where the Pump backend lives. Overridable for local testing via --api-base or
# the PUMP_API_BASE env var (e.g. http://localhost:8001).
DEFAULT_API_BASE = os.environ.get("PUMP_API_BASE", "https://api.pump.co")


def main():
    parser = argparse.ArgumentParser(
        prog="pump-aws-radar",
        description="AWS resource inventory & draw.io architecture diagram generator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── inventory sub-command ──
    inv = sub.add_parser("inventory", help="Scan AWS account and list all resources")
    inv.add_argument("--region",      default=None,  help="AWS region (default: boto3 default)")
    inv.add_argument("--profile",     default=None,  help="AWS SSO/named profile")
    inv.add_argument("--role-arn",    default=None,  help="IAM role ARN to assume")
    inv.add_argument("--all-regions", action="store_true", help="Scan all enabled regions")
    inv.add_argument("--ai", action=argparse.BooleanOptionalAction, default=True,
                     help="Scan AI/ML services (Bedrock, SageMaker, Rekognition, Lex, Kendra, …). On by default; pass --no-ai to skip them")
    inv.add_argument("--tags",        action="store_true", help="Fetch resource tags and add a 'Tags' column")
    inv.add_argument("--tags-wide",   action="store_true", help="Also write a CSV with one column per tag key (implies --tags)")
    inv.add_argument("--cost-allocation-tags", action="store_true", help="Add a 'CostAllocTags' column with billing-activated tags (implies --tags)")
    inv.add_argument("--include-aws-tags", action="store_true", help="Include aws:-prefixed system tags (excluded by default)")
    inv.add_argument("--billing",     action="store_true", help="Also pull Cost Explorer daily cost by service and write a CSV")
    inv.add_argument("--billing-days", type=int, default=None, help="Billing window in days (default: 90)")
    inv.add_argument("--billing-metric", default=None, choices=METRICS, help="Cost Explorer metric (default: UnblendedCost)")
    inv.add_argument("--billing-output", metavar="FILE.csv", default=None, help="Billing CSV path (default: billing.csv)")
    inv.add_argument("--include-zero", action="store_true", help="Keep zero-cost service/day buckets in the billing CSV")
    inv.add_argument("--export",      metavar="FILE.csv", help="Export results to CSV")

    # ── billing sub-command ──
    bil = sub.add_parser("billing", help="Pull Cost Explorer daily cost by service to CSV")
    bil.add_argument("--profile", default=None, help="AWS SSO/named profile")
    bil.add_argument("--days",    type=int, default=90, help="Trailing window in days (default: 90)")
    bil.add_argument("--metric",  default="UnblendedCost", choices=METRICS, help="Cost Explorer metric (default: UnblendedCost)")
    bil.add_argument("--include-zero", action="store_true", help="Keep service/day buckets with zero cost")
    bil.add_argument("--output",  metavar="FILE.csv", default="billing.csv", help="CSV output path (default: billing.csv)")

    # ── diagram sub-command ──
    dia = sub.add_parser("diagram", help="Generate draw.io diagram from inventory CSV")
    dia.add_argument("--input",  required=True,          help="CSV produced by 'inventory'")
    dia.add_argument("--output", default="architecture.drawio", help="Output .drawio file")

    # ── all-in-one sub-command ──
    run = sub.add_parser("run", help="Inventory + diagram in one shot (or push CSVs to Pump)")
    run.add_argument("--region",      default=None)
    run.add_argument("--profile",     default=None)
    run.add_argument("--role-arn",    default=None)
    run.add_argument("--all-regions", action="store_true")
    run.add_argument("--ai", action=argparse.BooleanOptionalAction, default=True,
                     help="Scan AI/ML services (on by default; --no-ai to skip)")
    run.add_argument("--tags",   action="store_true", help="Fetch resource tags and add a 'Tags' column")
    run.add_argument("--tags-wide", action="store_true", help="Also write a CSV with one column per tag key (implies --tags)")
    run.add_argument("--cost-allocation-tags", action="store_true", help="Add a 'CostAllocTags' column with billing-activated tags (implies --tags)")
    run.add_argument("--include-aws-tags", action="store_true", help="Include aws:-prefixed system tags (excluded by default)")
    run.add_argument("--billing", action="store_true", help="Also pull Cost Explorer daily cost by service and write a CSV")
    run.add_argument("--billing-days", type=int, default=None, help="Billing window in days (default: 90)")
    run.add_argument("--billing-metric", default=None, choices=METRICS, help="Cost Explorer metric (default: UnblendedCost)")
    run.add_argument("--billing-output", metavar="FILE.csv", default=None, help="Billing CSV path (default: billing.csv)")
    run.add_argument("--include-zero", action="store_true", help="Keep zero-cost service/day buckets in the billing CSV")
    run.add_argument("--csv",    default="inventory.csv",      help="Intermediate CSV path")
    run.add_argument("--output", default="architecture.drawio", help="Output .drawio file")
    # ── Pump onboarding push (fork addition) ──
    run.add_argument("--upload-token", default=None,
                     help="Pump upload token: push the inventory + billing CSVs to Pump instead of drawing a diagram")
    run.add_argument("--api-base", default=DEFAULT_API_BASE,
                     help=f"Pump API base for --upload-token (default: {DEFAULT_API_BASE}; or set PUMP_API_BASE)")
    run.add_argument("--no-diagram", dest="diagram", action="store_false", default=True,
                     help="Skip the draw.io diagram (by default 'run' always draws it, even when uploading)")

    args = parser.parse_args()

    if args.command == "inventory":
        from pump_aws_radar.inventory import main as inv_main
        sys.argv = _rebuild_argv("inventory", args)
        inv_main()

    elif args.command == "billing":
        from pump_aws_radar.billing import main as bil_main
        sys.argv = _rebuild_argv("billing", args)
        bil_main()

    elif args.command == "diagram":
        from pump_aws_radar.drawio import main as dia_main
        sys.argv = _rebuild_argv("diagram", args)
        dia_main()

    elif args.command == "run":
        _run(args)


def _run(args):
    from pump_aws_radar.inventory import main as inv_main

    uploading = bool(args.upload_token)
    # The Pump flow needs both CSVs: the backend only starts analysis once
    # inventory.csv and billing.csv are both present.
    if uploading and not args.billing:
        sys.exit(
            "Error: --upload-token requires --billing so both CSVs are produced.\n"
            "Run: pump-aws-radar run --all-regions --tags --billing --upload-token <TOKEN>"
        )

    drawing = args.diagram
    total = 1 + (1 if uploading else 0) + (1 if drawing else 0)
    step = 1
    # Step 1 — inventory (and billing, when --billing is set)
    print(f"── Step {step}/{total}: Running inventory ──")
    inv_args = ["pump-aws-radar"]
    if args.profile:     inv_args += ["--profile", args.profile]
    if args.role_arn:    inv_args += ["--role-arn", args.role_arn]
    if args.region:      inv_args += ["--region", args.region]
    if args.all_regions: inv_args += ["--all-regions"]
    # Ternary, not `if args.ai:` — a bare if would emit nothing for --no-ai
    # and let inventory.py's own default (True) decide instead.
    inv_args += ["--ai"] if args.ai else ["--no-ai"]
    if args.tags:                 inv_args += ["--tags"]
    if args.tags_wide:            inv_args += ["--tags-wide"]
    if args.cost_allocation_tags: inv_args += ["--cost-allocation-tags"]
    if args.include_aws_tags:     inv_args += ["--include-aws-tags"]
    if args.billing:              inv_args += ["--billing"]
    if args.billing_days is not None:   inv_args += ["--billing-days", str(args.billing_days)]
    if args.billing_metric:             inv_args += ["--billing-metric", args.billing_metric]
    if args.billing_output:             inv_args += ["--billing-output", args.billing_output]
    if args.include_zero:               inv_args += ["--include-zero"]
    inv_args += ["--export", args.csv]
    sys.argv = inv_args
    inv_main()

    if uploading:
        # Push both CSVs to Pump
        from pump_aws_radar.upload import UploadError, upload_csvs

        step += 1
        billing_csv = args.billing_output or "billing.csv"
        print(f"\n── Step {step}/{total}: Uploading to Pump ({args.api_base}) ──")
        try:
            upload_csvs(
                api_base=args.api_base,
                token=args.upload_token,
                files={"inventory": args.csv, "billing": billing_csv},
            )
        except UploadError as e:
            sys.exit(f"\nUpload failed: {e}")
        print("  ✓ Your inventory and billing data are on their way to Pump.")

    if drawing:
        # Draw the diagram. Runs on both paths — upload and non-upload — so a
        # single `run` can push to Pump and still leave a local .drawio.
        from pump_aws_radar.drawio import main as dia_main

        step += 1
        print(f"\n── Step {step}/{total}: Generating diagram ──")
        sys.argv = ["pump-aws-radar", "--input", args.csv, "--output", args.output]
        dia_main()
        print(f"  ✓ Open {args.output} at https://app.diagrams.net/")

    print("\n✓ Done!")


# Dests whose False value is meaningful and so must be forwarded explicitly.
# inventory.py re-parses this argv with its own parser and its own defaults, so
# a flag omitted here is decided by that parser, not by the user. That is only
# correct for plain store_true flags, which default to False on both sides.
NEGATABLE = {"inventory": {"ai"}, "run": {"ai"}}


def _rebuild_argv(cmd, args):
    argv = ["pump-aws-radar"]
    negatable = NEGATABLE.get(cmd, frozenset())
    d = vars(args)
    for k, v in d.items():
        if k == "command":
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                argv.append(flag)
            elif k in negatable:
                argv.append("--no-" + k.replace("_", "-"))
        elif v is not None:
            argv += [flag, str(v)]
    return argv


if __name__ == "__main__":
    main()
