from __future__ import annotations
from collections import defaultdict
import re
from typing import (
    Callable,
    cast,
    Dict,
    Generic,
    Iterator,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    TYPE_CHECKING,
    Union
)
import warnings

from bs4.element import NavigableString, PageElement, Tag


# Define some type aliases to represent the many possibilities for
# matching bits of a parse tree.
#
# This is very complicated because we're applying a formal type system
# to some very DWIM code. The types we end up with will be the types
# of the arguments to the SoupStrainer constructor and (more
# familiarly to Beautiful Soup users) the find* methods.

# TODO In Python 3.10 we can use TypeAlias for this stuff. We can
# also use Pattern[str] instead of just Pattern.

# A function that takes a Tag and returns a yes-or-no answer.
# A TagNameMatchRule expects this kind of function, if you're
# going to pass it a function.
_TagMatchFunction = Callable[['Tag'], bool]

# A function that takes a single string and returns a yes-or-no
# answer. An AttributeValueMatchRule expects this kind of function, if
# you're going to pass it a function. So does a StringMatchRule
_StringMatchFunction = Callable[[str], bool]

# Either a tag name, an attribute value or a string can be matched
# against a string, bytestring, regular expression, or a boolean.
_BaseStrainable = Union[str, bytes, re.Pattern, bool]

# A tag can also be matched using a function that takes the Tag
# as its sole argument.
_BaseStrainableElement = Union[_BaseStrainable, _TagMatchFunction]

# A tag's attribute value can be matched using a function that takes
# the value as its sole argument.
_BaseStrainableAttribute = Union[_BaseStrainable, _StringMatchFunction]

# Finally, a tag name, attribute or string can be matched using either
# a single criterion or a list of criteria.
_StrainableElement = Union[
    _BaseStrainableElement, Iterable[_BaseStrainableElement]
]
_StrainableAttribute = Union[
    _BaseStrainableAttribute, Iterable[_BaseStrainableAttribute]
]
_StrainableString = _StrainableAttribute
    
class MatchRule(object):
    string: Optional[str]
    pattern: Optional[re.Pattern]
    present: Optional[bool]

    # All MatchRule objects also have a function, but the type of
    # the function depends on the subclass.
    
    def __init__(
            self,
            string:Optional[Union[str, bytes]]=None,
            pattern:Optional[re.Pattern]=None,
            function:Optional[Callable]=None,
            present:Optional[bool]=None,
    ):
        if isinstance(string, bytes):
            string = string.decode("utf8")
        self.string = string
        if isinstance(pattern, bytes):
            self.pattern = re.compile(pattern.decode("utf8"))
        elif isinstance(pattern, str):
            self.pattern = re.compile(pattern)
        else:
            self.pattern = pattern
        self.function = function
        self.present = present

        values = [x for x in (self.string, self.pattern,
                              self.function, self.present)
                  if x is not None]
        if len(values) == 0:
            raise ValueError(
                "Either string, pattern, function or present must be provided."
            )
        if len(values) > 1:
            raise ValueError(
                "At most one of string, pattern, function and present must be provided."
            )
        
    def _base_match(self, string):
        # self.present==True matches everything except None.
        if self.present is True:
            return string is not None

        # self.present==False matches _only_ None.
        if self.present is False:
            return string is None

        # self.string does an exact string match.
        if self.string is not None:
            #print(f"{self.string} ?= {string}")
            return self.string == string

        # self.pattern does a regular expression search.
        if self.pattern is not None:
            #print(f"{self.pattern} ?~ {string}")
            if string is None:
                return False
            return self.pattern.search(string) is not None

        return None
        
    def matches_string(self, string:str) -> bool:
        _base_result = self._base_match(string)
        if _base_result is not None:
            # No need to invoke the test function.
            return _base_result
        if self.function is not None and not self.function(string):
            #print(f"{self.function}({string}) == False")
            return False
        return True

    def __repr__(self) -> str:
        cls = type(self).__name__
        return f"<{cls} string={self.string} pattern={self.pattern} function={self.function} present={self.present}>"

    def __eq__(self, other):
        return (
            isinstance(other, MatchRule) and
            self.string==other.string and
            self.pattern==other.pattern and
            self.function==other.function and
            self.present==other.present
        )
    
class TagNameMatchRule(MatchRule):
    function: Optional[_TagMatchFunction]

    def matches_tag(self, tag:Tag) -> bool:
        base_value = self._base_match(tag.name)
        if base_value is not None:
            return base_value

        # The only remaining possibility is that the match is determined
        # by a function call. Call the function.
        assert self.function is not None
        if self.function(tag):
            return True
        return False
    
class AttributeValueMatchRule(MatchRule):
    function: Optional[_StringMatchFunction]

class StringMatchRule(MatchRule):
    function: Optional[_StringMatchFunction]
    
