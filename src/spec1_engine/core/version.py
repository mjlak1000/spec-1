"""Version metadata for SPEC-1 Intelligence Engine.

This file is part of the frozen core package.

IMMUTABILITY RULE: No agent or module may write to ``core/``.
Version bumps require human review and a corresponding CHANGELOG.md entry.

Versioning Rules
----------------
+-------------------------------+---------------+
| Change type                   | Version bump  |
+===============================+===============+
| Breaking schema/contract/     | MAJOR         |
| prompt change in ``/core``    |               |
+-------------------------------+---------------+
| New module, scorer, adapter   | MINOR         |
+-------------------------------+---------------+
| Bug fix, CI, infra            | PATCH         |
+-------------------------------+---------------+

Every PR touching ``/core`` must bump the version here and document
the impact in ``CHANGELOG.md``.
"""

from __future__ import annotations

#: Current semantic version of the SPEC-1 core package.
__version__: str = "0.2.0"

#: Structured version tuple for programmatic comparison.
VERSION: tuple[int, int, int] = (0, 2, 0)

#: Human-readable release name for this version.
RELEASE_NAME: str = "Frozen Core"


def bump_version(part: str) -> str:
    """Return the next semantic version string after bumping *part*.

    This is a **utility function only** — it does not mutate :data:`__version__`
    or :data:`VERSION`.  Actual version bumps must be applied manually by a
    human reviewer in this file.

    Args:
        part: One of ``"major"``, ``"minor"``, or ``"patch"``.

    Returns:
        The bumped version string (e.g. ``"0.3.0"``).

    Raises:
        ValueError: If *part* is not one of the allowed values.

    Example::

        >>> bump_version("minor")
        '0.3.0'
        >>> bump_version("patch")
        '0.2.1'
    """
    major, minor, patch = VERSION
    part = part.lower()
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid version part {part!r}. Expected 'major', 'minor', or 'patch'.")
