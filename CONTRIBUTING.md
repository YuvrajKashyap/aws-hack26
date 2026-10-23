# Personal branches, reviewed integration

Every teammate pulls and ships from their own lowercase name branch. Yuvraj uses `yuvraj`; Abhinav uses `abhinav`. `main` is the reviewed integration branch. Do not push directly to `main`, push another person's branch, or force-push over anyone's work.

## First setup

With a clean checkout, fetch remote branches and inspect what already exists:

```sh
git fetch origin
git branch -a
```

If your branch already exists remotely, track it:

```sh
git switch --track origin/yuvraj
```

If it does not exist, create it from the current integration branch:

```sh
git switch -c yuvraj origin/main
```

Replace `yuvraj` with your own name. Do not run both switch commands. Do not switch branches over someone else's uncommitted work; coordinate first.

## Daily work

```sh
git switch yuvraj
git status --short
git pull --ff-only origin yuvraj
```

The pull command applies after the first authorized push has created the remote branch. To incorporate reviewed team changes, start with a clean working tree, then:

```sh
git fetch origin
git merge origin/main
```

Resolve conflicts on your own branch and rerun tests. This project uses explicit merges rather than rewriting shared branch history. Review the staged diff for secrets and restricted materials before committing.

When the work is ready and publishing is authorized:

```sh
git branch --show-current
git diff --cached --check
git push -u origin yuvraj
```

Open a pull request with base `main` and head `yuvraj`, include test evidence, and request teammate review. Everyone else follows the same flow with their own name. Only merge after the team's review and authorization. Branch protection is a separate repository setting; these instructions do not claim server-side enforcement or modify GitHub permissions.

For this local checkout, `push.default=current` is configured as a convenience. Always verify the branch and prefer the explicit push command above. That setting is not an access-control boundary.
