# The Shop is a git submodule pinned to a release

The Shop's code sits in this repo as a git submodule pinned to release 3.1.0, and is never edited.
This keeps a visible line between borrowed code and ours (an honesty rule) and records exactly
which Shop version every result came from. We rejected copying it in (blurs the line), cloning it
outside the repo (version not recorded), and forking it (mixes our work into theirs).
