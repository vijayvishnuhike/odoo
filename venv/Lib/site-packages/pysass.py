#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
from datetime import datetime, timedelta
from functools import wraps
from optparse import AmbiguousOptionError, BadOptionError, OptionParser

from pysassc import main as pysassc_main
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


def main(argv=sys.argv):
    watch = False
    if "-w" in argv:
        watch = True
        argv.remove("-w")
    if "--watch" in argv:
        watch = True
        argv.remove("--watch")

    if watch:
        # Just parsing usefull options
        parser = PassThroughOptionParser()
        parser.add_option(
            "-I",
            "--include-path",
            metavar="DIR",
            dest="include_paths",
            action="append",
        )
        options, args = parser.parse_args(argv[1:])
        # Fake parsing others
        args = fake_parser(args)

        rcode = throttled_pysassc_main(argv=argv)
        if not args:
            sys.exit(rcode)

        # Retrieve directories to watch
        sourcepath = os.path.dirname(args[0])
        paths = options.include_paths + [sourcepath or "."]

        observer = Observer()
        for path in paths:
            observer.schedule(ScssHandler(argv), path=path, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()
    else:
        pysassc_main()


class PassThroughOptionParser(OptionParser):
    """
    An unknown option pass-through implementation of OptionParser.

    When unknown arguments are encountered, bundle with largs and try again,
    until rargs is depleted.

    sys.exit(status) will still be called if a known argument is passed
    incorrectly (e.g. missing arguments or bad argument types, etc.)
    """

    def _process_args(self, largs, rargs, values):
        while rargs:
            try:
                OptionParser._process_args(self, largs, rargs, values)
            except (BadOptionError, AmbiguousOptionError) as e:
                largs.append(e.opt_str)


def fake_parser(args):
    ignore_next = False
    out = []
    for v in args:
        if ignore_next:
            ignore_next = False
            continue
        if v in ["-t", "--style", "-s", "--out-style"]:
            ignore_next = True
            continue
        if v in [
            "-m",
            "-g",
            "--sourcemap",
            "-p",
            "--precision",
            "--source-comments",
            "-v",
            "--version",
            "-h",
            "--help",
        ]:
            continue
        out.append(v)
    return out


class ScssHandler(PatternMatchingEventHandler):
    patterns = ["*.scss"]

    def __init__(self, argv, *args, **kwargs):
        self.argv = argv
        return super().__init__(*args, **kwargs)

    def process(self, event):
        print(event.src_path, event.event_type)
        throttled_pysassc_main(argv=self.argv)

    def on_modified(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)


class Throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
        @Throttle(minutes=1)
        def my_fun():
            pass
    """

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_period = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
        self.time_of_last_call = datetime.min

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            time_since_last_call = now - self.time_of_last_call

            if time_since_last_call > self.throttle_period:
                self.time_of_last_call = now
                return fn(*args, **kwargs)

        return wrapper


@Throttle(seconds=1)
def throttled_pysassc_main(*args, **kwargs):
    print("Compiling...")
    pysassc_main(*args, **kwargs)
    print("Watching...")


if __name__ == "__main__":
    main()
