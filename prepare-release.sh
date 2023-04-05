# A script to automatically create and test source and wheel
# distributions of Beautiful Soup.

# Recommend you run these steps one at a time rather than just running
# the script.

# If you screwed up on the test server and have to create a "a" or "b"
# release the second time, add the '--pre' argument to pip install to
# find the 'prerelease'.

# Change the version number in
#  CHANGELOG
#  bs4/__init__.py
#  doc/source/index.rst

hatch clean
tox run-parallel

# Build sdist and wheel.
hatch build

# Test the wheel locally.
rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install dist/beautifulsoup4-*.whl pytest lxml html5lib soupsieve
python -m pytest ../py3-install-test-virtualenv/lib/python3.10/site-packages/bs4/tests/
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")
# That should print something like:
# /home/.../py3-install-test-virtualenv/bin/python
# [new version number] <a>foo</a>

deactivate
rm -rf ../py3-install-test-virtualenv

# Upload to test pypi
hatch publish -r test

# Test install from test pypi
rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install pytest lxml html5lib
pip install -i https://testpypi.python.org/pypi beautifulsoup4 --extra-index-url=https://pypi.python.org/pypi 
python -m pytest ../py3-install-test-virtualenv/lib/python3.10/site-packages/bs4/tests/
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'lxml'))")
# That should print something like:
# /home/.../py3-install-test-virtualenv/bin/python
# [new version number] <a>foo</a>
deactivate
rm -rf ../py3-install-test-virtualenv

# Upload to production pypi
hatch publish

# Test install from production pypi

rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install beautifulsoup4
echo "EXPECT HTML ON LINE BELOW"
(cd .. && which python && python -c "from bs4 import _s, __version__; print(__version__, _s('<a>foo', 'html.parser'))")
# That should print '<a>foo</a>'
deactivate
rm -rf ../py3-install-test-virtualenv
