from os import environ


def pytest_sessionfinish(session, exitstatus):
    print()
    if exitstatus == 0:
        print("TEST OK.")
    else:
        print("FAILED")
    print()


def pytest_addoption(parser):
    parser.addoption(
        "--wave",
        action="store_true",
        default=False,
        help="Waveform dump",
    )
    parser.addoption(
        "--dprint",
        action="store_true",
        default=False,
        help="Enable debug prints",
    )
    parser.addoption(
        "--no-simbuild",
        action="store_true",
        default=False,
        help="Do not rebuild simulator",
    )
    parser.addoption(
        "--simarg",
        action="append",
        default=[],
        help="Simulator runtime arguments",
    )
    parser.addoption(
        "--sim",
        action="store",
        default="verilator",
        help="Simulator to use: verilator or questa",
    )
        
if "PYTEST_NO_FCOV" not in environ:
    pytest_plugins = ("tb.coco.pytest_fcov.plugin",)
