# Contribution Guidelines for netext

Welcome to the netext project! We appreciate your interest in contributing to our project. To maintain a quality in our codebase, we have set up some guidelines that will help you get started with contributing effectively. Please take a moment to read and understand these guidelines before submitting any pull requests (PRs) or issues.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Setting Up Your Development Environment](#setting-up-your-development-environment)
3. [Coding Style and Conventions](#coding-style-and-conventions)
4. [Writing Tests](#writing-tests)
5. [Submitting a Pull Request](#submitting-a-pull-request)
6. [Additional Resources](#additional-resources)

## Getting Started
1. Fork the netext repository on GitHub.
2. Clone your fork to your local machine.
3. Add the original repository as a remote called "upstream" to keep up-to-date with the main project.

```sh
git remote add upstream https://github.com/[your-username]/[your-project-name].git
```


## Setting Up Your Development Environment

This project uses [pixi](https://pixi.sh) to manage development environments.

To set up the development environment, follow these steps:
1. Install pixi (see pixi docs).

```sh
pixi install -e testing
```


1. Run tests:

```sh
pixi run -e testing pytest
```


1. Run formatting/linting:

```sh
pixi install -e linting
pixi run -e linting ruff format .
pixi run -e linting ruff check --fix .
pixi run -e linting pyright
```


## Coding Style and Conventions

We use the following tools to maintain a consistent coding style and conventions:
- [ruff](https://docs.astral.sh/ruff/) : Formatting + linting.
- [pyright](https://github.com/microsoft/pyright) : Type checking.

You can run these tools manually using the following commands:
- Format code with ruff:

```sh
pixi run -e linting ruff format .
```


- Lint and apply auto-fixes:

```sh
pixi run -e linting ruff check --fix .
```



Please make sure your code adheres to these conventions before submitting a PR.

## Writing Tests

We require that all external contributions are covered by tests. This project uses the [pytest](https://docs.pytest.org/en/stable/)  testing framework. You should write tests for any new features or bug fixes and ensure that all tests pass before submitting a PR.

To run tests, execute the following command:

```sh
pytest
```


## Submitting a Pull Request
1. Create a new branch with a descriptive name:

```sh
git checkout -b my-feature-branch
```


1. Make your changes, following the coding style and conventions, and write tests to cover your changes.
2. Commit your changes with a descriptive commit message.
3. Push your changes to your fork on GitHub.
4. Open a PR against the "main" branch of the original repository.

In the PR description, please provide a clear and concise description of the changes you've made, any issues or bugs that your changes address, and any additional information that may help reviewers.

## Additional Resources
- [GitHub Flow](https://guides.github.com/introduction/flow/) : A guide to understanding the GitHub workflow.
- [Poetry Documentation](https://python-poetry.org/docs/) : Official Poetry
