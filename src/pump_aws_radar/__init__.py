"""
pump-aws-radar — a fork of aws-radar (gomorsmi/aws-radar) that adds a one-command
push of the inventory + billing CSVs to Pump's self-serve onboarding endpoint.

Upstream scans an AWS account read-only and writes a CSV inventory, a Cost Explorer
billing CSV, and a draw.io diagram. This fork adds `run --upload-token`, which sends
the two CSVs to Pump instead of drawing a diagram (see pump_aws_radar.upload).

Quick start (Pump onboarding):
    pump-aws-radar run --all-regions --tags --billing --upload-token <TOKEN>
"""

__version__ = "1.1.0"
__author__ = "Pump (fork of aws-radar by Mor Michaeli)"
