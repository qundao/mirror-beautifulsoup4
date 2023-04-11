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
# to some very DWIM code.

# TODO In Python 3.10 we can use TypeAlias for this stuff. We can
# also use Pattern[str] instead of just Pattern.
# A function that takes a Tag and returns a yes-or-no answer.
_ElementFunction = Callable[['Tag'], bool]

# A function that takes a single attribute value and returns a
# yes-or-no answer.
_AttributeFunction = Callable[[str], bool]

# Either a tag name or an attribute value can be strained with a
# string, bytestring, regular expression, or None.
#
# (But note that None means different things when straining a tag name
#  versus an attribute value.)
_BaseStrainable = Union[str, bytes, re.Pattern, bool, None]

# A tag name can also be strained using a function designed to
# match an element.
_BaseStrainableElement = Union[_BaseStrainable, _ElementFunction]

# A tag attribute can also be strained using a function designed to
# match an attribute value.
_BaseStrainableAttribute = Union[_BaseStrainable, _AttributeFunction]

# Finally, a tag name or attribute can be strained using a single filter
# or a list of filters.
_StrainableElement = Union[
    _BaseStrainableElement, Iterable[_BaseStrainableElement]
]
_StrainableAttribute = Union[
    _BaseStrainableAttribute, Iterable[_BaseStrainableAttribute]
]
    
# Now define those types again, without allowing bytes. These are the
# types used once the values passed into the SoupStrainer constructor
# have been normalized.
_BaseNormalizedStrainable = Union[str, re.Pattern, bool, None]
_BaseNormalizedStrainableElement = Union[
    _BaseNormalizedStrainable, _ElementFunction
]
_BaseNormalizedStrainableAttribute = Union[
    _BaseNormalizedStrainable, _AttributeFunction
]
_NormalizedStrainableElement = Union[
    _BaseNormalizedStrainableElement,
    Iterable[_BaseNormalizedStrainableElement]
]
_NormalizedStrainableAttribute = Union[
    _BaseNormalizedStrainableAttribute,
    Iterable[_BaseNormalizedStrainableAttribute]
]

