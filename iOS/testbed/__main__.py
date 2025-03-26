import argparse
import asyncio
import json
import plistlib
import re
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path


DECODE_ARGS = ("UTF-8", "backslashreplace")

# The system log prefixes each line:
#   2025-01-17 16:14:29.090 Df iOSTestbed[23987:1fd393b4] (Python) ...
#   2025-01-17 16:14:29.090 E  iOSTestbed[23987:1fd393b4] (Python) ...

LOG_PREFIX_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # YYYY-MM-DD
    r"\s+\d+:\d{2}:\d{2}\.\d+"  # HH:MM:SS.sss
    r"\s+\w+"  # Df/E
    r"\s+iOSTestbed\[\d+:\w+\]"  # Process/thread ID
    r"\s+\(Python\)\s"  # Logger name
)


# Work around a bug involving sys.exit and TaskGroups
# (https://github.com/python/cpython/issues/101515).
def exit(*args):
    raise MySystemExit(*args)


class MySystemExit(Exception):
    pass


# All subprocesses are executed through this context manager so that no matter
# what happens, they can always be cancelled from another task, and they will
# always be cleaned up on exit.
@asynccontextmanager
async def async_process(*args, **kwargs):
    process = await asyncio.create_subprocess_exec(*args, **kwargs)
    try:
        yield process
    finally:
        if process.returncode is None:
            # Allow a reasonably long time for Xcode to clean itself up,
            # because we don't want stale emulators left behind.
            timeout = 10
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout)
            except TimeoutError:
                print(
                    f"Command {args} did not terminate after {timeout} seconds "
                    f" - sending SIGKILL"
                )
                process.kill()

                # Even after killing the process we must still wait for it,
                # otherwise we'll get the warning "Exception ignored in __del__".
                await asyncio.wait_for(process.wait(), timeout=1)


async def async_check_output(*args, **kwargs):
    async with async_process(
        *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    ) as process:
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return stdout.decode(*DECODE_ARGS)
        else:
            raise subprocess.CalledProcessError(
                process.returncode,
                args,
                stdout.decode(*DECODE_ARGS),
                stderr.decode(*DECODE_ARGS),
            )


# Return a list of UDIDs associated with booted simulators
async def list_devices():
    # List the testing simulators, in JSON format
    raw_json = await async_check_output(
        "xcrun", "simctl", "--set", "testing", "list", "-j"
    )
    json_data = json.loads(raw_json)

    # Filter out the booted iOS simulators
    return [
        simulator["udid"]
        for runtime, simulators in json_data["devices"].items()
        for simulator in simulators
        if runtime.split(".")[-1].startswith("iOS") and simulator["state"] == "Booted"
    ]


async def find_device(initial_devices):
    while True:
        new_devices = set(await list_devices()).difference(initial_devices)
        if len(new_devices) == 0:
            await asyncio.sleep(1)
        elif len(new_devices) == 1:
            udid = new_devices.pop()
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S}: New test simulator detected")
            print(f"UDID: {udid}")
            return udid
        else:
            exit(f"Found more than one new device: {new_devices}")


