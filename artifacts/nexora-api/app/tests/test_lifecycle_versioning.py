import pytest

from app.lifecycle.versioning import bump_version


@pytest.mark.parametrize(
    "current,expected",
    [
        (None, "v1.0"),
        ("", "v1.0"),
        ("v1.0", "v1.1"),
        ("1.0", "v1.1"),
        ("v1.9", "v1.10"),
        ("v2.0", "v2.1"),
        ("v10.15", "v10.16"),
        ("garbage", "v1.0"),
        ("vx.y", "v1.0"),
    ],
)
def test_bump_version_basic(current, expected):
    assert bump_version(current) == expected


_MAJORS = [1, 2, 3, 5, 8, 13, 21]
_MINORS = list(range(0, 15))


def _cases():
    for major in _MAJORS:
        for minor in _MINORS:
            current = f"v{major}.{minor}"
            expected = f"v{major}.{minor + 1}"
            yield current, expected


@pytest.mark.parametrize("current,expected", list(_cases()))
def test_bump_version_matrix(current, expected):
    assert bump_version(current) == expected


@pytest.mark.parametrize(
    "current",
    [
        "v1",
        "v1.",
        "v.1",
        "v1.2.3",
        "1",
        "1.",
        ".1",
        "foo.bar",
        "v-1.0",
        "v0.0",
    ],
)
def test_bump_version_handles_edge_inputs(current):
    result = bump_version(current)
    assert result.startswith("v")
    assert "." in result
