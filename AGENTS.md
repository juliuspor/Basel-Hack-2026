# Repository instructions

These instructions apply to all agents working anywhere in this repository.

## Repository structure

- Put application code in `code/`.
- Put code documentation in `documentation/`.
- Put media, presentations, and other assets in `assets/`.

## Required commit format

Every commit message you create or propose MUST follow Conventional Commits
with a mandatory scope:

```text
<type>(<scope>): <description>
```

For example:

```text
feat(app): added onboarding screen
```

Conventional Commits is the format; Commitizen is a tool that helps write
messages using it. This repository requires a scope even though the upstream
specification makes it optional.

### Rules

- Use one of these lowercase types: `feat`, `fix`, `docs`, `style`, `refactor`,
  `perf`, `test`, `build`, `ci`, `chore`, or `revert`.
- Use `feat` for new features and `fix` for bug fixes. Choose the other type
  that best describes the change: documentation, formatting, refactoring,
  performance, tests, build/dependencies, CI, maintenance, or reversions.
- Always include a meaningful lowercase scope in parentheses, such as `app`,
  `api`, `docs`, or `repo`. Use lowercase letters and digits separated by
  single hyphens for multiword scopes, such as `user-auth`.
- Follow the closing parenthesis with a colon and exactly one space.
- Write a concise, nonempty description of the actual change. Past tense,
  such as `added onboarding screen`, is allowed. Do not add a trailing period.
- For a breaking change, insert `!` immediately before the colon:
  `feat(api)!: changed authentication response`. Explain the incompatibility
  and migration in a `BREAKING CHANGE: ...` footer, separated from the header
  or body by a blank line.
- Optional bodies and footers follow the header after a blank line.
- Apply these rules to squash commit messages as well. Do not use generic
  messages such as `update`, `WIP`, or `fix stuff`.

### Check before committing

Before creating or proposing a commit, verify its first line against this
regular expression, then check the semantic rules above:

```regex
^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)\([a-z0-9]+(-[a-z0-9]+)*\)!?: \S(.*\S)?$
```

If a message fails these rules, rewrite it before committing. Do not create
a noncompliant commit. These are agent instructions; this file alone does
not install a Git hook or a CI validator.

Valid examples:

```text
feat(app): added onboarding screen
fix(api): fixed empty response handling
docs(repo): documented local setup
chore(build): updated development dependencies
```

Invalid examples:

```text
added onboarding screen
feat: added onboarding screen
Feat(app): added onboarding screen
feat(app):added onboarding screen
```

### References

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Commitizen commit-message documentation](https://commitizen-tools.github.io/commitizen/tutorials/writing_commits/)