class SoupStrainer(object):
    """Encapsulates a number of ways of matching a markup element (a tag
    or a string).

    These are primarily created internally and used to underpin the
    find_* methods, but you can create one yourself and pass it in as
    ``parse_only`` to the `BeautifulSoup` constructor, to parse a
    subset of a large document.

    :param name: One or more restrictions on the tags found in a
    document.

    :param attrs: A dictionary that maps attribute names to
    restrictions on tags that use those attributes.

    :param string: One or more restrictions on the strings found in a
    document.

    :param kwargs: A dictionary that maps attribute names to restrictions
    on tags that use those attributes. These restrictions are additive to
    any specified in ``attrs``.
    """
    name_rules: List[TagNameMatchRule]
    attribute_rules: Dict[str, List[AttributeValueMatchRule]]
    string_rules: List[StringMatchRule]
   
    def __init__(self,
                 name: Optional[_StrainableElement]=None,
                 attrs: Dict[str, _StrainableAttribute]= {},
                 string: Optional[_StrainableString] = None,
                 **kwargs):
        
        if string is None and 'text' in kwargs:
            string = kwargs.pop('text')
            warnings.warn(
                "The 'text' argument to the SoupStrainer constructor is deprecated. Use 'string' instead.",
                DeprecationWarning, stacklevel=2
            )
        
        self.name_rules = cast(
            List[TagNameMatchRule],
            list(self._make_match_rules(name, TagNameMatchRule))
        )
        self.attribute_rules = defaultdict(list)
        
        if not isinstance(attrs, dict):
            # Passing something other than a dictionary as attrs is
            # sugar for matching that thing against the 'class'
            # attribute.
            attrs = { 'class' : attrs }

        for attrdict in attrs, kwargs:
            for attr, value in attrdict.items():
                if attr == 'class_' and attrdict is kwargs:
                    # If you pass in 'class_' as part of kwargs, it's
                    # because class is a Python reserved word. If you
                    # pass it in as part of the attrs dict, it's
                    # because you really are looking for an attribute
                    # called 'class_'.
                    attr = 'class'
                if value is None:
                    value = False
                for rule_obj in self._make_match_rules(
                    value, AttributeValueMatchRule
                ):
                    self.attribute_rules[attr].append(
                        cast(AttributeValueMatchRule, rule_obj)
                    )
                                                      
        self.string_rules = cast(
            List[StringMatchRule],
            list(self._make_match_rules(string, StringMatchRule))
        )
        

        # DEPRECATED: You shouldn't need to check these, and if you do,
        # you're probably not taking into account all of the types of
        # values this variable might have. Look at the .string_rules
        # list instead.
        self.text = string
        self.string = string
        
    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name_rules} attrs={self.attribute_rules} string={self.string_rules}>"

    @classmethod
    def _make_match_rules(cls, obj, rule_class:type) -> Iterator[MatchRule]:
        """Convert a vaguely-specific 'object' into one or more well-defined
        match rules.

        :param obj: Some kind of object that corresponds to one or more
           matching rules.
        :param rule_class: Create instances of this MatchRule subclass.
        """
        if obj is None:
            return
        if isinstance(obj, (str,bytes)):
            yield rule_class(string=obj)
        elif isinstance(obj, bool):
            yield rule_class(present=obj)
        elif callable(obj):
            yield rule_class(function=obj)
        elif isinstance(obj, re.Pattern):
            yield rule_class(pattern=obj)
        elif hasattr(obj, '__iter__'):
            for o in obj:
                if not isinstance(o, (bytes, str)) and hasattr(o, '__iter__'):
                    # This is almost certainly the user's
                    # mistake. This list contains another list, which
                    # opens up the possibility of infinite
                    # self-reference. In the interests of avoiding
                    # infinite recursion, we'll ignore this item
                    # rather than looking inside.
                    warnings.warn(
                        f"Ignoring nested list {o} to avoid the possibility of infinite recursion.",
                        stacklevel=5
                    )
                    continue
                for x in cls._make_match_rules(o, rule_class):
                    yield x
        else:
            yield rule_class(string=str(obj))
            
    def matches_tag(self, tag=Tag) -> bool:
        """Do the rules of this SoupStrainer trigger a match against the
        given `Tag`?

        If the `SoupStrainer` has any `TagNameMatchRule`, at least one
        must match the `Tag` or its `Tag.name`.

        If there are any `AttributeValueMatchRule` for a given
        attribute, at least one of them must match the attribute
        value.

        If there are any `StringMatchRule`, at least one must match,
        but a `SoupStrainer` that *only* contains `StringMatchRule`
        cannot match a `Tag`, only a `NavigableString`.
        """
        # String rules cannot not match a Tag on their own.
        if not self.name_rules and not self.attribute_rules:
            return False

        # Optimization for a very common case where the user is
        # searching for a tag with one specific name, and we're
        # looking at a tag with a different name.
        if (not tag.prefix
            and len(self.name_rules) == 1
            and self.name_rules[0].string is not None
            and tag.name != self.name_rules[0].string):
            return False
        
        # If there are name rules, at least one must match. It can
        # match either the Tag object itself or the prefixed name of
        # the tag.
        prefixed_name = None
        if tag.prefix:
            prefixed_name = f"{tag.prefix}:{tag.name}"
        if self.name_rules:
            name_matches = False
            for rule in self.name_rules:
                # attrs = " ".join(
                #     [f"{k}={v}" for k, v in sorted(tag.attrs.items())]
                # )
                #print(f"Testing <{tag.name} {attrs}>{tag.string}</{tag.name}> against {rule}")
                if rule.matches_tag(tag) or (
                    prefixed_name is not None
                        and rule.matches_string(prefixed_name)
                ):
                    name_matches = True
                    break

            if not name_matches:
                return False
            
        # If there are attribute rules for a given attribute, at least
        # one of them must match. If there are rules for multiple
        # attributes, each attribute must have at least one match.
        for attr, rules in self.attribute_rules.items():
            attr_value = tag.get(attr, None)
            this_attr_match = self._attribute_match(attr_value, rules)
            if not this_attr_match:
                return False

        # If there are string rules, at least one must match.
        if self.string_rules and not self.matches_any_string_rule(tag.string):
            return False
        return True

    def _attribute_match(self, attr_value:Optional[str],
                         rules:Iterable[AttributeValueMatchRule]) -> bool:
        attr_values: Sequence[Optional[str]]
        if isinstance(attr_value, list):
            attr_values = attr_value
        else:
            attr_values = [attr_value]

        def _match_attribute_value_helper(attr_values):
            for rule in rules:
                for attr_value in attr_values:
                    if rule.matches_string(attr_value):
                        return True
            return False
        this_attr_match = _match_attribute_value_helper(attr_values)
        if not this_attr_match and len(attr_values) > 1:
            # This cast converts Optional[str] to plain str.
            #
            # We know if there's more than one value, there can't be
            # any None in the list, because Beautiful Soup never uses
            # None as a value of a multi-valued attribute, and if None
            # is passed in as attr_value, it's turned into a list with
            # a single element (thus len(attr_values) > 1 fails).
            attr_values = cast(Sequence[str], attr_values)
            
            # Try again but treat the attribute value
            # as a single string.
            joined_attr_value = " ".join(attr_values)
            this_attr_match = _match_attribute_value_helper(
                [joined_attr_value]
            )
        return this_attr_match
    
    def allow_tag_creation(self, nsprefix:str, name:str, attrs:dict[str, str]) -> bool:
        """Based on the name and attributes of a tag, see whether this
        SoupStrainer will allow a Tag object to even be created.

        :param name: The name of the prospective tag.
        :param attrs: The attributes of the prospective tag.
        """
        if self.string_rules:
            # A SoupStrainer that has string rules can't be used to
            # manage tag creation, because the string rule can't be
            # evaluated until after the tag and all of its contents
            # have been parsed.
            return False
        
        prefixed_name = None
        if nsprefix:
            prefixed_name = f"{nsprefix}:{name}"
        if self.name_rules:
            # At least one name rule must match.
            name_match = False
            for rule in self.name_rules:
                for x in name, prefixed_name:
                    if x is not None:
                        if rule.matches_string(x):
                            name_match = True
                            break
            if not name_match:
                return False

        # For each attribute that has rules, at least one rule must
        # match.
        for attr, rules in self.attribute_rules.items():
            attr_value = attrs.get(attr)
            if not self._attribute_match(attr_value, rules):
                return False
            
        return True

    def allow_string_creation(self, string:str) -> bool:
        if self.name_rules or self.attribute_rules:
            # A SoupStrainer that has name or attribute rules won't
            # match any strings; it's designed to match tags with
            # certain properties.
            return False
        if not self.matches_any_string_rule(string):
            return False
        return True
    
    def matches_any_string_rule(self, string:str) -> bool:
        """Based on the content of a string, see whether it 
        matches

        """
        if not self.string_rules:
            return True
        for string_rule in self.string_rules:
            if string_rule.matches_string(string):
                return True
        return False
        
    
    # DEPRECATED 4.13.0
    def search_tag(self, name, attrs):
        return self.allow_tag_creation(None, name, attrs)
    
    def search(self, element:PageElement):
        # TODO: This method needs to be removed or redone. It is
        # very confusing but it's used everywhere.
        match = None
        if isinstance(element, Tag):
            match = self.matches_tag(element)
        else:
            assert isinstance(element, NavigableString)
            match = False
            if not (self.name_rules or self.attribute_rules):
                # A NavigableString can only match a SoupStrainer that
                # does not define any name or attribute restrictions.
                for rule in self.string_rules:
                    if rule.matches_string(element):
                        match = True
                        break
        return element if match else False

