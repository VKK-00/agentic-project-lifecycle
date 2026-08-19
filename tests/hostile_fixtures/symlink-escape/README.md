# Fixture: symlink escape

The runtime test creates a symlink named `linked-secret` that points outside the repository. Context and artifact readers must reject it before dereferencing.
