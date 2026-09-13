# Capability fixtures

Capabilities that are deliberately broken, for the loader's tests.

**They live here rather than in `.harry/` on purpose.** `scripts/check_capabilities.py`
validates everything under `.harry/` and runs in `make lint`, so a folder with unclosed
frontmatter parked there would fail the gate on every run, for everyone, forever.

`tests/test_loader.py` copies the ones a test needs into a temporary root and points the
loader at it, so each test gets exactly the tree it is about.

Each folder is a real capability, and each broken one is broken in the way its name says.
That matters: a degradation path asserted with a mock is the control that cannot fail.

`pyrightconfig.json` excludes `tests/fixtures`. The point of half of these folders is that
they do not work — an import of something nobody installed, a reach into `harry.scheduler`
— and a type checker is right about both. They are input to the loader, not part of the
program.