async def log_stream_task(initial_devices):
    # Wait up to 5 minutes for the build to complete and the simulator to boot.
    udid = await asyncio.wait_for(find_device(initial_devices), 5 * 60)

    # Stream the iOS device's logs, filtering out messages that come from the
    # XCTest test suite (catching NSLog messages from the test method), or
    # Python itself (catching stdout/stderr content routed to the system log
    # with config->use_system_logger).
    args = [
        "xcrun",
        "simctl",
        "--set",
        "testing",
        "spawn",
        udid,
        "log",
        "stream",
        "--style",
        "compact",
        "--predicate",
        (
            'senderImagePath ENDSWITH "/iOSTestbedTests.xctest/iOSTestbedTests"'
            ' OR senderImagePath ENDSWITH "/Python.framework/Python"'
        ),
    ]

    async with async_process(
        *args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as process:
        suppress_dupes = False
        while line := (await process.stdout.readline()).decode(*DECODE_ARGS):
            # Strip the prefix from each log line
            line = LOG_PREFIX_REGEX.sub("", line)
            # The iOS log streamer can sometimes lag; when it does, it outputs
            # a warning about messages being dropped... often multiple times.
            # Only print the first of these duplicated warnings.
            if line.startswith("=== Messages dropped "):
                if not suppress_dupes:
                    suppress_dupes = True
                    sys.stdout.write(line)
            else:
                suppress_dupes = False
                sys.stdout.write(line)
            sys.stdout.flush()


async def xcode_test(location, simulator, verbose):
    # Run the test suite on the named simulator
    print("Starting xcodebuild...")
    args = [
        "xcodebuild",
        "test",
        "-project",
        str(location / "iOSTestbed.xcodeproj"),
        "-scheme",
        "iOSTestbed",
        "-destination",
        f"platform=iOS Simulator,name={simulator}",
        "-resultBundlePath",
        str(location / f"{datetime.now():%Y%m%d-%H%M%S}.xcresult"),
        "-derivedDataPath",
        str(location / "DerivedData"),
    ]
    if not verbose:
        args += ["-quiet"]

    async with async_process(
        *args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as process:
        while line := (await process.stdout.readline()).decode(*DECODE_ARGS):
            sys.stdout.write(line)
            sys.stdout.flush()

        status = await asyncio.wait_for(process.wait(), timeout=1)
        exit(status)


def clone_testbed(
    source: Path,
    target: Path,
    framework: Path,
    apps: list[Path],
) -> None:
    if target.exists():
        print(f"{target} already exists; aborting without creating project.")
        sys.exit(10)

    if framework is None:
        if not (
            source / "Python.xcframework/ios-arm64_x86_64-simulator/bin"
        ).is_dir():
            print(
                f"The testbed being cloned ({source}) does not contain "
                f"a simulator framework. Re-run with --framework"
            )
            sys.exit(11)
    else:
        if not framework.is_dir():
            print(f"{framework} does not exist.")
            sys.exit(12)
        elif not (
            framework.suffix == ".xcframework"
            or (framework / "Python.framework").is_dir()
        ):
            print(
                f"{framework} is not an XCframework, "
                f"or a simulator slice of a framework build."
            )
            sys.exit(13)

    print("Cloning testbed project:")
    print(f"  Cloning {source}...", end="", flush=True)
    shutil.copytree(source, target, symlinks=True)
    print(" done")

    if framework is not None:
        if framework.suffix == ".xcframework":
            print("  Installing XCFramework...", end="", flush=True)
            xc_framework_path = (target / "Python.xcframework").resolve()
            if xc_framework_path.is_dir():
                shutil.rmtree(xc_framework_path)
            else:
                xc_framework_path.unlink()
            xc_framework_path.symlink_to(
                framework.relative_to(xc_framework_path.parent, walk_up=True)
            )
            print(" done")
        else:
            print("  Installing simulator framework...", end="", flush=True)
            sim_framework_path = (
                target / "Python.xcframework" / "ios-arm64_x86_64-simulator"
            ).resolve()
            if sim_framework_path.is_dir():
                shutil.rmtree(sim_framework_path)
            else:
                sim_framework_path.unlink()
            sim_framework_path.symlink_to(
                framework.relative_to(sim_framework_path.parent, walk_up=True)
            )
            print(" done")
    else:
        print("  Using pre-existing iOS framework.")

    for app_src in apps:
        print(f"  Installing app {app_src.name!r}...", end="", flush=True)
        app_target = target / f"iOSTestbed/app/{app_src.name}"
        if app_target.is_dir():
            shutil.rmtree(app_target)
        shutil.copytree(app_src, app_target)
        print(" done")

    print(f"Successfully cloned testbed: {target.resolve()}")


def update_plist(testbed_path, args):
    # Add the test runner arguments to the testbed's Info.plist file.
    info_plist = testbed_path / "iOSTestbed" / "iOSTestbed-Info.plist"
    with info_plist.open("rb") as f:
        info = plistlib.load(f)

    info["TestArgs"] = args

    with info_plist.open("wb") as f:
        plistlib.dump(info, f)


async def run_testbed(simulator: str, args: list[str], verbose: bool=False):
    location = Path(__file__).parent
    print("Updating plist...", end="", flush=True)
    update_plist(location, args)
    print(" done.")

    # Get the list of devices that are booted at the start of the test run.
    # The simulator started by the test suite will be detected as the new
    # entry that appears on the device list.
    initial_devices = await list_devices()

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(log_stream_task(initial_devices))
            tg.create_task(xcode_test(location, simulator=simulator, verbose=verbose))
    except* MySystemExit as e:
        raise SystemExit(*e.exceptions[0].args) from None
    except* subprocess.CalledProcessError as e:
        # Extract it from the ExceptionGroup so it can be handled by `main`.
        raise e.exceptions[0]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Manages the process of testing a Python project in the iOS simulator."
        ),
    )

    subcommands = parser.add_subparsers(dest="subcommand")

    clone = subcommands.add_parser(
        "clone",
        description=(
            "Clone the testbed project, copying in an iOS Python framework and"
            "any specified application code."
        ),
        help="Clone a testbed project to a new location.",
    )
    clone.add_argument(
        "--framework",
        help=(
            "The location of the XCFramework (or simulator-only slice of an "
            "XCFramework) to use when running the testbed"
        ),
    )
    clone.add_argument(
        "--app",
        dest="apps",
        action="append",
        default=[],
        help="The location of any code to include in the testbed project",
    )
    clone.add_argument(
        "location",
        help="The path where the testbed will be cloned.",
    )

    run = subcommands.add_parser(
        "run",
        usage="%(prog)s [-h] [--simulator SIMULATOR] -- <test arg> [<test arg> ...]",
        description=(
            "Run a testbed project. The arguments provided after `--` will be "
            "passed to the running iOS process as if they were arguments to "
            "`python -m`."
        ),
        help="Run a testbed project",
    )
    run.add_argument(
        "--simulator",
        default="iPhone SE (3rd Generation)",
        help="The name of the simulator to use (default: 'iPhone SE (3rd Generation)')",
    )
    run.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    try:
        pos = sys.argv.index("--")
        testbed_args = sys.argv[1:pos]
        test_args = sys.argv[pos + 1 :]
    except ValueError:
        testbed_args = sys.argv[1:]
        test_args = []

    context = parser.parse_args(testbed_args)

    if context.subcommand == "clone":
        clone_testbed(
            source=Path(__file__).parent,
            target=Path(context.location),
            framework=Path(context.framework).resolve() if context.framework else None,
            apps=[Path(app) for app in context.apps],
        )
    elif context.subcommand == "run":
        if test_args:
            if not (
                Path(__file__).parent / "Python.xcframework/ios-arm64_x86_64-simulator/bin"
            ).is_dir():
                print(
                    f"Testbed does not contain a compiled iOS framework. Use "
                    f"`python {sys.argv[0]} clone ...` to create a runnable "
                    f"clone of this testbed."
                )
                sys.exit(20)

            asyncio.run(
                run_testbed(
                    simulator=context.simulator,
                    verbose=context.verbose,
                    args=test_args,
                )
            )
        else:
            print(f"Must specify test arguments (e.g., {sys.argv[0]} run -- test)")
            print()
            parser.print_help(sys.stderr)
            sys.exit(21)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
