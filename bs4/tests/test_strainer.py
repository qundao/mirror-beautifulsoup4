import pytest
import re
import warnings

from . import (
    SoupTest,
)
from bs4.element import Tag
from bs4.strainer import (
    MatchRule,
    SoupStrainer,
    TagNameMatchRule,
)

class TestMatchrule(SoupTest):

    def _tuple(self, rule):
        if isinstance(rule.pattern, str):
            import pdb; pdb.set_trace()

        return (
            rule.string,
            rule.pattern.pattern if rule.pattern else None,
            rule.function,
            rule.present
        )

    def tag_function(x:Tag) -> bool:
        return False

    def string_function(x:str) -> bool:
        return False

    @pytest.mark.parametrize(
        "constructor_args, constructor_kwargs, result",
        [
            # String
            ([], dict(string="a"), ("a", None, None, None)),
            ([], dict(string="\N{SNOWMAN}".encode("utf8")),
             ("\N{SNOWMAN}", None, None, None)),

            # Regular expression
            ([], dict(pattern=re.compile("a")), (None, "a", None, None)),
            ([], dict(pattern="b"), (None, "b", None, None)),
            ([], dict(pattern=b"c"), (None, "c", None, None)),

            # Function
            ([], dict(function=tag_function), (None, None, tag_function, None)),
            ([], dict(function=string_function), (None, None, string_function, None)),

            # Boolean
            ([], dict(present=True), (None, None, None, True)),

            # With positional arguments rather than keywords
            (("a", None, None, None), {}, ("a", None, None, None)),
            ((None, "b", None, None), {}, (None, "b", None, None)),
            ((None, None, tag_function, None), {},
             (None, None, tag_function, None)),
            ((None, None, None, True), {}, (None, None, None, True)),
        ]
    )
    def test_constructor(self, constructor_args, constructor_kwargs, result):
        rule = MatchRule(*constructor_args, **constructor_kwargs)
        assert result == self._tuple(rule)

    def test_empty_match_not_allowed(self):
        with pytest.raises(
                ValueError,
                match="Either string, pattern, function or present must be provided."
        ):
            MatchRule()

    def test_full_match_not_allowed(self):
        with pytest.raises(
                ValueError,
                match="At most one of string, pattern, function and present must be provided."
        ):
            MatchRule("a", "b", self.tag_function, True)

    @pytest.mark.parametrize(
        "rule_kwargs, match_against, result",
        [
            (dict(string="a"), "a", True),
            (dict(string="a"), "ab", False),

            (dict(pattern="a"), "a", True),
            (dict(pattern="a"), "ab", True),
            (dict(pattern="^a$"), "a", True),
            (dict(pattern="^a$"), "ab", False),

            (dict(present=True), "any random value", True),
            (dict(present=True), None, False),
            (dict(present=False), "any random value", False),
            (dict(present=False), None, True),

            (dict(function=lambda x: x.upper() == x), "UPPERCASE", True),
            (dict(function=lambda x: x.upper() == x), "lowercase", False),

            (dict(function=lambda x: x.lower() == x), "UPPERCASE", False),
            (dict(function=lambda x: x.lower() == x), "lowercase", True),
        ],
    )
    def test_matches_string(self, rule_kwargs, match_against, result):
        rule = MatchRule(**rule_kwargs)
        assert rule.matches_string(match_against) == result
        
class TestTagNameMatchRule(SoupTest):
    @pytest.mark.parametrize(
        "rule_kwargs, tag_kwargs, result",
        [
            (dict(string="a"), dict(name="a"), True),
            (dict(string="a"), dict(name="ab"), False),

            (dict(pattern="a"), dict(name="a"), True),
            (dict(pattern="a"), dict(name="ab"), True),
            (dict(pattern="^a$"), dict(name="a"), True),
            (dict(pattern="^a$"), dict(name="ab"), False),

            # This isn't very useful, but it will work.
            (dict(present=True), dict(name="any random value"), True),
            (dict(present=False), dict(name="any random value"), False),

            (dict(function=lambda t: t.name in t.attrs),
             dict(name="id", attrs=dict(id="a")), True),

            (dict(function=lambda t: t.name in t.attrs),
             dict(name="id", attrs={"class":"a"}), False),
        ],
    )
    def test_matches_tag(self, rule_kwargs, tag_kwargs, result):
        rule = TagNameMatchRule(**rule_kwargs)
        tag = Tag(**tag_kwargs)
        assert rule.matches_tag(tag) == result

# AttributeValueMatchRule and StringMatchRule have the same
# logic as MatchRule.
        
class TestSoupStrainer(SoupTest):
    
    def test_constructor_string_deprecated_text_argument(self):
        with warnings.catch_warnings(record=True) as w:
            strainer = SoupStrainer(text="text")
            assert strainer.string == 'text'
            [warning] = w
            msg = str(warning.message)
            assert warning.filename == __file__
            assert msg == "The 'text' argument to the SoupStrainer constructor is deprecated. Use 'string' instead."

