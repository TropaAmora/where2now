# Walkthrough: Push the CI/CD changes via a feature branch

Run these in your project root (`c:\devs\where2now`) in PowerShell or Git Bash. If you get a lock error, close anything that might be using Git (IDE, another terminal) and try again.

---

## Step 1: Create a feature branch (keeps your current changes on the new branch)

```powershell
git checkout -b feature/ci-cd-and-git-workflow
```

You’re now on `feature/ci-cd-and-git-workflow`; your uncommitted files are unchanged.

---

## Step 2: Stage everything (new, modified, and deleted files)

```powershell
git add .github/
git add README.md
git add pyproject.toml
git add pytest.ini
```

Or in one go:

```powershell
git add -A
```

Then check what will be committed:

```powershell
git status
```

You should see: new `.github/` workflows, modified `README.md`, new `pyproject.toml`, and deleted `pytest.ini`.

---

## Step 3: Commit

```powershell
git commit -m "Add CI/CD workflows and Git workflow docs"
```

---

## Step 4: Push the branch and set upstream

```powershell
git push -u origin feature/ci-cd-and-git-workflow
```

The first time you push this branch, `-u origin feature/ci-cd-and-git-workflow` sets the upstream so later you can just run `git push`.

---

## Step 5: Open a Pull Request (on GitHub)

1. Go to your repo on GitHub.
2. You should see a yellow bar: **“feature/ci-cd-and-git-workflow had recent pushes”** with a **Compare & pull request** button — click it.
3. Or: **Pull requests** → **New pull request**.
   - **base:** `main` (or `develop` if you want this to merge into develop first).
   - **compare:** `feature/ci-cd-and-git-workflow`.
4. Add a title (e.g. “Add CI/CD workflows and Git workflow docs”) and create the PR.
5. CI will run on the PR; when it’s green, merge (e.g. “Merge pull request”).

---

## Step 6: After the PR is merged (back on your machine)

```powershell
git checkout main
git pull origin main
git branch -d feature/ci-cd-and-git-workflow
```

That updates `main` and deletes the local feature branch. You’re ready for the next feature.
