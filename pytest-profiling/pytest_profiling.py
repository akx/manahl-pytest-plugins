from __future__ import absolute_import

import pytest
import os
import cProfile
import pstats
import pipes


def clean_filename(s):
    forbidden_chars = set('/?<>\:*|"')
    return "".join(
        c if c not in forbidden_chars and ord(c) < 127 else '_'
        for c in s
    )


class Profiling(object):
    """Profiling plugin for pytest."""

    def __init__(self, svg, combined_only):
        self.svg = bool(svg)
        self.combined_only = bool(combined_only)
        self.prof_names = []
        self.svg_name = None
        self.combined_name = None
        self.shared_profiler = None

        if self.combined_only:
            # When in combined_only mode, use a shared profiler
            # instance that gets updated for each test run.
            self.shared_profiler = cProfile.Profile()

    def pytest_sessionstart(self, session):  # @UnusedVariable
        try:
            os.makedirs("prof")
        except OSError:
            pass

    def pytest_sessionfinish(self, session, exitstatus):  # @UnusedVariable
        combined = None
        combined_file = os.path.join("prof", "combined.prof")
        if self.combined_only:
            combined = self.shared_profiler
        elif self.prof_names:
            combined = pstats.Stats(self.prof_names[0])
            for prof in self.prof_names[1:]:
                combined.add(prof)

        if combined:
            combined.dump_stats(combined_file)
            self.combined_name = combined_file
            if self.svg:
                self.svg_name = os.path.join("prof", "combined.svg")
                t = pipes.Template()
                t.append("gprof2dot -f pstats $IN", "f-")
                t.append("dot -Tsvg -o $OUT", "-f")
                t.copy(self.combined_name, self.svg_name)

    def pytest_terminal_summary(self, terminalreporter):
        if self.combined_name:
            terminalreporter.write("Profiling (from {prof}):\n".format(prof=self.combined_name))
            pstats.Stats(self.combined_name, stream=terminalreporter).strip_dirs().sort_stats('cumulative').print_stats(20)
        if self.svg_name:
            terminalreporter.write("SVG profile in {svg}.\n".format(svg=self.svg_name))

    @pytest.mark.tryfirst
    def pytest_pyfunc_call(self, __multicall__, pyfuncitem):
        """Hook into pytest_pyfunc_call; marked as a tryfirst hook so that we
        can call everyone else inside `cProfile.runctx`.
        """
        if self.combined_only:
            profiler = self.shared_profiler
            prof_name = None
        else:
            prof_name = os.path.join("prof", clean_filename(pyfuncitem.name) + ".prof")
            profiler = cProfile.Profile()

        profiler.runcall(__multicall__.execute)

        if prof_name:
            profiler.dump_stats(prof_name)
            self.prof_names.append(prof_name)


def pytest_addoption(parser):
    """pytest_addoption hook for profiling plugin"""
    group = parser.getgroup('Profiling')
    group.addoption("--profile", action="store_true",
                    help="generate profiling information")
    group.addoption("--profile-combined-only", action="store_true",
                    help="only generate the combined profile file")
    group.addoption("--profile-svg", action="store_true",
                    help="generate profiling graph (using gprof2dot and dot -Tsvg)")


def pytest_configure(config):
    """pytest_configure hook for profiling plugin"""
    profile_enable = any(config.getvalue(x) for x in ('profile', 'profile_svg'))
    if profile_enable:
        config.pluginmanager.register(Profiling(
            svg=config.getvalue('profile_svg'),
            combined_only=config.getvalue('profile_combined_only'),
        ))
