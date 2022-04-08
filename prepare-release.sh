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

# Make sure tests pass
./test-all-versions

rm -rf build dist beautifulsoup4.egg-info

# Make both sdist and wheels.
python3 setup.py sdist bdist_wheel

# Test the wheel locally.

rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install dist/beautifulsoup4-*.whl
echo "EXPECT HTML ON LINE BELOW"
(cd .. && python -c "from bs4 import _s; print(_s('<a>foo', 'html.parser'))")
# That should print '<a>foo</a>'
deactivate
rm -rf ../py3-install-test-virtualenv

#

# Upload to test
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Test install from test pypi

rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install -i https://testpypi.python.org/pypi beautifulsoup4 --extra-index-url=https://pypi.python.org/pypi
echo "EXPECT HTML ON LINE BELOW"
(cd .. && python -c "from bs4 import _s; print(_s('<a>foo', 'html.parser'))")
# That should print '<a>foo</a>'
deactivate
rm -rf ../py3-install-test-virtualenv

# Upload for real
twine upload dist/*

# Test install from production pypi

rm -rf ../py3-install-test-virtualenv
virtualenv -p /usr/bin/python3 ../py3-install-test-virtualenv
source ../py3-install-test-virtualenv/bin/activate
pip install beautifulsoup4
echo "EXPECT HTML ON LINE BELOW"
(cd .. && python -c "from bs4 import _s; print(_s('<a>foo', 'html.parser'))")
# That should print '<a>foo</a>'
deactivate
rm -rf ../py3-install-test-virtualenv
