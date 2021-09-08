from bs4.testing import SoupTest
from bs4.element import (
    CData,
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    Script,
    Stylesheet,
    TemplateString,
)

class TestNavigableString(SoupTest):

    def test_text_acquisition_methods(self):
        # These methods are intended for use against Tag, but they
        # work on NavigableString as well,
        eq_ = self.assertEqual
        
        s = NavigableString("fee ")
        cdata = CData("fie ")
        comment = Comment("foe ")

        eq_("fee ", s.get_text())
        eq_("fee", s.get_text(strip=True))
        eq_(["fee "], list(s.strings))
        eq_(["fee"], list(s.stripped_strings))
        eq_(["fee "], list(s._all_strings()))

        eq_("fie ", cdata.get_text())
        eq_("fie", cdata.get_text(strip=True))
        eq_(["fie "], list(cdata.strings))
        eq_(["fie"], list(cdata.stripped_strings))
        eq_(["fie "], list(cdata._all_strings()))
        
        # Since a Comment isn't normally considered 'text',
        # these methods generally do nothing.
        eq_("", comment.get_text())
        eq_([], list(comment.strings))
        eq_([], list(comment.stripped_strings))
        eq_([], list(comment._all_strings()))

        # Unless you specifically say that comments are okay.
        eq_("foe", comment.get_text(strip=True, types=Comment))
        eq_("foe ", comment.get_text(types=(Comment, NavigableString)))
        
class TestNavigableStringSubclasses(SoupTest):

    def test_cdata(self):
        # None of the current builders turn CDATA sections into CData
        # objects, but you can create them manually.
        soup = self.soup("")
        cdata = CData("foo")
        soup.insert(1, cdata)
        self.assertEqual(str(soup), "<![CDATA[foo]]>")
        self.assertEqual(soup.find(text="foo"), "foo")
        self.assertEqual(soup.contents[0], "foo")

    def test_cdata_is_never_formatted(self):
        """Text inside a CData object is passed into the formatter.

        But the return value is ignored.
        """

        self.count = 0
        def increment(*args):
            self.count += 1
            return "BITTER FAILURE"

        soup = self.soup("")
        cdata = CData("<><><>")
        soup.insert(1, cdata)
        self.assertEqual(
            b"<![CDATA[<><><>]]>", soup.encode(formatter=increment))
        self.assertEqual(1, self.count)

    def test_doctype_ends_in_newline(self):
        # Unlike other NavigableString subclasses, a DOCTYPE always ends
        # in a newline.
        doctype = Doctype("foo")
        soup = self.soup("")
        soup.insert(1, doctype)
        self.assertEqual(soup.encode(), b"<!DOCTYPE foo>\n")

    def test_declaration(self):
        d = Declaration("foo")
        self.assertEqual("<?foo?>", d.output_ready())

    def test_default_string_containers(self):
        # In some cases, we use different NavigableString subclasses for
        # the same text in different tags.
        soup = self.soup(
            "<div>text</div><script>text</script><style>text</style>"
        )
        self.assertEqual(
            [NavigableString, Script, Stylesheet],
            [x.__class__ for x in soup.find_all(text=True)]
        )

        # The TemplateString is a little unusual because it's generally found
        # _inside_ children of a <template> element, not a direct child of the
        # <template> element.
        soup = self.soup(
            "<template>Some text<p>In a tag</p></template>Some text outside"
        )
        assert all(
            isinstance(x, TemplateString)
            for x in soup.template._all_strings(types=None)
        )
        
        # Once the <template> tag closed, we went back to using
        # NavigableString.
        outside = soup.template.next_sibling
        assert isinstance(outside, NavigableString)
        assert not isinstance(outside, TemplateString)

        # The TemplateString is also unusual because it can contain
        # NavigableString subclasses of _other_ types, such as
        # Comment.
        markup = b"<template>Some text<p>In a tag</p><!--with a comment--></template>"
        soup = self.soup(markup)
        self.assertEqual(markup, soup.template.encode("utf8"))