class MatchRule(object):
    string: Optional[str]
    pattern: Optional[re.Pattern]
    function: Optional[Callable]
    present: bool
    
    def __init__(
            self,
            string:Optional[Union[str, bytes]]=None,
            pattern:Optional[re.Pattern]=None,
            function:Optional[Callable]=None,
            present:bool=None,
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
        
    def matches_string(self, string):
        _base_result = self._base_match(string)
        if _base_result is not None:
            # No need to invoke the test function.
            return _base_result
        if self.function is not None and not self.function(string):
            #print(f"{self.function}({string}) == False")
            return False
        return True

    def __repr__(self):
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
    function: Callable[['Tag'], bool]    

    def matches_tag(self, tag):
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
    function: Callable[[str], bool]

class StringMatchRule(MatchRule):
    function: Callable[[str], bool]
    
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
    name_rules: Iterable[TagNameMatchRule]
    attribute_rules: Dict[str, Iterable[AtributeValueMatchRule]]
    string_rules: Iterable[StringMatchRule]
   
    def __init__(self,
                 name =None,
                 attrs = {},
                 string=None,
                 **kwargs):
        
        if string is None and 'text' in kwargs:
            string = kwargs.pop('text')
            warnings.warn(
                "The 'text' argument to the SoupStrainer constructor is deprecated. Use 'string' instead.",
                DeprecationWarning, stacklevel=2
            )
        
        self.name_rules = list(self._make_match_rules(name, TagNameMatchRule))
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
                    self.attribute_rules[attr].append(rule_obj)
                                                      
        self.string_rules = list(
            self._make_match_rules(string, StringMatchRule)
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
        elif isinstance(obj, Callable):
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
        if not tag.prefix and len(self.name_rules) == 1 and self.name_rules[0].string is not None and tag.name != self.name_rules[0].string:
            return False
        
        # If there are attribute rules for a given attribute, at least
        # one must match. If there are rules for multiple attributes,
        # each one must have a match.

        # If there are string rules, at least one must match.

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
            
        for attr, rules in self.attribute_rules.items():
            attr_value = tag.get(attr)
            this_attr_match = self._attribute_match(attr_value, rules)
            if not this_attr_match:
                return False

        if self.string_rules and not self.matches_any_string_rule(tag.string):
            return False
        return True

    def _attribute_match(self, attr_value, rules):
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
                if any(rule.matches_string(x) for x in (name, prefixed_name)):
                    name_match = True
            if not name_match:
                return False

        # For each attribute that has rules, at least one rule must
        # match.
        for attr, rules in self.attribute_rules.items():
            attr_value = attrs.get(attr)
            if not self._attribute_match(attr_value, rules):
                return False
            
        return True

    def allow_string_creation(self, string:str):
        if self.name_rules or self.attribute_rules:
            # A SoupStrainer that has name or attribute rules won't
            # match any strings; it's designed to match tags with
            # certain properties.
            return False
        if not self.matches_any_string_rule(string):
            return False
        return True
    
    def matches_any_string_rule(self, string:str):
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
        match = None
        if isinstance(element, Tag):
            match = self.matches_tag(element)
        else:
            match = False
            if not (self.name_rules or self.attribute_rules):
                # A NavigableString can only match a SoupStrainer that
                # does not define any name or attribute restrictions.
                for rule in self.string_rules:
                    if rule.matches_string(element):
                        match = True
                        break
        return element if match else False
            
class SoupStrainerOld(object):
    
    name_rules: Iterable[TagNameMatchRule]
    attribute_rules: Dict[str, Iterable[AttributeValueMatchRule]]
    string_rules: Optional[StringMatchRule]
                              
    def __init__(self):
        """Constructor.

        The SoupStrainer constructor takes the same arguments passed
        into the find_* methods. See the online documentation for
        detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter to find a NavigableString with specific text.
        :kwargs: A dictionary of filters on attribute values.
        """
        if string is None and 'text' in kwargs:
            string = kwargs.pop('text')
            warnings.warn(
                "The 'text' argument to the SoupStrainer constructor is deprecated. Use 'string' instead.",
                DeprecationWarning, stacklevel=2
            )

        self.name = self._normalize_search_value(name)
        if not isinstance(attrs, dict):
            # Treat a non-dict value for attrs as a search for the 'class'
            # attribute.
            kwargs['class'] = attrs
            attrs = None

        if 'class_' in kwargs:
            # Treat class_="foo" as a search for the 'class'
            # attribute, overriding any non-dict value for attrs.
            kwargs['class'] = kwargs['class_']
            del kwargs['class_']

        if kwargs:
            if attrs:
                attrs = attrs.copy()
                attrs.update(kwargs)
            else:
                attrs = kwargs
        normalized_attrs = {}
        for key, value in list(attrs.items()):
            normalized_attrs[key] = self._normalize_search_value(value)

        self.attrs = normalized_attrs
        self.string = self._normalize_search_value(string)

        # DEPRECATED but just in case someone is checking this.
        self.text = self.string

    def _normalize_search_value(self, value):
        # Leave it alone if it's a Unicode string, a callable, a
        # regular expression, a boolean, or None.
        if (isinstance(value, str) or callable(value) or hasattr(value, 'match')
            or isinstance(value, bool) or value is None):
            return value

        # If it's a bytestring, convert it to Unicode, treating it as UTF-8.
        if isinstance(value, bytes):
            return value.decode("utf8")

        # If it's listlike, convert it into a list of strings.
        if hasattr(value, '__iter__'):
            new_value = []
            for v in value:
                if (hasattr(v, '__iter__') and not isinstance(v, bytes)
                    and not isinstance(v, str)):
                    # This is almost certainly the user's mistake. In the
                    # interests of avoiding infinite loops, we'll let
                    # it through as-is rather than doing a recursive call.
                    new_value.append(v)
                else:
                    new_value.append(self._normalize_search_value(v))
            return new_value

        # Otherwise, convert it into a Unicode string.
        return str(value)

    def __str__(self) -> str:
        """A human-readable representation of this SoupStrainer."""
        if self.string:
            return self.string
        else:
            return "%s|%s" % (self.name, self.attrs)

    def search_tag(self, markup_name:Optional[Union[Tag,str]]=None,
                   markup_attrs={}):
        """Check whether a Tag with the given name and attributes would
        match this SoupStrainer.

        When a SoupStrainer is used during the parse phase, this is
        used prospectively to decide whether to even bother creating a
        Tag object. When a SoupStrainer is used to perform a search,
        this is used to match the SoupStrainer's configuration against
        existing Tag objects.

        TODO: This method signature is confusing and should be
        reworked. And/or the method itself can probably be made
        private.

        :param markup_name: A tag name as found in some markup.
        :param markup_attrs: A dictionary of attributes as found in some markup.

        :return: True if the prospective tag would match this SoupStrainer;
            False otherwise.
        """
        found = None
        markup = None
        if isinstance(markup_name, Tag):
            markup = markup_name
            markup_attrs = markup

        if isinstance(self.name, str):
            # Optimization for a very common case where the user is
            # searching for a tag with one specific name, and we're
            # looking at a tag with a different name.
            if markup and not markup.prefix and self.name != markup.name:
                 return False

        call_function_with_tag_data = (
            callable(self.name)
            and not isinstance(markup_name, Tag))

        if ((not self.name)
            or call_function_with_tag_data
            or (markup and self._matches(markup, self.name))
            or (not markup and self._matches(markup_name, self.name))):
            if call_function_with_tag_data:
                match = self.name(markup_name, markup_attrs)
            else:
                match = True
                markup_attr_map = None
                for attr, match_against in list(self.attrs.items()):
                    if not markup_attr_map:
                        if hasattr(markup_attrs, 'get'):
                            markup_attr_map = markup_attrs
                        else:
                            markup_attr_map = {}
                            for k, v in markup_attrs:
                                markup_attr_map[k] = v
                    attr_value = markup_attr_map.get(attr)
                    if not self._matches(attr_value, match_against):
                        match = False
                        break
            if match:
                if markup:
                    found = markup
                else:
                    found = markup_name
        if found and self.string and not self._matches(found.string, self.string):
            found = None
        return found

    searchTag = search_tag #: :meta private: BS3

    def search(self, markup:PageElement) -> PageElement | None:
        """Check whether the given `PageElement` matches this `SoupStrainer`.

        This is used by the core _find_all() method, which is ultimately
        called by all find_* methods.

        TODO: This is never passed an Iterable, and what it does when
        passed an Iterable isn't very useful. It should be simplified.
        Also, it seemingly returns either a PageElement or False,
        which is slightly off.
        """
        # print('looking for %s in %s' % (self, markup))
        found = None
        # If given a list of items, scan it for a text element that
        # matches.
        if hasattr(markup, '__iter__') and not isinstance(markup, (Tag, str)):
            for element in markup:
                if isinstance(element, NavigableString) \
                       and self.search(element):
                    found = element
                    break
        # If it's a Tag, make sure its name or attributes match.
        # Don't bother with Tags if we're searching for text.
        elif isinstance(markup, Tag):
            if not self.string or self.name or self.attrs:
                found = self.search_tag(markup)
        # If it's text, make sure the text matches.
        elif isinstance(markup, NavigableString) or \
                 isinstance(markup, str):
            if not self.name and not self.attrs and self._matches(markup, self.string):
                found = markup
        else:
            raise Exception(
                "I don't know how to match against a %s" % markup.__class__)
        return found

    def _matches(self, markup, match_against, already_tried=None):
        # print(u"Matching %s against %s" % (markup, match_against))
        result = False
        if isinstance(markup, list) or isinstance(markup, tuple):
            # This should only happen when searching a multi-valued attribute
            # like 'class'.
            for item in markup:
                if self._matches(item, match_against):
                    return True
            # We didn't match any particular value of the multivalue
            # attribute, but maybe we match the attribute value when
            # considered as a string.
            if self._matches(' '.join(markup), match_against):
                return True
            return False

        if match_against is True:
            # True matches any non-None value.
            return markup is not None

        if callable(match_against):
            return match_against(markup)

        # Custom callables take the tag as an argument, but all
        # other ways of matching match the tag name as a string.
        original_markup = markup
        if isinstance(markup, Tag):
            markup = markup.name

        # Ensure that `markup` is either a Unicode string, or None.
        markup = self._normalize_search_value(markup)

        if markup is None:
            # None matches None, False, an empty string, an empty list, and so on.
            return not match_against

        if (hasattr(match_against, '__iter__')
            and not isinstance(match_against, str)):
            # We're asked to match against an iterable of items.
            # The markup must be match at least one item in the
            # iterable. We'll try each one in turn.
            #
            # To avoid infinite recursion we need to keep track of
            # items we've already seen.
            if not already_tried:
                already_tried = set()
            for item in match_against:
                if item.__hash__:
                    key = item
                else:
                    key = id(item)
                if key in already_tried:
                    continue
                else:
                    already_tried.add(key)
                    if self._matches(original_markup, item, already_tried):
                        return True
            else:
                return False

        # Beyond this point we might need to run the test twice: once against
        # the tag's name and once against its prefixed name.
        match = False

        if not match and isinstance(match_against, str):
            # Exact string match
            match = markup == match_against

        if not match and hasattr(match_against, 'search'):
            # Regexp match
            return match_against.search(markup)

        if (not match
            and isinstance(original_markup, Tag)
            and original_markup.prefix):
            # Try the whole thing again with the prefixed tag name.
            return self._matches(
                original_markup.prefix + ':' + original_markup.name, match_against
            )

        return match

