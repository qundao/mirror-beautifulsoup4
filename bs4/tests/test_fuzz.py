"""This file contains test cases reported by third parties using
fuzzing tools, primarily from Google's oss-fuzz project. Some of these
represent real problems with Beautiful Soup, but many are problems in
libraries that Beautiful Soup depends on, and many of the test cases
represent different ways of triggering the same problem.

Grouping these test cases together makes it easy to see which test
cases represent the same problem, and puts the test cases in close
proximity to code that can trigger the problems.
"""
import os
import pytest
from bs4 import (
    BeautifulSoup,
    ParserRejectedMarkup,
)

class TestFuzz(object):

    # This class of error has been fixed by catching a less helpful
    # exception from html.parser and raising ParserRejectedMarkup
    # instead.
    @pytest.mark.parametrize(
        "filename", [
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5703933063462912",
        ]
    )
    def test_rejected_markup(self, filename):
        markup = self.__markup(filename)
        with pytest.raises(ParserRejectedMarkup):
            BeautifulSoup(markup, 'html.parser')

    # This class of error has to do with very deeply nested documents
    # which overflow the Python call stack when the tree is converted
    # to string. This is an issue with Beautiful Soup. See
    # [bug=1471755], for example.
    @pytest.mark.skip("recursion limit exceeded")
    @pytest.mark.parametrize(
        "filename", [
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5984173902397440",
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5167584867909632",
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5984173902397440",
            "clusterfuzz-testcase-minimized-bs4_fuzzer-6124268085182464",
            "clusterfuzz-testcase-minimized-bs4_fuzzer-6450958476902400",
        ]
    )
    def test_recursion_limit_exceeded(self, filename):
        markup = self.__markup(filename)
        with pytest.raises(RecursionError):
            BeautifulSoup(markup, 'html.parser').encode()

    # This class of error represents problems with html5lib's parser,
    # not Beautiful Soup.
    @pytest.mark.skip("html5lib problems")
    @pytest.mark.parametrize(
        "filename", [
            # b"""ÿ<!DOCTyPEV PUBLIC'''Ð'"""
            "clusterfuzz-testcase-minimized-bs4_fuzzer-4818336571064320",

            # b')<a><math><TR><a><mI><a><p><a>'
            "clusterfuzz-testcase-minimized-bs4_fuzzer-4999465949331456",

            # very large, lots of %&&%&&
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5389523868581888",

            # b'-<math><sElect><mi><sElect><sElect>'
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5843991618256896",

            # b'ñ<table><svg><html>'
            "clusterfuzz-testcase-minimized-bs4_fuzzer-6241471367348224",

            # <TABLE>, some ^@ characters, some <math> tags.
            "clusterfuzz-testcase-minimized-bs4_fuzzer-6600557255327744"
        ]
    )
    def test_html5lib_parse_errors(self, filename):
        markup = self.__markup(filename)
        print(BeautifulSoup(markup, 'html5lib').encode())

    def __markup(self, filename):
        this_dir = os.path.split(__file__)[0]
        path = os.path.join(this_dir, 'fuzz', filename)
        return open(path, 'rb').read()
