# Contributing to IRIS

This repository is the home of **IRIS**, the Insurance Reference Intelligence Stack: the architecture proposal, the supporting diagrams, the first-wave task breakdown, and the production code that grows out of executing those tasks.

## Before you start

1. Read the README. It links to the architecture proposal, the diagrams, and the task breakdown.
2. Pick a task from [`tasks/`](tasks/). Each workstream folder lists every task with an identifier (`T0xx`), a size, and an acceptance criterion.
3. If you do not have an assigned task and want to suggest work, open an issue using the **Task** template.

## Branch protection on `main`

`main` is protected. The rules are:

- Direct pushes to `main` are rejected by GitHub. All changes land through pull requests.
- Every pull request requires **one approving review** before merge.
- New commits dismiss stale approvals on the PR.
- Every review conversation must be marked resolved before merge.
- Merges use **squash and merge**; the PR title becomes the squashed commit message.
- Force pushes and branch deletion are blocked on `main`.

Repository admins can bypass the review requirement in an emergency (`enforce_admins: false`). This bypass is auditable and should be the exception, not the routine.

## The flow per task

1. **Cut a feature branch** from `main` named after the task identifier:
   ```
   git checkout main
   git pull --ff-only origin main
   git checkout -b T031-ocr-selector
   ```
   The convention is `T0xx-short-slug`. The slug is a few words, lower-case, hyphen-separated.

2. **Open a draft pull request** as soon as the first commit lands. This makes the work visible early and lets reviewers catch direction problems before you go deep.
   ```
   gh pr create --draft --base main --head T031-ocr-selector
   ```

3. **Work the task.** Use the PR template's checklist:
   - Every acceptance criterion in the task's `tasks.md` entry is satisfied.
   - The `docs-ci` workflow passes (markdown lint + structural check on `tasks/`).
   - No em-dashes in new prose. The project convention is to use periods, commas, parentheses, or colons.
   - All internal links resolve.
   - No secrets, credentials, or personal names introduced.

4. **Mark the PR ready for review** when the criteria are satisfied:
   ```
   gh pr ready
   ```
   `CODEOWNERS` auto-requests review from the architect; add any other reviewers manually.

5. **Address review comments.** Resolve every conversation in the GitHub UI. If you push new commits, the previous approval is dismissed and the reviewer is asked to approve again.

6. **Merge via squash and merge.** Through the GitHub UI's button, or:
   ```
   gh pr merge --squash --delete-branch
   ```
   The feature branch is deleted on merge.

## Style notes for prose in this repo

These come up in review enough to be worth writing down.

- No em-dashes. Use a period, a comma, a colon, or parentheses. Hyphens in compound words (`multi-tenant`, `audit-first`) are fine.
- Lead with the verb in PR titles and commit messages. `add CODEOWNERS file`, not `CODEOWNERS file added`.
- Plain English with technical terms when needed. Avoid jargon that has not been introduced in the same document.
- Tables for comparisons; prose for reasoning; bullets only when the items are genuinely parallel.

## When to open an issue

- Filing a discrete task that is not already in `tasks/`: open a **Task** issue using the issue template. Tie it back to a workstream.
- Reporting a defect in the documents (broken link, factual error, missing acceptance criterion): open a regular issue or just open a PR with the fix.

## Where the conversation happens

- Architectural questions: in the PR or issue itself. Tag the architect.
- Status updates and planning: project tracker, not this repo.
- Roadmap-level discussion: the four-phase rollout in [`docs/architecture/architecture.md`](docs/architecture/architecture.md) is the reference; propose changes through a PR that edits that section.

## What to do if you cannot merge

GitHub will not let you approve a PR you opened yourself. If you are the only person on the repo and you opened the PR, the practical options are:

1. **Admin merge bypass** (the architect or another admin uses the "Merge as admin" path).
2. **Add a second reviewer** to the repo so someone other than the author can approve.

For a small early team, option 1 is fine as an exception. The yellow "merged as admin" banner makes the action auditable.

## Local development of the docs

If you are running the markdown lint locally before pushing:

```
npm install -g markdownlint-cli@0.41.0
markdownlint 'docs/**/*.md' 'tasks/**/*.md' 'README.md'
```

To run the tasks structural check:

```
python3 scripts/check-tasks.py
```

Both run on every PR via `.github/workflows/docs-ci.yml`.
