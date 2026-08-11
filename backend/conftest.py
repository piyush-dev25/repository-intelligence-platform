# backend/conftest.py
# Empty on purpose - its presence here tells pytest to treat backend/
# as the import root, so "from app.xxx import yyy" resolves correctly
# in test files, regardless of which subfolder they live in.