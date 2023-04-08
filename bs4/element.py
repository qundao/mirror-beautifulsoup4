from __future__ import annotations
# Use of this source code is governed by the MIT license.
__license__ = "MIT"

from collections.abc import Callable
from typing import Callable as CallableType, cast, Dict, Generic, Iterator, Iterable, List, Set, Tuple, TypeVar, TYPE_CHECKING, Union # Python 3.9

import re
import sys
from typing import Optional, Set
import warnings

from bs4.css import CSS
from bs4.formatter import (
    Formatter,
    HTMLFormatter,
    XMLFormatter,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup
    from bs4.builder import TreeBuilder

#: Documents output by Beautiful Soup will be encoded with
#: this encoding unless you specify otherwise.
DEFAULT_OUTPUT_ENCODING = "utf-8"

nonwhitespace_re = re.compile(r"\S+")

# NOTE: This isn't used as of 4.7.0. I'm leaving it for a little bit on
# the off chance someone imported it for their own use.
whitespace_re = re.compile(r"\s+")

def _alias(attr):
    """Alias one attribute name to another for backward compatibility"""
    @property
    def alias(self):
        return getattr(self, attr)

    @alias.setter
    def alias(self):
        return setattr(self, attr)
    return alias


#: These encodings are recognized by Python (so `Tag.encode`
#: could theoretically support them) but XML and HTML don't recognize
#: them (so they should not show up in an XML or HTML document as that
#: document's encoding).
#:
#: If an XML document is encoded in one of these encodings, no encoding
#: will be mentioned in the XML declaration. If an HTML document is
#: encoded in one of these encodings, and the HTML document has a
#: <meta> tag that mentions an encoding, the encoding will be given as
#: the empty string.
#:
#: Source:
#: Python documentation, `Python Specific Encodings <https://docs.python.org/3/library/codecs.html#python-specific-encodings>`_
PYTHON_SPECIFIC_ENCODINGS: Set = set([
    "idna",
    "mbcs",
    "oem",
    "palmos",
    "punycode",
    "raw_unicode_escape",
    "undefined",
    "unicode_escape",
    "raw-unicode-escape",
    "unicode-escape",
    "string-escape",
    "string_escape",
])


class NamespacedAttribute(str):
    """A namespaced string (e.g. 'xml:lang') that remembers the namespace
    ('xml') and the name ('lang') that were used to create it.
    """

    prefix: Optional[str]
    name: Optional[str]
    namespace: Optional[str]
    
    def __new__(cls, prefix:str, name:Optional[str]=None, namespace:Optional[str]=None):
        if not name:
            # This is the default namespace. Its name "has no value"
            # per https://www.w3.org/TR/xml-names/#defaulting
            name = None

        if not name:
            obj = str.__new__(cls, prefix)
        elif not prefix:
            # Not really namespaced.
            obj = str.__new__(cls, name)
        else:
            obj = str.__new__(cls, prefix + ":" + name)
        obj.prefix = prefix
        obj.name = name
        obj.namespace = namespace
        return obj

class AttributeValueWithCharsetSubstitution(str):
    """An abstract class standing in for a character encoding specified
    inside an HTML ``<meta>`` tag.

    Subclasses exist for each place such a character encoding might be
    found: either inside the ``charset`` attribute
    (`CharsetMetaAttributeValue`) or inside the ``content`` attribute
    (`ContentMetaAttributeValue`)

    This allows Beautiful Soup to replace that part of the HTML file
    with a different encoding when ouputting a tree as a string.
    """
    pass

class CharsetMetaAttributeValue(AttributeValueWithCharsetSubstitution):
    """A generic stand-in for the value of a ``<meta>`` tag's ``charset``
    attribute.

    When Beautiful Soup parses the markup ``<meta charset="utf8">``, the
    value of the ``charset`` attribute will become one of these objects.

    If the document is later encoded to an encoding other than UTF-8, its
    ``<meta>`` tag will mention the new encoding instead of ``utf8``.
    """
    def __new__(cls, original_value):
        obj = str.__new__(cls, original_value)
        obj.original_value = original_value
        return obj

    def substitute_encoding(self, eventual_encoding="utf-8") -> str:
        """When an HTML document is being encoded to a given encoding, the
        value of a ``<meta>`` tag's ``charset`` becomes the name of
        the encoding.
        """
        if eventual_encoding in PYTHON_SPECIFIC_ENCODINGS:
            return ''
        return eventual_encoding


class ContentMetaAttributeValue(AttributeValueWithCharsetSubstitution):
    """A generic stand-in for the value of a ``<meta>`` tag's ``content``
    attribute.

    When Beautiful Soup parses the markup:
     ``<meta http-equiv="content-type" content="text/html; charset=utf8">``

    The value of the ``content`` attribute will become one of these objects.

    If the document is later encoded to an encoding other than UTF-8, its
    ``<meta>`` tag will mention the new encoding instead of ``utf8``.
    """
    #: :meta private:
    CHARSET_RE = re.compile(r"((^|;)\s*charset=)([^;]*)", re.M)

    original_value: str
    
    def __new__(cls, original_value):
        match = cls.CHARSET_RE.search(original_value)
        if match is None:
            # No substitution necessary.
            return str.__new__(str, original_value)

        obj = str.__new__(cls, original_value)
        obj.original_value = original_value
        return obj

    def substitute_encoding(self, eventual_encoding="utf-8") -> str:
        """When an HTML document is being encoded to a given encoding, the
        value of the ``charset=`` in a ``<meta>`` tag's ``content`` becomes
        the name of the encoding.
        """
        if eventual_encoding in PYTHON_SPECIFIC_ENCODINGS:
            return ''
        def rewrite(match):
            return match.group(1) + eventual_encoding
        return self.CHARSET_RE.sub(rewrite, self.original_value)


class PageElement(object):
    """An abstract class representing a single element in the parse tree.

    `NavigableString`, `Tag`, etc. are all subclasses of
    `PageElement`. For this reason you'll see a lot of methods that
    return `PageElement`, but you'll never see an actual `PageElement`
    object. For the most part you can think of `PageElement` as
    meaning "a `Tag` or a `NavigableString`."
    """

    #: In general, we can't tell just by looking at an element whether
    #: it's contained in an XML document or an HTML document. But for
    #: `Tag` objects (q.v.) we can store this information at parse time.
    #: :meta private:
    known_xml: Optional[bool] = None

    _decomposed: bool
    
    def setup(self, parent=None, previous_element=None, next_element=None,
              previous_sibling=None, next_sibling=None):
        """Sets up the initial relations between this element and
        other elements.

        :param parent: The parent of this element.

        :param previous_element: The element parsed immediately before
            this one.

        :param next_element: The element parsed immediately before
            this one.

        :param previous_sibling: The most recently encountered element
            on the same level of the parse tree as this one.

        :param previous_sibling: The next element to be encountered
            on the same level of the parse tree as this one.
        """
        self.parent = parent

        self.previous_element = previous_element
        if previous_element is not None:
            self.previous_element.next_element = self

        self.next_element = next_element
        if self.next_element is not None:
            self.next_element.previous_element = self

        self.next_sibling = next_sibling
        if self.next_sibling is not None:
            self.next_sibling.previous_sibling = self

        if (previous_sibling is None
            and self.parent is not None and self.parent.contents):
            previous_sibling = self.parent.contents[-1]

        self.previous_sibling = previous_sibling
        if previous_sibling is not None:
            self.previous_sibling.next_sibling = self

    def format_string(self, s, formatter):
        """Format the given string using the given formatter.

        :param s: A string.
        :param formatter: A Formatter object, or a string naming one of the standard formatters.
        """
        if formatter is None:
            return s
        if not isinstance(formatter, Formatter):
            formatter = self.formatter_for_name(formatter)
        output = formatter.substitute(s)
        return output

    def formatter_for_name(self, formatter):
        """Look up or create a Formatter for the given identifier,
        if necessary.

        :param formatter: Can be a Formatter object (used as-is), a
            function (used as the entity substitution hook for an
            XMLFormatter or HTMLFormatter), or a string (used to look
            up an XMLFormatter or HTMLFormatter in the appropriate
            registry.
        """
        if isinstance(formatter, Formatter):
            return formatter
        if self._is_xml:
            c = XMLFormatter
        else:
            c = HTMLFormatter
        if isinstance(formatter, Callable):
            return c(entity_substitution=formatter)
        return c.REGISTRY[formatter]

    @property
    def _is_xml(self):
        """Is this element part of an XML tree or an HTML tree?

        This is used in formatter_for_name, when deciding whether an
        XMLFormatter or HTMLFormatter is more appropriate. It can be
        inefficient, but it should be called very rarely.
        """
        if self.known_xml is not None:
            # Most of the time we will have determined this when the
            # document is parsed.
            return self.known_xml

        # Otherwise, it's likely that this element was created by
        # direct invocation of the constructor from within the user's
        # Python code.
        if self.parent is None:
            # This is the top-level object. It should have .known_xml set
            # from tree creation. If not, take a guess--BS is usually
            # used on HTML markup.
            return getattr(self, 'is_xml', False)
        return self.parent._is_xml

    nextSibling = _alias("next_sibling")  #: :meta private: BS3
    previousSibling = _alias("previous_sibling")  #: :meta private: BS3

    default: Iterable[type] = tuple() #: :meta private:
    def _all_strings(self, strip=False, types:Iterable[type]=default):
        """Yield all strings of certain classes, possibly stripping them.

        This is implemented differently in Tag and NavigableString.
        """
        raise NotImplementedError()

    @property
    def stripped_strings(self) -> Iterator[Union[NavigableString, CData]]:
        """Yield all interesting strings in this PageElement, stripping them
        first.

        See `Tag` for information on which strings are considered
        interesting in a given context.
        """
        for string in self._all_strings(True):
            yield string

    def get_text(self, separator:str="", strip:bool=False,
                 types:Iterable[type]=default) -> str:
        """Get all child strings of this PageElement, concatenated using the
        given separator.

        :param separator: Strings will be concatenated using this separator.

        :param strip: If True, strings will be stripped before being
            concatenated.

        :param types: A tuple of NavigableString subclasses. Any
            strings of a subclass not found in this list will be
            ignored. Although there are exceptions, the default
            behavior in most cases is to consider only NavigableString
            and CData objects. That means no comments, processing
            instructions, etc.

        :return: A string.
        """
        return separator.join([s for s in self._all_strings(
                    strip, types=types)])
    getText = get_text
    text = property(get_text)

    def replace_with(self, *args:Iterable[PageElement]) -> PageElement:
        """Replace this `PageElement` with one or more other `PageElements`,
        keeping the rest of the tree the same.

        :return: This object, no longer part of the tree.
        """
        if self.parent is None:
            raise ValueError(
                "Cannot replace one element with another when the "
                "element to be replaced is not part of a tree.")
        if len(args) == 1 and args[0] is self:
            # Replacing an element with itself is a no-op.
            return self
        if any(x is self.parent for x in args):
            raise ValueError("Cannot replace a Tag with its parent.")
        old_parent = self.parent
        my_index = self.parent.index(self)
        self.extract(_self_index=my_index)
        for idx, replace_with in enumerate(args, start=my_index):
            old_parent.insert(idx, replace_with)
        return self
    replaceWith = replace_with  #: :meta private: BS3

    def unwrap(self):
        """Replace this `PageElement` with its contents.

        :return: This object, no longer part of the tree.
        """
        my_parent = self.parent
        if self.parent is None:
            raise ValueError(
                "Cannot replace an element with its contents when that"
                "element is not part of a tree.")
        my_index = self.parent.index(self)
        self.extract(_self_index=my_index)
        for child in reversed(self.contents[:]):
            my_parent.insert(my_index, child)
        return self
    replace_with_children = unwrap
    replaceWithChildren = unwrap  #: :meta private: BS3

    def wrap(self, wrap_inside:Tag) -> Tag:
        """Wrap this `PageElement` inside a `Tag`.

        :return: ``wrap_inside``, occupying the position in the tree that used
           to be occupied by this object, and with this object now inside it.
        """
        me = self.replace_with(wrap_inside)
        wrap_inside.append(me)
        return wrap_inside

    def extract(self, _self_index:Optional[int]=None) -> PageElement:
        """Destructively rips this element out of the tree.

        :param _self_index: The location of this element in its parent's
           .contents, if known. Passing this in allows for a performance
           optimization.

        :return: this `PageElement`, no longer part of the tree.
        """
        if self.parent is not None:
            if _self_index is None:
                _self_index = self.parent.index(self)
            del self.parent.contents[_self_index]

        #Find the two elements that would be next to each other if
        #this element (and any children) hadn't been parsed. Connect
        #the two.
        last_child = self._last_descendant()

        # last_child can't be None because we passed accept_self=True
        # into _last_descendant. Worst case, last_child will be
        # self. Making this cast removes several mypy complaints later
        # on as we manipulate last_child.
        last_child = cast(PageElement, last_child)
        next_element = last_child.next_element

        if self.previous_element is not None:
            if self.previous_element is not next_element:
                self.previous_element.next_element = next_element
        if next_element is not None and next_element is not self.previous_element:
            next_element.previous_element = self.previous_element
        self.previous_element = None
        last_child.next_element = None

        self.parent = None
        if (self.previous_sibling is not None
            and self.previous_sibling is not self.next_sibling):
            self.previous_sibling.next_sibling = self.next_sibling
        if (self.next_sibling is not None
            and self.next_sibling is not self.previous_sibling):
            self.next_sibling.previous_sibling = self.previous_sibling
        self.previous_sibling = self.next_sibling = None
        return self

    def decompose(self) -> None:
        """Recursively destroys this `PageElement` and its children.

        This element will be removed from the tree and wiped out; so
        will everything beneath it.

        The behavior of a decomposed `PageElement` is undefined and you
        should never use one for anything, but if you need to *check*
        whether an element has been decomposed, you can use the
        `PageElement.decomposed` property.
        """
        self.extract()
        i = self
        while i is not None:
            n = i.next_element
            i.__dict__.clear()
            if isinstance(i, Tag):
                i.contents = []
            i._decomposed = True
            i = n

    def _last_descendant(self, is_initialized:bool=True, accept_self:bool=True) -> Optional[PageElement]:
        """Finds the last element beneath this object to be parsed.

        :param is_initialized: Has ``setup()`` been called on this PageElement
            yet?
        :param accept_self: Is ``self`` an acceptable answer to the question?
        """
        if is_initialized and self.next_sibling is not None:
            last_child = self.next_sibling.previous_element
        else:
            last_child = self
            while isinstance(last_child, Tag) and last_child.contents:
                last_child = last_child.contents[-1]
        if not accept_self and last_child is self:
            last_child = None
        return last_child
    #: :meta private: BS3: Not part of the API!
    _lastRecursiveChild = _last_descendant

    def insert_before(self, *args:Iterable[PageElement]) -> None:
        """Makes the given element(s) the immediate predecessor of this one.

        All the elements will have the same `PageElement.parent` as
        this one, and the given elements will occur immediately before
        this one.
        """
        parent = self.parent
        if parent is None:
            raise ValueError(
                "Element has no parent, so 'before' has no meaning.")
        if any(x is self for x in args):
                raise ValueError("Can't insert an element before itself.")
        for predecessor in args:
            # Extract first so that the index won't be screwed up if they
            # are siblings.
            if isinstance(predecessor, PageElement):
                predecessor.extract()
            index = parent.index(self)
            parent.insert(index, predecessor)

    def insert_after(self, *args:Iterable[PageElement]) -> None:
        """Makes the given element(s) the immediate successor of this one.

        The elements will have the same `PageElement.parent` as this
        one, and the given elements will occur immediately after this
        one.
        """
        # Do all error checking before modifying the tree.
        parent = self.parent
        if parent is None:
            raise ValueError(
                "Element has no parent, so 'after' has no meaning.")
        if any(x is self for x in args):
            raise ValueError("Can't insert an element after itself.")

        offset = 0
        for successor in args:
            # Extract first so that the index won't be screwed up if they
            # are siblings.
            if isinstance(successor, PageElement):
                successor.extract()
            index = parent.index(self)
            parent.insert(index+1+offset, successor)
            offset += 1

    def find_next(self, name=None, attrs={}, string=None, **kwargs) -> PageElement:
        """Find the first PageElement that matches the given criteria and
        appears later in the document than this PageElement.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :kwargs: A dictionary of filters on attribute values.
        """
        return self._find_one(self.find_all_next, name, attrs, string, **kwargs)
    findNext = find_next  #: :meta private: BS3

    def find_all_next(self, name=None, attrs={}, string=None, limit=None,
                    **kwargs) -> ResultSet[PageElement]: 
        """Find all `PageElement` objects that match the given criteria and
        appear later in the document than this `PageElement`.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        """
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(name, attrs, string, limit, self.next_elements,
                              _stacklevel=_stacklevel+1, **kwargs)
    findAllNext = find_all_next  #: :meta private: BS3

    def find_next_sibling(self, name=None, attrs={}, string=None, **kwargs) -> PageElement:
        """Find the closest sibling to this PageElement that matches the
        given criteria and appears later in the document.

        All find_* methods take a common set of arguments. See the
        online documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :kwargs: A dictionary of filters on attribute values.
        """
        return self._find_one(self.find_next_siblings, name, attrs, string,
                             **kwargs)
    findNextSibling = find_next_sibling  #: :meta private: BS3

    def find_next_siblings(self, name=None, attrs={}, string=None, limit=None,
                           **kwargs) -> ResultSet[PageElement]:
        """Find all siblings of this PageElement that match the given criteria
        and appear later in the document.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        :return: A ResultSet of PageElements.
        :rtype: bs4.element.ResultSet
        """
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(
            name, attrs, string, limit,
            self.next_siblings, _stacklevel=_stacklevel+1, **kwargs
        )
    findNextSiblings = find_next_siblings   #: :meta private: BS3
    fetchNextSiblings = find_next_siblings  #: :meta private: BS2

    def find_previous(self, name=None, attrs={}, string=None, **kwargs) -> PageElement:
        """Look backwards in the document from this PageElement and find the
        first PageElement that matches the given criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :kwargs: A dictionary of filters on attribute values.
        :return: A PageElement.
        :rtype: bs4.element.Tag | bs4.element.NavigableString
        """
        return self._find_one(
            self.find_all_previous, name, attrs, string, **kwargs)
    findPrevious = find_previous  #: :meta private: BS3

    def find_all_previous(self, name=None, attrs={}, string=None, limit=None,
                        **kwargs) -> ResultSet[PageElement]:
        """Look backwards in the document from this PageElement and find all
        PageElements that match the given criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        :return: A ResultSet of PageElements.
        :rtype: bs4.element.ResultSet
        """
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(
            name, attrs, string, limit, self.previous_elements,
            _stacklevel=_stacklevel+1, **kwargs
        )
    findAllPrevious = find_all_previous  #: :meta private: BS3    
    fetchPrevious = find_all_previous    #: :meta private: BS2

    def find_previous_sibling(self, name=None, attrs={}, string=None, **kwargs) -> PageElement:
        """Returns the closest sibling to this PageElement that matches the
        given criteria and appears earlier in the document.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :kwargs: A dictionary of filters on attribute values.
        """
        return self._find_one(self.find_previous_siblings, name, attrs, string,
                             **kwargs)
    findPreviousSibling = find_previous_sibling  #: :meta private: BS3

    def find_previous_siblings(self, name=None, attrs={}, string=None,
                               limit=None, **kwargs) -> ResultSet[PageElement]:
        """Returns all siblings to this PageElement that match the
        given criteria and appear earlier in the document.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param string: A filter for a NavigableString with specific text.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        :return: A ResultSet of PageElements.
        :rtype: bs4.element.ResultSet
        """
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(
            name, attrs, string, limit,
            self.previous_siblings, _stacklevel=_stacklevel+1, **kwargs
        )
    findPreviousSiblings = find_previous_siblings   #: :meta private: BS3
    fetchPreviousSiblings = find_previous_siblings  #: :meta private: BS2

    def find_parent(self, name=None, attrs={}, **kwargs) -> Optional[PageElement]:
        """Find the closest parent of this PageElement that matches the given
        criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :kwargs: A dictionary of filters on attribute values.

        :return: A PageElement.
        :rtype: bs4.element.Tag | bs4.element.NavigableString
        """
        # NOTE: We can't use _find_one because findParents takes a different
        # set of arguments.
        r = None
        l = self.find_parents(name, attrs, 1, _stacklevel=3, **kwargs)
        if l:
            r = l[0]
        return r
    findParent = find_parent  #: :meta private: BS3

    def find_parents(self, name=None, attrs={}, limit=None, **kwargs) -> ResultSet[PageElement]:
        """Find all parents of this PageElement that match the given criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.

        :return: A PageElement.
        :rtype: bs4.element.Tag | bs4.element.NavigableString
        """
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(name, attrs, None, limit, self.parents,
                              _stacklevel=_stacklevel+1, **kwargs)
    findParents = find_parents   #: :meta private: BS3
    fetchParents = find_parents  #: :meta private: BS2

    @property
    def next(self) -> PageElement:
        """The `PageElement`, if any, that was parsed just after this one.
        """
        return self.next_element

    @property
    def previous(self) -> PageElement:
        """The `PageElement`, if any, that was parsed just before this one.
        """
        return self.previous_element

    #These methods do the real heavy lifting.

    def _find_one(self, method, name, attrs, string, **kwargs):
        r = None
        l = method(name, attrs, string, 1, _stacklevel=4, **kwargs)
        if l:
            r = l[0]
        return r

    def _find_all(self, name, attrs, string, limit, generator, **kwargs):
        "Iterates over a generator looking for things that match."
        _stacklevel = kwargs.pop('_stacklevel', 3)

        if string is None and 'text' in kwargs:
            string = kwargs.pop('text')
            warnings.warn(
                "The 'text' argument to find()-type methods is deprecated. Use 'string' instead.",
                DeprecationWarning, stacklevel=_stacklevel
            )

        if isinstance(name, SoupStrainer):
            strainer = name
        else:
            strainer = SoupStrainer(name, attrs, string, **kwargs)

        if string is None and not limit and not attrs and not kwargs:
            if name is True or name is None:
                # Optimization to find all tags.
                result = (element for element in generator
                          if isinstance(element, Tag))
                return ResultSet(strainer, result)
            elif isinstance(name, str):
                # Optimization to find all tags with a given name.
                if name.count(':') == 1:
                    # This is a name with a prefix. If this is a namespace-aware document,
                    # we need to match the local name against tag.name. If not,
                    # we need to match the fully-qualified name against tag.name.
                    prefix, local_name = name.split(':', 1)
                else:
                    prefix = None
                    local_name = name
                result = (element for element in generator
                          if isinstance(element, Tag)
                          and (
                              element.name == name
                          ) or (
                              element.name == local_name
                              and (prefix is None or element.prefix == prefix)
                          )
                )
                return ResultSet(strainer, result)
        results = ResultSet(strainer)
        while True:
            try:
                i = next(generator)
            except StopIteration:
                break
            if i:
                found = strainer.search(i)
                if found:
                    results.append(found)
                    if limit and len(results) >= limit:
                        break
        return results

    #These generators can be used to navigate starting from both
    #NavigableStrings and Tags.
    @property
    def next_elements(self) -> Iterator[PageElement]:
        """All PageElements that were parsed after this one.
        """
        i = self.next_element
        while i is not None:
            yield i
            i = i.next_element

    @property
    def next_siblings(self) -> Iterator[PageElement]:
        """All PageElements that are siblings of this one but were parsed
        later.
        """
        i = self.next_sibling
        while i is not None:
            yield i
            i = i.next_sibling

    @property
    def previous_elements(self):
        """All PageElements that were parsed before this one.

        :yield: A sequence of PageElements.
        """
        i = self.previous_element
        while i is not None:
            yield i
            i = i.previous_element

    @property
    def previous_siblings(self):
        """All PageElements that are siblings of this one but were parsed
        earlier.

        :yield: A sequence of PageElements.
        """
        i = self.previous_sibling
        while i is not None:
            yield i
            i = i.previous_sibling

    @property
    def parents(self):
        """All PageElements that are parents of this PageElement.

        :yield: A sequence of PageElements.
        """
        i = self.parent
        while i is not None:
            yield i
            i = i.parent

    @property
    def decomposed(self) -> bool:
        """Check whether a PageElement has been decomposed."""
        return getattr(self, '_decomposed', False) or False
   
    # Old non-property versions of the generators, for backwards
    # compatibility with BS3.

    #: :meta private:
    def nextGenerator(self):
        return self.next_elements

    #: :meta private:
    def nextSiblingGenerator(self):
        return self.next_siblings

    #: :meta private:
    def previousGenerator(self):
        return self.previous_elements

    #: :meta private:
    def previousSiblingGenerator(self):
        return self.previous_siblings

    #: :meta private:
    def parentGenerator(self):
        return self.parents


class NavigableString(str, PageElement):
    """A Python string that is part of a parse tree.

    When Beautiful Soup parses the markup ``<b>penguin</b>``, it will
    create a `NavigableString` for the string "penguin".
    """

    PREFIX = ''
    SUFFIX = ''

    def __new__(cls, value:str) -> NavigableString:
        """Create a new NavigableString.

        When unpickling a NavigableString, this method is called with
        the string in DEFAULT_OUTPUT_ENCODING. That encoding needs to be
        passed in to the superclass's __new__ or the superclass won't know
        how to handle non-ASCII characters.
        """
        if isinstance(value, str):
            u = str.__new__(cls, value)
        else:
            u = str.__new__(cls, value, DEFAULT_OUTPUT_ENCODING)
        u.setup()
        return u

    def __deepcopy__(self, memo:dict, recursive:bool=False) -> NavigableString:
        """A copy of a NavigableString has the same contents and class
        as the original, but it is not connected to the parse tree.

        :param recursive: This parameter is ignored; it's only defined
           so that NavigableString.__deepcopy__ implements the same
           signature as Tag.__deepcopy__.
        """
        return type(self)(self)

    def __copy__(self) -> NavigableString:
        """A copy of a NavigableString can only be a deep copy, because
        only one PageElement can occupy a given place in a parse tree.
        """
        return self.__deepcopy__({})

    def __getnewargs__(self):
        return (str(self),)

    @property
    def string(self) -> Optional[str]:
        """Convenience property defined to match `Tag.string`.

        :return: This property always returns the `NavigableString` it was
           called on.
        """
        return self

    def output_ready(self, formatter:Formatter|str="minimal") -> str:
        """Run the string through the provided formatter, making it
        ready for output as part of an HTML or XML document.

        :param formatter: A `Formatter` object, or a string naming one
            of the standard formatters.
        """
        output = self.format_string(self, formatter)
        return self.PREFIX + output + self.SUFFIX

    @property
    def name(self) -> None:
        """Since a NavigableString is not a Tag, it has no .name.

        This property is implemented so that code like this doesn't crash
        when run on a mixture of Tag and NavigableString objects:
            [x.name for x in tag.children]

        :meta private:
        """
        return None

    @name.setter
    def name(self, name:str):
        """Prevent NavigableString.name from ever being set.

        :meta private:
        """
        raise AttributeError("A NavigableString cannot be given a name.")

    def _all_strings(self, strip=False, types:Iterable[type]=PageElement.default) -> Iterator[str]:
        """Yield all strings of certain classes, possibly stripping them.

        This makes it easy for NavigableString to implement methods
        like get_text() as conveniences, creating a consistent
        text-extraction API across all PageElements.

        :param strip: If True, all strings will be stripped before being
            yielded.

        :param types: A tuple of NavigableString subclasses. If this
            NavigableString isn't one of those subclasses, the
            sequence will be empty. By default, the subclasses
            considered are NavigableString and CData objects. That
            means no comments, processing instructions, etc.

        :yield: A sequence that either contains this string, or is empty.
        """
        if types is self.default:
            # This is kept in Tag because it's full of subclasses of
            # this class, which aren't defined until later in the file.
            types = Tag.MAIN_CONTENT_STRING_TYPES

        # Do nothing if the caller is looking for specific types of
        # string, and we're of a different type.
        #
        # We check specific types instead of using isinstance(self,
        # types) because all of these classes subclass
        # NavigableString. Anyone who's using this feature probably
        # wants generic NavigableStrings but not other stuff.
        my_type = type(self)
        if types is not None:
            if isinstance(types, type):
                # Looking for a single type.
                if my_type is not types:
                    return
            elif my_type not in types:
                # Looking for one of a list of types.
                return

        value = self
        if strip:
            final_value = value.strip()
        else:
            final_value = self
        if len(final_value) > 0:
            yield final_value

    @property
    def strings(self) -> Iterator[str]:
        """Yield this string, but only if it is interesting.

        This is defined the way it is for compatibility with
        `Tag.strings`. See `Tag` for information on which strings are
        interesting in a given context.

        :yield: A sequence that either contains this string, or is empty.
        """
        return self._all_strings()

class PreformattedString(NavigableString):
    """A `NavigableString` not subject to the normal formatting rules.

    This is an abstract class used for special kinds of strings such
    as comments (`Comment`) and CDATA blocks (`CData`).
    """

    PREFIX = ''
    SUFFIX = ''

    def output_ready(self, formatter:Optional[str|Formatter]=None) -> str:
        """Make this string ready for output by adding any subclass-specific
            prefix or suffix.

        :param formatter: A `Formatter` object, or a string naming one
            of the standard formatters. The string will be passed into the
            `Formatter`, but only to trigger any side effects: the return
            value is ignored.

        :return: The string, with any subclass-specific prefix and
           suffix added on.
        """
        if formatter is not None:
            ignore = self.format_string(self, formatter)
        return self.PREFIX + self + self.SUFFIX

class CData(PreformattedString):
    """A `CDATA section <https://dev.w3.org/html5/spec-LC/syntax.html#cdata-sections>`_."""
    PREFIX = '<![CDATA['
    SUFFIX = ']]>'

class ProcessingInstruction(PreformattedString):
    """A SGML processing instruction."""

    PREFIX = '<?'
    SUFFIX = '>'

class XMLProcessingInstruction(ProcessingInstruction):
    """An `XML processing instruction <https://www.w3.org/TR/REC-xml/#sec-pi>`_."""
    PREFIX = '<?'
    SUFFIX = '?>'

class Comment(PreformattedString):
    """An `HTML comment <https://dev.w3.org/html5/spec-LC/syntax.html#comments>`_ or `XML comment <https://www.w3.org/TR/REC-xml/#sec-comments>`_."""
    PREFIX = '<!--'
    SUFFIX = '-->'


class Declaration(PreformattedString):
    """An `XML declaration <https://www.w3.org/TR/REC-xml/#sec-prolog-dtd>`_."""
    PREFIX = '<?'
    SUFFIX = '?>'


class Doctype(PreformattedString):
    """A `document type declaration <https://www.w3.org/TR/REC-xml/#dt-doctype>`_."""
    @classmethod
    def for_name_and_ids(cls, name:str, pub_id:str, system_id:str) -> Doctype:
        """Generate an appropriate document type declaration for a given
        public ID and system ID.

        :param name: The name of the document's root element, e.g. 'html'.
        :param pub_id: The Formal Public Identifier for this document type,
            e.g. '-//W3C//DTD XHTML 1.1//EN'
        :param system_id: The system identifier for this document type,
            e.g. 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'
        """
        value = name or ''
        if pub_id is not None:
            value += ' PUBLIC "%s"' % pub_id
            if system_id is not None:
                value += ' "%s"' % system_id
        elif system_id is not None:
            value += ' SYSTEM "%s"' % system_id

        return Doctype(value)

    PREFIX = '<!DOCTYPE '
    SUFFIX = '>\n'


class Stylesheet(NavigableString):
    """A `NavigableString` representing the contents of a `<style> HTML
    tag <https://dev.w3.org/html5/spec-LC/Overview.html#the-style-element>`_
    (probably CSS).

    Used to distinguish embedded stylesheets from textual content.
    """
    pass


class Script(NavigableString):
    """A `NavigableString` representing the contents of a `<script>
    HTML tag
    <https://dev.w3.org/html5/spec-LC/Overview.html#the-script-element>`_
    (probably Javascript).

    Used to distinguish executable code from textual content.
    """
    pass


class TemplateString(NavigableString):
    """A `NavigableString` representing a string found inside an `HTML
    <template> tag <https://html.spec.whatwg.org/multipage/scripting.html#the-template-element>`_ 
    embedded in a larger document.

    Used to distinguish such strings from the main body of the document.
    """
    pass


class RubyTextString(NavigableString):
    """A NavigableString representing the contents of an `<rt> HTML
    tag <https://dev.w3.org/html5/spec-LC/text-level-semantics.html#the-rt-element>`_.

    Can be used to distinguish such strings from the strings they're
    annotating.
    """
    pass


class RubyParenthesisString(NavigableString):
    """A NavigableString representing the contents of an `<rp> HTML
    tag <https://dev.w3.org/html5/spec-LC/text-level-semantics.html#the-rp-element>`_.
    """
    pass


class Tag(PageElement):
    """An HTML or XML tag that is part of a parse tree, along with its
    attributes, contents, and relationships to other parts of the tree.

    When Beautiful Soup parses the markup ``<b>penguin</b>``, it will
    create a `Tag` object representing the ``<b>`` tag. You can
    instantiate `Tag` objects directly, but it's not necessary unless
    you're adding entirely new markup to a parsed document. Most of
    the constructor arguments are intended for use by the `TreeBuilder`
    that's parsing a document.

    :param parser: A `BeautifulSoup` object representing the parse tree this
        `Tag` will be part of.
    :param builder: The `TreeBuilder` being used to build the tree.
    :param name: The name of the tag.
    :param namespace: The URI of this tag's XML namespace, if any.
    :param prefix: The prefix for this tag's XML namespace, if any.
    :param attrs: A dictionary of attribute values.
    :param parent: The `Tag` to use as the parent of this `Tag`. May be
       the `BeautifulSoup` object itself.
    :param previous: The `PageElement` that was parsed immediately before
        parsing this tag.
    :param is_xml: If True, this is an XML tag. Otherwise, this is an
        HTML tag.
    :param sourceline: The line number where this tag was found in its
        source document.
    :param sourcepos: The character position within ``sourceline`` where this
        tag was found.
    :param can_be_empty_element: If True, this tag should be
        represented as <tag/>. If False, this tag should be represented
        as <tag></tag>.
    :param cdata_list_attributes: A dictionary of attributes whose values should
        be parsed as lists of strings if they ever show up on this tag.
    :param preserve_whitespace_tags: Names of tags whose contents
        should have their whitespace preserved if they are encountered inside
        this tag.
    :param interesting_string_types: When iterating over this
        tag's string contesnts in methods like `Tag.strings` or `Tag.get_text`,
        these are the types of strings that are interesting enough
        to be considered. By default, `NavigableString` (normal strings)
        and `CData` (CDATA sections) are the only interesting string subtypes.
    :param namespaces: A dictionary mapping currently active
        namespace prefixes to URIs, as of the point in the parsing process when
        this tag was encountered. This can be used later to
        construct CSS selectors.
    """
    def __init__(self,
                 parser:Optional[BeautifulSoup]=None,
                 builder:Optional[TreeBuilder]=None,
                 name:Optional[str]=None,
                 namespace:Optional[str]=None,
                 prefix:Optional[str]=None,
                 attrs:Optional[_AttributeDict]=None,
                 parent:Optional[Union[BeautifulSoup, Tag]]=None,
                 previous:Optional[PageElement]=None,
                 is_xml:Optional[bool]=None,
                 sourceline:Optional[int]=None,
                 sourcepos:Optional[int]=None,
                 can_be_empty_element:Optional[bool]=None,
                 cdata_list_attributes:Optional[Dict[str, Iterable[str]]]=None,
                 preserve_whitespace_tags:Optional[Iterable[str]]=None,
                 interesting_string_types:Optional[Iterable[type]]=None,
                 namespaces:Optional[Dict[str, str]]=None
    ):
        if parser is None:
            self.parser_class = None
        else:
            # We don't actually store the parser object: that lets extracted
            # chunks be garbage-collected.
            self.parser_class = parser.__class__
        if name is None:
            raise ValueError("No value provided for new tag's name.")
        self.name = name
        self.namespace = namespace
        self._namespaces = namespaces or {}
        self.prefix = prefix
        if ((not builder or builder.store_line_numbers)
            and (sourceline is not None or sourcepos is not None)):
            self.sourceline = sourceline
            self.sourcepos = sourcepos

        if attrs is None:
            self.attrs = dict()
        else:
            if builder is not None and builder.cdata_list_attributes:
                self.attrs = builder._replace_cdata_list_attribute_values(
                    self.name, attrs)
            else:
                self.attrs = dict(attrs)

        # If possible, determine ahead of time whether this tag is an
        # XML tag.
        if builder:
            self.known_xml = builder.is_xml
        else:
            self.known_xml = is_xml
        self.contents: List[PageElement] = []
        self.setup(parent, previous)
        self.hidden = False

        if builder is None:
            # In the absence of a TreeBuilder, use whatever values were
            # passed in here. They're probably None, unless this is a copy of some
            # other tag.
            self.can_be_empty_element = can_be_empty_element
            self.cdata_list_attributes = cdata_list_attributes
            self.preserve_whitespace_tags = preserve_whitespace_tags
            self.interesting_string_types = interesting_string_types
        else:
            # Set up any substitutions for this tag, such as the charset in a META tag.
            builder.set_up_substitutions(self)

            # Ask the TreeBuilder whether this tag might be an empty-element tag.
            self.can_be_empty_element = builder.can_be_empty_element(name)

            # Keep track of the list of attributes of this tag that
            # might need to be treated as a list.
            #
            # For performance reasons, we store the whole data structure
            # rather than asking the question of every tag. Asking would
            # require building a new data structure every time, and
            # (unlike can_be_empty_element), we almost never need
            # to check this.
            self.cdata_list_attributes = builder.cdata_list_attributes

            # Keep track of the names that might cause this tag to be treated as a
            # whitespace-preserved tag.
            self.preserve_whitespace_tags = builder.preserve_whitespace_tags

            if self.name in builder.string_containers:
                # This sort of tag uses a special string container
                # subclass for most of its strings. We need to be able
                # to look up the proper container subclass.
                self.interesting_string_types = builder.string_containers[self.name]
            else:
                self.interesting_string_types = self.MAIN_CONTENT_STRING_TYPES

    # Alias for a dictionary of tag attribute values.
    _AttributeDict = Dict[str, Union[str, Iterable[str]]]
    name: str
    attrs: _AttributeDict
                
    parserClass = _alias("parser_class")  #: :meta private: BS3

    def __deepcopy__(self, memo:dict, recursive:bool=True) -> Tag:
        """A deepcopy of a Tag is a new Tag, unconnected to the parse tree.
        Its contents are a copy of the old Tag's contents.
        """
        clone = self._clone()

        if recursive:
            # Clone this tag's descendants recursively, but without
            # making any recursive function calls.
            tag_stack = [clone]
            for event, element in self._event_stream(self.descendants):
                if event is Tag.END_ELEMENT_EVENT:
                    # Stop appending incoming Tags to the Tag that was
                    # just closed.
                    tag_stack.pop()
                else:
                    descendant_clone = element.__deepcopy__(
                        memo, recursive=False
                    )
                    # Add to its parent's .contents
                    tag_stack[-1].append(descendant_clone)

                    if event is Tag.START_ELEMENT_EVENT:
                        # Add the Tag itself to the stack so that its
                        # children will be .appended to it.
                        tag_stack.append(descendant_clone)
        return clone

    def __copy__(self) -> Tag:
        """A copy of a Tag must always be a deep copy, because a Tag's
        children can only have one parent at a time.
        """
        return self.__deepcopy__({})

    def _clone(self) -> Tag:
        """Create a new Tag just like this one, but with no
        contents and unattached to any parse tree.

        This is the first step in the deepcopy process.
        """
        clone = type(self)(
            None, self.builder, self.name, self.namespace,
            self.prefix, self.attrs, is_xml=self._is_xml,
            sourceline=self.sourceline, sourcepos=self.sourcepos,
            can_be_empty_element=self.can_be_empty_element,
            cdata_list_attributes=self.cdata_list_attributes,
            preserve_whitespace_tags=self.preserve_whitespace_tags,
            interesting_string_types=self.interesting_string_types
        )
        for attr in ('can_be_empty_element', 'hidden'):
            setattr(clone, attr, getattr(self, attr))
        return clone
    
    @property
    def is_empty_element(self) -> bool:
        """Is this tag an empty-element tag? (aka a self-closing tag)

        A tag that has contents is never an empty-element tag.

        A tag that has no contents may or may not be an empty-element
        tag. It depends on the `TreeBuilder` used to create the
        tag. If the builder has a designated list of empty-element
        tags, then only a tag whose name shows up in that list is
        considered an empty-element tag. This is usually the case
        for HTML documents.

        If the builder has no designated list of empty-element, then
        any tag with no contents is an empty-element tag. This is usually
        the case for XML documents.
        """
        return len(self.contents) == 0 and self.can_be_empty_element is True
    isSelfClosing = is_empty_element  #: :meta private: BS3

    @property
    def string(self) -> Optional[str]:
        """Convenience property to get the single string within this
        `Tag`, assuming there is just one.

        :return: If this `Tag` has a single child that's a
         `NavigableString`, the return value is that string. If this
         element has one child `Tag`, the return value is that child's
         `Tag.string`, recursively. If this `Tag` has no children,
         or has more than one child, the return value is ``None``.

         If this property is unexpectedly returning ``None`` for you,
         it's probably because your `Tag` has more than one thing
         inside it.
        """
        if len(self.contents) != 1:
            return None
        child = self.contents[0]
        if isinstance(child, NavigableString):
            return child
        elif isinstance(child, Tag):
            return child.string
        return None

    @string.setter
    def string(self, string:str) -> None:
        """Replace the `Tag.contents` of this `Tag` with a single string."""
        self.clear()
        if isinstance(string, NavigableString):
            new_class = string.__class__
        else:
            new_class = NavigableString
        self.append(new_class(string))

    #: :meta private:
    MAIN_CONTENT_STRING_TYPES = {NavigableString, CData}
    def _all_strings(self, strip:bool=False, types:Iterable[type]=PageElement.default) -> Iterator[str]:
        """Yield all strings of certain classes, possibly stripping them.

        :param strip: If True, all strings will be stripped before being
            yielded.

        :param types: A tuple of NavigableString subclasses. Any strings of
            a subclass not found in this list will be ignored. By
            default, the subclasses considered are the ones found in
            self.interesting_string_types. If that's not specified,
            only NavigableString and CData objects will be
            considered. That means no comments, processing
            instructions, etc.
        """
        if types is self.default:
            if self.interesting_string_types is None:
                types = self.MAIN_CONTENT_STRING_TYPES
            else:
                types = self.interesting_string_types

        for descendant in self.descendants:
            if not isinstance(descendant, NavigableString):
                continue
            descendant_type = type(descendant)
            if isinstance(types, type):
                if descendant_type is not types:
                    # We're not interested in strings of this type.
                    continue
            elif types is not None and descendant_type not in types:
                # We're not interested in strings of this type.
                continue
            if strip:
                stripped = descendant.strip()
                if len(stripped) == 0:
                    continue
                yield stripped
            else:
                yield descendant
    strings = property(_all_strings)

    def insert(self, position:int, new_child:PageElement) -> None:
        """Insert a new PageElement as a child of this `Tag`.

        This works the same way as :py:meth:`list.insert`.

        :param position: The numeric position that should be occupied
           in this Tag's `Tag.children` by the new `PageElement`.
        """
        if new_child is None:
            raise ValueError("Cannot insert None into a tag.")
        if new_child is self:
            raise ValueError("Cannot insert a tag into itself.")
        if (isinstance(new_child, str)
            and not isinstance(new_child, NavigableString)):
            new_child = NavigableString(new_child)

        from bs4 import BeautifulSoup
        if isinstance(new_child, BeautifulSoup):
            # We don't want to end up with a situation where one BeautifulSoup
            # object contains another. Insert the children one at a time.
            for subchild in list(new_child.contents):
                self.insert(position, subchild)
                position += 1
            return
        position = min(position, len(self.contents))
        if hasattr(new_child, 'parent') and new_child.parent is not None:
            # We're 'inserting' an element that's already one
            # of this object's children.
            if new_child.parent is self:
                current_index = self.index(new_child)
                if current_index < position:
                    # We're moving this element further down the list
                    # of this object's children. That means that when
                    # we extract this element, our target index will
                    # jump down one.
                    position -= 1
            new_child.extract()

        new_child.parent = self
        previous_child = None
        if position == 0:
            new_child.previous_sibling = None
            new_child.previous_element = self
        else:
            previous_child = self.contents[position - 1]
            new_child.previous_sibling = previous_child
            new_child.previous_sibling.next_sibling = new_child
            new_child.previous_element = previous_child._last_descendant(False)
        if new_child.previous_element is not None:
            new_child.previous_element.next_element = new_child

        new_childs_last_element = new_child._last_descendant(
            is_initialized=False, accept_self=True
        )
        # new_childs_last_element can't be None because we passed
        # accept_self=True into _last_descendant. Worst case,
        # new_childs_last_element will be new_child itself. Making
        # this cast removes several mypy complaints later on as we
        # manipulate new_childs_last_element.
        new_childs_last_element = cast(PageElement, new_childs_last_element)
        
        if position >= len(self.contents):
            new_child.next_sibling = None

            parent = self
            parents_next_sibling = None
            while parents_next_sibling is None and parent is not None:
                parents_next_sibling = parent.next_sibling
                parent = parent.parent
                if parents_next_sibling is not None:
                    # We found the element that comes next in the document.
                    break
            if parents_next_sibling is not None:
                new_childs_last_element.next_element = parents_next_sibling
            else:
                # The last element of this tag is the last element in
                # the document.
                new_childs_last_element.next_element = None
        else:
            next_child = self.contents[position]
            new_child.next_sibling = next_child
            if new_child.next_sibling is not None:
                new_child.next_sibling.previous_sibling = new_child
            new_childs_last_element.next_element = next_child

        if new_childs_last_element.next_element is not None:
            new_childs_last_element.next_element.previous_element = new_childs_last_element
        self.contents.insert(position, new_child)
    
    def append(self, tag:PageElement) -> None:
        """Appends the given `PageElement` to the contents of this `Tag`.
        """
        self.insert(len(self.contents), tag)

    def extend(self, tags:Iterable[PageElement]|Tag) -> None:
        """Appends one or more objects to the contents of this
        `Tag`.

        :param tags: If a list of `PageElement` objects is provided,
            they will be appended to this tag's contents, one at a time.
            If a single `Tag` is provided, its `Tag.contents` will be
            used to extend this object's `Tag.contents`.
        """
        tag_list: Iterable[PageElement]
        if isinstance(tags, Tag):
            tag_list = tags.contents
        elif isinstance(tags, PageElement):
            # The caller should really be using append() instead,
            # but we can make it work.
            warnings.warn(
                "A single item was passed into Tag.extend. Use Tag.append instead.",
                stacklevel=2
            )
            tag_list = [tags]
        elif isinstance(tags, list):
            tag_list = tags

        if isinstance(tag_list, list):
            # Moving items around the tree may change their position in
            # the original list. Make a list that won't change.
            tag_list = list(tag_list)
        for tag in tag_list:
            self.append(tag)
    
    def clear(self, decompose:bool=False) -> None:
        """Destroy all children of this `Tag` by calling
           `PageElement.extract` on them.

        :param decompose: If this is True, `PageElement.decompose` (a
            more destructive method) will be called instead of
            `PageElement.extract`.
        """
        for element in self.contents[:]:
            if decompose:
                element.decompose()
            else:
                element.extract()

    def smooth(self) -> None:
        """Smooth out the children of this `Tag` by consolidating consecutive
        strings.

        If you perform a lot of operations that modify the tree,
        calling this method afterwards can make pretty-printed output
        look more natural.
        """
        # Mark the first position of every pair of children that need
        # to be consolidated.  Do this rather than making a copy of
        # self.contents, since in most cases very few strings will be
        # affected.
        marked = []
        for i, a in enumerate(self.contents):
            if isinstance(a, Tag):
                # Recursively smooth children.
                a.smooth()
            if i == len(self.contents)-1:
                # This is the last item in .contents, and it's not a
                # tag. There's no chance it needs any work.
                continue
            b = self.contents[i+1]
            if (isinstance(a, NavigableString)
                and isinstance(b, NavigableString)
                and not isinstance(a, PreformattedString)
                and not isinstance(b, PreformattedString)
            ):
                marked.append(i)

        # Go over the marked positions in reverse order, so that
        # removing items from .contents won't affect the remaining
        # positions.
        for i in reversed(marked):
            a = cast(NavigableString, self.contents[i])
            b = cast(NavigableString, self.contents[i+1])
            b.extract()
            n = NavigableString(a+b)
            a.replace_with(n)

    def index(self, element:PageElement) -> int:
        """Find the index of a child of this `Tag` (by identity, not value).

        Doing this by identity avoids issues when a `Tag` contains two
        children that have string equality.

        :param element: Look for this `PageElement` in this object's contents.
        """
        for i, child in enumerate(self.contents):
            if child is element:
                return i
        raise ValueError("Tag.index: element not in tag")

    def get(self, key:str,
            default:Optional[Union[str, List[str]]]=None) -> Optional[Union[str, List[str]]]:
        """Returns the value of the 'key' attribute for the tag, or
        the value given for 'default' if it doesn't have that
        attribute.

        :param key: The attribute to look for.
        :param default: Use this value if the attribute is not present
            on this `Tag`.
        """
        return self.attrs.get(key, default)

    def get_attribute_list(self, key:str,
                           default:Optional[List[str]]=None) -> List[str]:
        """The same as get(), but always returns a list.

        :param key: The attribute to look for.
        :param default: Use this value if the attribute is not present
            on this `Tag`.
        :return: A list of strings, probably containing only a single
            value.
        """
        value = self.get(key, default)
        if value is None:
            value = []
        elif not isinstance(value, list):
            value = [value]
        return value

    def has_attr(self, key:str) -> bool:
        """Does this `Tag` have an attribute with the given name?"""
        return key in self.attrs

    def __hash__(self):
        return str(self).__hash__()

    def __getitem__(self, key):
        """tag[key] returns the value of the 'key' attribute for the Tag,
        and throws an exception if it's not there."""
        return self.attrs[key]

    def __iter__(self):
        "Iterating over a Tag iterates over its contents."
        return iter(self.contents)

    def __len__(self):
        "The length of a Tag is the length of its list of contents."
        return len(self.contents)

    def __contains__(self, x):
        return x in self.contents

    def __bool__(self):
        "A tag is non-None even if it has no contents."
        return True

    def __setitem__(self, key, value):
        """Setting tag[key] sets the value of the 'key' attribute for the
        tag."""
        self.attrs[key] = value

    def __delitem__(self, key):
        "Deleting tag[key] deletes all 'key' attributes for the tag."
        self.attrs.pop(key, None)

    def __call__(self, *args, **kwargs):
        """Calling a Tag like a function is the same as calling its
        find_all() method. Eg. tag('a') returns a list of all the A tags
        found within this tag."""
        return self.find_all(*args, **kwargs)

    def __getattr__(self, subtag):
        """Calling tag.subtag is the same as calling tag.find(name="subtag")"""
        #print("Getattr %s.%s" % (self.__class__, tag))
        if len(subtag) > 3 and subtag.endswith('Tag'):
            # BS3: soup.aTag -> "soup.find("a")
            tag_name = subtag[:-3]
            warnings.warn(
                '.%(name)sTag is deprecated, use .find("%(name)s") instead. If you really were looking for a tag called %(name)sTag, use .find("%(name)sTag")' % dict(
                    name=tag_name
                ),
                DeprecationWarning, stacklevel=2
            )
            return self.find(tag_name)
        # We special case contents to avoid recursion.
        elif not subtag.startswith("__") and not subtag == "contents":
            return self.find(subtag)
        raise AttributeError(
            "'%s' object has no attribute '%s'" % (self.__class__, subtag))

    def __eq__(self, other):
        """Returns true iff this Tag has the same name, the same attributes,
        and the same contents (recursively) as `other`."""
        if self is other:
            return True
        if (not hasattr(other, 'name') or
            not hasattr(other, 'attrs') or
            not hasattr(other, 'contents') or
            self.name != other.name or
            self.attrs != other.attrs or
            len(self) != len(other)):
            return False
        for i, my_child in enumerate(self.contents):
            if my_child != other.contents[i]:
                return False
        return True

    def __ne__(self, other):
        """Returns true iff this Tag is not identical to `other`,
        as defined in __eq__."""
        return not self == other

    def __repr__(self) -> str:
        """Renders this `Tag` as a string."""
        return self.decode()

    def __unicode__(self):
        """Renders this `Tag` as a string."""
        return self.decode()

    __str__ = __repr__ = __unicode__

    def encode(self, encoding:str=DEFAULT_OUTPUT_ENCODING,
               indent_level:Optional[int]=None,
               formatter:Formatter|str="minimal",
               errors:str="xmlcharrefreplace") -> bytes:
        """Render this `Tag` and its contents as a bytestring.

        :param encoding: The encoding to use when converting to
           a bytestring. This may also affect the text of the document,
           specifically any encoding declarations within the document.
        :param indent_level: Each line of the rendering will be
           indented this many levels. (The ``formatter`` decides what a
           'level' means, in terms of spaces or other characters
           output.) This is used internally in recursive calls while
           pretty-printing.
        :param formatter: Either a `Formatter` object, or a string naming one of
            the standard formatters.
        :param errors: An error handling strategy such as
            'xmlcharrefreplace'. This value is passed along into
            :py:meth:`str.encode` and its value should be one of the `error
            handling constants defined by Python's codecs module
            <https://docs.python.org/3/library/codecs.html#error-handlers>`_.
        """
        # Turn the data structure into Unicode, then encode the
        # Unicode.
        u = self.decode(indent_level, encoding, formatter)
        return u.encode(encoding, errors)

    def decode(self, indent_level:Optional[int]=None,
               eventual_encoding:str=DEFAULT_OUTPUT_ENCODING,
               formatter:Formatter|str="minimal",
               iterator:Optional[Iterable]=None) -> str:
        """Render this `Tag` and its contents as a Unicode string.

        :param indent_level: Each line of the rendering will be
           indented this many levels. (The ``formatter`` decides what a
           'level' means, in terms of spaces or other characters
           output.) This is used internally in recursive calls while
           pretty-printing.
        :param encoding: The encoding you intend to use when
           converting the string to a bytestring. decode() is *not*
           responsible for performing that encoding. This information
           is needed so that a real encoding can be substituted in if
           the document contains an encoding declaration (e.g. in a
           <meta> tag).
        :param formatter: Either a `Formatter` object, or a string
            naming one of the standard formatters.
        :param iterator: The iterator to use when navigating over the
            parse tree. This is only used by `Tag.decode_contents` and
            you probably won't need to use it.

        """
        pieces = []
        # First off, turn a non-Formatter `formatter` into a Formatter
        # object. This will stop the lookup from happening over and
        # over again.
        if not isinstance(formatter, Formatter):
            formatter = self.formatter_for_name(formatter)

        if indent_level is True:
            indent_level = 0

        # The currently active tag that put us into string literal
        # mode. Until this element is closed, children will be treated
        # as string literals and not pretty-printed. String literal
        # mode is turned on immediately after this tag begins, and
        # turned off immediately before it's closed. This means there
        # will be whitespace before and after the tag itself.
        string_literal_tag = None

        for event, element in self._event_stream(iterator):
            if event in (Tag.START_ELEMENT_EVENT, Tag.EMPTY_ELEMENT_EVENT):
                piece = element._format_tag(
                    eventual_encoding, formatter, opening=True
                )
            elif event is Tag.END_ELEMENT_EVENT:
                piece = element._format_tag(
                    eventual_encoding, formatter, opening=False
                )
                if indent_level is not None:
                    indent_level -= 1
            else:
                piece = element.output_ready(formatter)

            # Now we need to apply the 'prettiness' -- extra
            # whitespace before and/or after this tag. This can get
            # complicated because certain tags, like <pre> and
            # <script>, can't be prettified, since adding whitespace would
            # change the meaning of the content.

            # The default behavior is to add whitespace before and
            # after an element when string literal mode is off, and to
            # leave things as they are when string literal mode is on.
            if string_literal_tag:
                indent_before = indent_after = False
            else:
                indent_before = indent_after = True

            # The only time the behavior is more complex than that is
            # when we encounter an opening or closing tag that might
            # put us into or out of string literal mode.
            if (event is Tag.START_ELEMENT_EVENT
                and not string_literal_tag
                and not element._should_pretty_print()):
                    # We are about to enter string literal mode. Add
                    # whitespace before this tag, but not after. We
                    # will stay in string literal mode until this tag
                    # is closed.
                    indent_before = True
                    indent_after = False
                    string_literal_tag = element
            elif (event is Tag.END_ELEMENT_EVENT
                  and element is string_literal_tag):
                # We are about to exit string literal mode by closing
                # the tag that sent us into that mode. Add whitespace
                # after this tag, but not before.
                indent_before = False
                indent_after = True
                string_literal_tag = None

            # Now we know whether to add whitespace before and/or
            # after this element.
            if indent_level is not None:
                if (indent_before or indent_after):
                    if isinstance(element, NavigableString):
                        piece = piece.strip()
                    if piece:
                        piece = self._indent_string(
                            piece, indent_level, formatter,
                            indent_before, indent_after
                        )
                if event == Tag.START_ELEMENT_EVENT:
                    indent_level += 1
            pieces.append(piece)
        return "".join(pieces)

    # Names for the different events yielded by _event_stream
    START_ELEMENT_EVENT = object() #: :meta private:
    END_ELEMENT_EVENT = object() #: :meta private:
    EMPTY_ELEMENT_EVENT = object() #: :meta private:
    STRING_ELEMENT_EVENT = object() #: :meta private:

    def _event_stream(self, iterator=None):
        """Yield a sequence of events that can be used to reconstruct the DOM
        for this element.

        This lets us recreate the nested structure of this element
        (e.g. when formatting it as a string) without using recursive
        method calls.

        This is similar in concept to the SAX API, but it's a simpler
        interface designed for internal use. The events are different
        from SAX and the arguments associated with the events are Tags
        and other Beautiful Soup objects.

        :param iterator: An alternate iterator to use when traversing
         the tree.
        """
        tag_stack = []

        iterator = iterator or self.self_and_descendants

        for c in iterator:
            # If the parent of the element we're about to yield is not
            # the tag currently on the stack, it means that the tag on
            # the stack closed before this element appeared.
            while tag_stack and c.parent != tag_stack[-1]:
                now_closed_tag = tag_stack.pop()
                yield Tag.END_ELEMENT_EVENT, now_closed_tag

            if isinstance(c, Tag):
                if c.is_empty_element:
                    yield Tag.EMPTY_ELEMENT_EVENT, c
                else:
                    yield Tag.START_ELEMENT_EVENT, c
                    tag_stack.append(c)
                    continue
            else:
                yield Tag.STRING_ELEMENT_EVENT, c

        while tag_stack:
            now_closed_tag = tag_stack.pop()
            yield Tag.END_ELEMENT_EVENT, now_closed_tag

    def _indent_string(self, s, indent_level, formatter,
                       indent_before, indent_after):
        """Add indentation whitespace before and/or after a string.

        :param s: The string to amend with whitespace.
        :param indent_level: The indentation level; affects how much
           whitespace goes before the string.
        :param indent_before: Whether or not to add whitespace
           before the string.
        :param indent_after: Whether or not to add whitespace
           (a newline) after the string.
        """
        space_before = ''
        if indent_before and indent_level:
            space_before = (formatter.indent * indent_level)

        space_after = ''
        if indent_after:
            space_after = "\n"

        return space_before + s + space_after

    def _format_tag(self, eventual_encoding, formatter, opening):
        # A tag starts with the < character (see below).

        # Then the / character, if this is a closing tag.
        closing_slash = ''
        if not opening:
            closing_slash = '/'

        # Then an optional namespace prefix.
        prefix = ''
        if self.prefix:
            prefix = self.prefix + ":"

        # Then a list of attribute values, if this is an opening tag.
        attribute_string = ''
        if opening:
            attributes = formatter.attributes(self)
            attrs = []
            for key, val in attributes:
                if val is None:
                    decoded = key
                else:
                    if isinstance(val, list) or isinstance(val, tuple):
                        val = ' '.join(val)
                    elif not isinstance(val, str):
                        val = str(val)
                    elif (
                            isinstance(val, AttributeValueWithCharsetSubstitution)
                            and eventual_encoding is not None
                    ):
                        val = val.substitute_encoding(eventual_encoding)

                    text = formatter.attribute_value(val)
                    decoded = (
                        str(key) + '='
                        + formatter.quoted_attribute_value(text))
                attrs.append(decoded)
            if attrs:
                attribute_string = ' ' + ' '.join(attrs)

        # Then an optional closing slash (for a void element in an
        # XML document).
        void_element_closing_slash = ''
        if self.is_empty_element:
            void_element_closing_slash = formatter.void_element_close_prefix or ''

        # Put it all together.
        return '<' + closing_slash + prefix + self.name + attribute_string + void_element_closing_slash + '>'

    def _should_pretty_print(self, indent_level=1):
        """Should this tag be pretty-printed?

        Most of them should, but some (such as <pre> in HTML
        documents) should not.
        """
        return (
            indent_level is not None
            and (
                not self.preserve_whitespace_tags
                or self.name not in self.preserve_whitespace_tags
            )
        )

    def prettify(self, encoding:Optional[str]=None,
                 formatter:Formatter|str="minimal") -> Union[str, bytes]:
        """Pretty-print this `Tag` as a string or bytestring.

        :param encoding: The encoding of the string.
        :param formatter: A Formatter object, or a string naming one of
            the standard formatters.
        :return: A string (if no ``encoding`` is provided) or a bytestring
            (otherwise).
        """
        if encoding is None:
            return self.decode(True, formatter=formatter)
        else:
            return self.encode(encoding, True, formatter=formatter)

    def decode_contents(self, indent_level:Optional[int]=None,
                       eventual_encoding:str=DEFAULT_OUTPUT_ENCODING,
                       formatter:Formatter|str="minimal"):
        """Renders the contents of this tag as a Unicode string.

        :param indent_level: Each line of the rendering will be
           indented this many levels. (The formatter decides what a
           'level' means in terms of spaces or other characters
           output.) Used internally in recursive calls while
           pretty-printing.

        :param eventual_encoding: The tag is destined to be
           encoded into this encoding. decode_contents() is *not*
           responsible for performing that encoding. This information
           is needed so that a real encoding can be substituted in if
           the document contains an encoding declaration (e.g. in a
           <meta> tag).

        :param formatter: A `Formatter` object, or a string naming one of
            the standard Formatters.
        """
        return self.decode(indent_level, eventual_encoding, formatter,
                           iterator=self.descendants)

    def encode_contents(
        self, indent_level:Optional[int]=None,
            encoding:str=DEFAULT_OUTPUT_ENCODING,
            formatter:Formatter|str="minimal") -> bytes:
        """Renders the contents of this PageElement as a bytestring.

        :param indent_level: Each line of the rendering will be
           indented this many levels. (The ``formatter`` decides what a
           'level' means, in terms of spaces or other characters
           output.) This is used internally in recursive calls while
           pretty-printing.
        :param formatter: Either a `Formatter` object, or a string naming one of
            the standard formatters.
        :param encoding: The bytestring will be in this encoding.
        """
        contents = self.decode_contents(indent_level, encoding, formatter)
        return contents.encode(encoding)

    # Old method for BS3 compatibility
    def renderContents(self, encoding=DEFAULT_OUTPUT_ENCODING,
                       prettyPrint=False, indentLevel=0):
        """Deprecated method for BS3 compatibility.

        :meta private:
        """
        if not prettyPrint:
            indentLevel = None
        return self.encode_contents(
            indent_level=indentLevel, encoding=encoding)

    #Soup methods

    def find(self, name=None, attrs={}, recursive=True, string=None,
             **kwargs):
        """Look in the children of this PageElement and find the first
        PageElement that matches the given criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param recursive: If this is True, find() will perform a
            recursive search of this PageElement's children. Otherwise,
            only the direct children will be considered.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        :return: A PageElement.
        :rtype: bs4.element.Tag | bs4.element.NavigableString
        """
        r = None
        l = self.find_all(name, attrs, recursive, string, 1, _stacklevel=3,
                          **kwargs)
        if l:
            r = l[0]
        return r
    findChild = find #BS2

    def find_all(self, name=None, attrs={}, recursive=True, string=None,
                 limit=None, **kwargs):
        """Look in the children of this PageElement and find all
        PageElements that match the given criteria.

        All find_* methods take a common set of arguments. See the online
        documentation for detailed explanations.

        :param name: A filter on tag name.
        :param attrs: A dictionary of filters on attribute values.
        :param recursive: If this is True, find_all() will perform a
            recursive search of this PageElement's children. Otherwise,
            only the direct children will be considered.
        :param limit: Stop looking after finding this many results.
        :kwargs: A dictionary of filters on attribute values.
        :return: A ResultSet of PageElements.
        :rtype: bs4.element.ResultSet
        """
        generator = self.descendants
        if not recursive:
            generator = self.children
        _stacklevel = kwargs.pop('_stacklevel', 2)
        return self._find_all(name, attrs, string, limit, generator,
                              _stacklevel=_stacklevel+1, **kwargs)
    findAll = find_all       #: :meta private: BS3
    findChildren = find_all  #: :meta private: BS2

    #Generator methods
    @property
    def children(self) -> Iterator[PageElement]:
        """Iterate over all direct children of this PageElement.

        :yield: A sequence of PageElements.
        """
        # return iter() to make the purpose of the method clear
        return iter(self.contents)  # XXX This seems to be untested.

    @property
    def self_and_descendants(self) -> Iterator[PageElement]:
        """Iterate over this `Tag` and its children in a
        breadth-first sequence.
        """
        if not self.hidden:
            yield self
        for i in self.descendants:
            yield i

    @property
    def descendants(self) -> Iterator[PageElement]:
        """Iterate over all children of this `Tag` in a
        breadth-first sequence.
        """
        if not len(self.contents):
            return
        stopNode = self._last_descendant().next_element
        current = self.contents[0]
        while current is not stopNode:
            yield current
            current = current.next_element

    # CSS selector code
    def select_one(self, selector, namespaces=None, **kwargs):
        """Perform a CSS selection operation on the current element.

        :param selector: A CSS selector.

        :param namespaces: A dictionary mapping namespace prefixes
           used in the CSS selector to namespace URIs. By default,
           Beautiful Soup will use the prefixes it encountered while
           parsing the document.

        :param kwargs: Keyword arguments to be passed into Soup Sieve's
           soupsieve.select() method.

        :return: A Tag.
        :rtype: bs4.element.Tag
        """
        return self.css.select_one(selector, namespaces, **kwargs)

    def select(self, selector, namespaces=None, limit=None, **kwargs):
        """Perform a CSS selection operation on the current element.

        This uses the SoupSieve library.

        :param selector: A string containing a CSS selector.

        :param namespaces: A dictionary mapping namespace prefixes
           used in the CSS selector to namespace URIs. By default,
           Beautiful Soup will use the prefixes it encountered while
           parsing the document.

        :param limit: After finding this number of results, stop looking.

        :param kwargs: Keyword arguments to be passed into SoupSieve's
           soupsieve.select() method.

        :return: A ResultSet of Tags.
        :rtype: bs4.element.ResultSet
        """
        return self.css.select(selector, namespaces, limit, **kwargs)

    @property
    def css(self) -> CSS:
        """Return an interface to the CSS selector API."""
        return CSS(self)

    # Old names for backwards compatibility
    def childGenerator(self):
        """Deprecated generator.
        :meta private:
        """
        return self.children

    def recursiveChildGenerator(self):
        """Deprecated generator.
        :meta private:
        """
        return self.descendants

    def has_key(self, key):
        """Deprecated method. This was kind of misleading because has_key()
        (attributes) was different from __in__ (contents).

        has_key() is gone in Python 3, anyway.
        :meta private:
        """
        warnings.warn(
            'has_key is deprecated. Use has_attr(key) instead.',
            DeprecationWarning, stacklevel=2
        )
        return self.has_attr(key)

# Define some type aliases to represent the many possibilities for
# matching bits of a parse tree.
#
# This is very complicated because we're applying a formal type system
# to some very DWIM code.

# TODO In Python 3.10 we can use TypeAlias for this stuff. We can
# also use Pattern[str] instead of just Pattern.

# A function that takes a Tag and returns a yes-or-no answer.
_ElementFunction = CallableType[[Tag], bool]

# A function that takes a single attribute value and returns a
# yes-or-no answer.
_AttributeFunction = CallableType[[str], bool]

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



# Next, a couple classes to represent queries and their results.
class SoupStrainer(object):
    """Encapsulates a number of ways of matching a markup element (tag or
    string).

    This is primarily used to underpin the find_* methods, but you can
    create one yourself and pass it in as ``parse_only`` to the
    `BeautifulSoup` constructor, to parse a subset of a large
    document.
    """
    name: _NormalizedStrainableAttribute
    attrs: dict[str, _NormalizedStrainableElement]
    string: _NormalizedStrainableAttribute
                              
    def __init__(self,
                 name:Optional[_StrainableElement]=None,
                 attrs:Union[_StrainableAttribute,
                             Dict[str, _StrainableAttribute]] = {},
                 string:Optional[_StrainableAttribute]=None,
                 **kwargs: dict[str, _StrainableAttribute]) -> None:
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
        if (isinstance(value, str) or isinstance(value, Callable) or hasattr(value, 'match')
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
            isinstance(self.name, Callable)
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

        if isinstance(match_against, Callable):
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

_PageElementT = TypeVar("_PageElementT", bound=PageElement)
class ResultSet(List[_PageElementT], Generic[_PageElementT]):
    """A ResultSet is a list of `PageElement` objects, gathered as the result
    of matching a `SoupStrainer` against a parse tree. Basically, a list of
    search results.
    """
    source: SoupStrainer
    
    def __init__(self, source:SoupStrainer, result: Iterable[_PageElementT]=()):
        super(ResultSet, self).__init__(result)
        self.source = source

    def __getattr__(self, key):
        """Raise a helpful exception to explain a common code fix."""
        raise AttributeError(
            "ResultSet object has no attribute '%s'. You're probably treating a list of elements like a single element. Did you call find_all() when you meant to call find()?" % key
        )
