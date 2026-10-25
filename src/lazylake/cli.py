"""Command-line entry point: `lazylake [--profile X] [--region Y] [--demo]`."""

from __future__ import annotations

import argparse

from lazylake import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lazylake",
        description="The terminal browser for your AWS data pipelines.",
    )
    parser.add_argument("--profile", "-p", help="AWS profile (~/.aws/config). Default: AWS_PROFILE.")
    parser.add_argument("--region", "-r", help="AWS region. Default: the profile's region.")
    parser.add_argument("--demo", action="store_true", help="Fake data, no AWS account needed.")
    parser.add_argument("--version", action="version", version=f"lazylake {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.demo:
        from lazylake.providers.demo import DemoGlueProvider

        provider = DemoGlueProvider()
    else:
        from lazylake.providers.aws import AwsGlueProvider

        provider = AwsGlueProvider(profile=args.profile, region=args.region)

    from lazylake.app import LazylakeApp

    LazylakeApp(provider).run()


if __name__ == "__main__":
    main()
