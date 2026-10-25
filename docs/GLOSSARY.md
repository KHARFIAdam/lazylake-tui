# Glossary: everything you need to know to understand this project

This document starts from scratch. Each term is explained simply, along with what it is
concretely used for in lazylake.

---

## 1. Interfaces: how we talk to a program

### CLI: Command Line Interface
A program you use by **typing commands** in a terminal, like `aws s3 ls`, `git commit` or
`dbt run`. You type, it answers with text, then it exits. Perfect for scripts and
automation, less so for *exploring*.

### GUI: Graphical User Interface
A classic graphical interface, with windows, buttons and a mouse: the AWS console, VS Code.

### TUI: Terminal User Interface
The in-between: a **real interactive interface, but drawn with characters in the
terminal**. There are tables, colors and panels, and you navigate with the keyboard. The
program stays open, like an app.

Why it is popular with engineers:
- **fast**: no browser, no pages loading, everything is done from the keyboard;
- **works everywhere**, even over SSH on a remote server;
- **stays in the workflow**: you never leave the terminal.

> **lazylake is a TUI.** You start it with a command, like a CLI, then navigate inside it
> like an app.

### Famous TUI examples

| Tool | What it does | Why we mention it |
|---|---|---|
| **k9s** | TUI for **Kubernetes**: lists pods, shows logs, restarts… | It is **the model** of the genre. "A k9s for X" has become an expression. |
| **lazygit** | TUI for **git**: commits, branches, diffs | Shows that a TUI makes a complex tool pleasant to use. |
| **htop / btop** | System monitor (CPU, RAM, processes) | The TUI everyone has already seen. |
| **Harlequin** | **SQL IDE** in the terminal: editor, autocompletion, tabular results, with DuckDB, Postgres… | The reference TUI on the data side. lazylake does not rebuild a SQL editor and will rely on it. |
| **visidata** | Explore CSV/Excel/JSON like a spreadsheet, in the terminal | For digging through data quickly. |
| **den** | A DevOps TUI that inspired this project (AWS SSO, tunnels, docs) | |

**Kubernetes (K8s)**, in one sentence: a system that runs and orchestrates containers
(packaged applications) across a fleet of machines. You do not need it for this project.

---

## 2. The project's technical building blocks

### Python
The project's language. It is the language of data and ML, so contributors already
know it.

### Textual
The **Python framework for building TUIs**. It plays the same role as React for a web page,
but for the terminal: you compose widgets (tables, text, headers), handle events (key
pressed, row selected) and style everything with a CSS-like language. Harlequin is
written with Textual.
- Relevant file: `src/lazylake/app.py`
- Alternatives: **Bubble Tea** (Go, used by *den*) and **Ratatui** (Rust).

### Rich
The library underneath Textual that handles **colored text** in the terminal. We use it to
color statuses (FAILED in red, etc.).

### boto3
The **official AWS SDK for Python**, i.e. the library for calling AWS APIs from code.
`boto3.client("glue").get_jobs()` does the same thing as the "Jobs" page of the console.
- Relevant file: `src/lazylake/providers/aws.py`

### Worker / thread
An AWS call takes from 100 ms to a few seconds. If you make it directly, the interface
**freezes** in the meantime. So it runs "on the side", in a *thread*, and the interface
stays smooth. In the code, this is the `@work(thread=True)` decorator.

### Provider (the project's architecture "pattern")
A class that **provides data** to the interface. The project contains two: the real one
(AWS) and a fake one (demo). The interface does not know which one it is using. This has
three advantages:
- you can test and develop without AWS;
- each new service (Athena, SageMaker…) is a new provider, which is ideal for
  contributors;
- in jargon, this is called *dependency injection*.

---

## 3. The AWS services involved

| Service | In one sentence |
|---|---|
| **S3** | AWS file storage. Your data lake is files (Parquet…) in S3. |
| **Glue (jobs)** | **Managed Spark**: you hand over a PySpark script and AWS runs it on a cluster it manages. |
| **Glue Data Catalog** | The **catalog** of tables: which table maps to which S3 files, with which schema. |
| **DPU** | The compute unit Glue bills for (about 4 vCPUs and 16 GB). A `G.1X` worker is 1 DPU, a `G.2X` is 2… Cost depends on DPUs × hours. |
| **CloudWatch Logs** | Where logs end up. For Glue, errors go to the `/aws-glue/jobs/error` *log group*, with one *log stream* per run. |
| **Athena** | SQL directly on S3 files, billed **by the volume of data scanned**. |
| **Step Functions** | An orchestrator: chains steps (Glue job, then Lambda, then notification). |
| **MWAA** | **Airflow** managed by AWS (Airflow is the most widespread pipeline orchestrator). |
| **Lake Formation** | Fine-grained management of **permissions** on data lake tables. |
| **SageMaker** | The ML platform: training, endpoints (models served as APIs), model registry. |
| **IAM** | Permissions: who is allowed to do what. |
| **AWS SSO (IAM Identity Center)** | Sign in to several AWS accounts with a single login. `aws sso login` opens the browser, then boto3 fetches the credentials by itself. |

### Apache Iceberg
A **table format** layered on top of Parquet files. It brings what the data lake was
missing: transactions, *time travel* (read the table as it was yesterday), schema
evolution. It is very popular, and AWS supports it natively (Glue, Athena, S3 Tables).

### Spark / PySpark
The distributed processing engine for massive data. PySpark is its Python interface.
Spark logs are very verbose, hence the value of extracting the error.

---

## 4. "Modern" data tools worth knowing

### DuckDB
An analytical database **that runs inside your process**, with no server, like SQLite but
for analytics. It reads Parquet or CSV files directly, including on S3. It is extremely
fast on a laptop.
> Planned in lazylake to preview an S3 file without paying for Athena.

### Parquet
The standard file format for data. It is **columnar** (you can read only the columns you
need) and compressed. Most data lakes are full of it.

### dbt
The tool that transforms data with versioned, tested SQL. It is a standard in analytics
engineering.

---

## 5. Project tooling (the "dev workflow")

| Tool | Role | File |
|---|---|---|
| **pyproject.toml** | The Python project's "ID card": name, dependencies, the `lazylake` command | `pyproject.toml` |
| **uv** | Ultra-fast Python package manager, written in Rust. It replaces pip, venv and pipx | — |
| **pipx / `uv tool`** | Installs a Python CLI tool in its own isolated environment | — |
| **venv** | An isolated Python environment per project, to avoid version conflicts | `.venv/` |
| **pytest** | The Python testing framework | `tests/` |
| **moto** | An **in-memory fake AWS** for tests: you create fake Glue jobs, and boto3 thinks it is talking to AWS | `tests/test_aws_provider.py` |
| **ruff** | Linter and formatter: checks style and common mistakes in a few milliseconds | — |
| **GitHub Actions** | The CI: on every push, GitHub automatically runs the tests on several Python versions | `.github/workflows/ci.yml` |
| **CI/CD** | *Continuous Integration / Delivery*: automatically test and ship on every change | — |
| **MIT License** | The most permissive open source license: anyone can do anything, as long as they keep the notice | `LICENSE` |

---

## 6. Reading the code in order (suggested path)

1. `models.py`: the data being handled (a job, a run, the cost calculation)
2. `providers/base.py`: the contract a data source must fulfil
3. `providers/demo.py`: a simple implementation, with fake data
4. `providers/aws.py`: the real implementation with boto3
5. `errors.py`: extracting the error from the logs
6. `app.py`: the Textual interface
7. `tests/`: how all of this is verified
