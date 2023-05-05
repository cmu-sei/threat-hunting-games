# Configuration file for pytest usage
def pytest_addoption(parser):
    parser.addoption("--local",
                     action="store_true",
                     default=False,
                     help="Run Tests against GHOSTS api hosted on https://localhost instead of https://ghosts-api")
    parser.addoption("--test",
                     action="store_true",
                     default=False,
                     help="Used for running unit tests, does not save simulation file or GHOSTS environment")

#def pytest_runtest_logreport(report):
#    if report.when == 'call' and report.failed:
        # If a test case has failed and a report is being created
