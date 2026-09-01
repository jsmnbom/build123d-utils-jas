import pytest

from build123d_utils_jas import remove_fast_patch


@pytest.fixture(autouse=True)
def _unpatched():
  """Ensure no test leaks the fast patch into another."""
  yield
  remove_fast_patch()
