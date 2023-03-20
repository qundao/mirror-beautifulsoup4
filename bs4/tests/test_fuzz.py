import os
import pytest
from bs4 import (
    BeautifulSoup,
    ParserRejectedMarkup,
)

class TestFuzz(object):

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
        
    @pytest.mark.parametrize(
        "filename", [
            "clusterfuzz-testcase-minimized-bs4_fuzzer-5703933063462912",
        ]
    )
    def test_rejected_markup(self, filename):
        markup = self.__markup(filename)
        with pytest.raises(ParserRejectedMarkup):
            BeautifulSoup(markup, 'html.parser')

    @pytest.mark.skip("recursion")
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
        
    def __markup(self, filename):
        this_dir = os.path.split(__file__)[0]
        path = os.path.join(this_dir, 'fuzz', filename)
        return open(path, 'rb').read()
