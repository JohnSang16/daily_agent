# Start here: handing this project to Claude

Pick one path. Neither needs anything installed on your computer.

## The zero setup path: give the zip to a normal Claude chat
Use this to build the foundation without GitHub and without installing anything.
1. Open a new chat at claude.ai. Make sure code execution and file creation are turned on in settings.
2. Attach `daily_agent.zip`.
3. Paste the prompt below and send it.
4. When Claude replies with a new zip, download it. Run the same prompt again with the new zip for the next spec if it did not finish all three.

```
Attached is a zip of my project, js ai. Unzip it. Read CLAUDE.md, specs/00_principles.md, and specs/01_overview.md first.

Build these specs, in this order, with tests first: spec 02 (specs/02_skeleton.md), then spec 17 (specs/17_write_protection.md), then spec 03 (specs/03_task_event_model.md).
You are authorized to proceed without waiting for plan approval for these three specs only. Do one spec per reply if it is too much for one reply.

For each spec: write the failing tests from the acceptance criteria (put the criterion ID in each test name), implement the smallest code that passes, and run uv run pytest and uv run ruff check . until both are clean. Show me the test results.

Hard limits: do not connect, request, or store any real account, token, key, or password. Use fakes. Everything is read only. If a spec is unclear or two specs disagree, ask me instead of guessing. Do not start spec 04 or later.

When you finish each spec, give me the end of task report from CLAUDE.md and a new zip of the whole project with the code added, plus an entry appended to docs/CHECKIN_LOG.md.
```

What to expect: this works for the foundation. It cannot connect Google, Gmail, your vault, or a bank, because those need your sign in and your secrets. From spec 04 on, switch to the Claude Code path below.

## The easiest path: Claude Code on the web
1. Make a private GitHub repository called `daily_agent`. Upload everything in this folder, including the hidden files (`CLAUDE.md`, `.gitignore`, `.env.example`). After uploading, check that `CLAUDE.md` and `specs/` show up in the repository.
2. Go to claude.ai/code and sign in. It asks you to connect GitHub (it installs the Claude GitHub app). Allow it to see the `daily_agent` repository. It then asks you to create an environment, and the defaults are fine. You need a paid Claude plan that includes Claude Code.
3. Pick the `daily_agent` repository, then paste the master prompt below.
4. Wait. Claude works in its own cloud machine, runs the tests, and opens a pull request. You can watch from the Claude app on your phone.
5. Read the pull request summary. If the tests pass, merge it. Then paste the summary into your chat with Claude and ask for a check in.

If package installs fail in the cloud session, widen the environment's allowed network domains so it can reach the Python package registry, then ask it to try again.

## Master prompt, phase A (the foundation, needs no accounts)
Copy everything inside the box.

```
You are building the js ai backend from the specs in this repository.
First read CLAUDE.md, specs/00_principles.md, and specs/01_overview.md.

Build these three specs, in this order, one branch and one pull request per spec:
1. specs/02_skeleton.md
2. specs/17_write_protection.md
3. specs/03_task_event_model.md

You are authorized to proceed without waiting for plan approval for these three specs only. For each one:
1. Write a short plan to docs/plans/ (named for the spec) and list every new dependency with a one sentence reason.
2. Write the failing tests first, straight from the acceptance criteria, with the criterion ID in each test name.
3. Implement the smallest code that passes.
4. Run uv run pytest and uv run ruff check . and fix until both are clean.
5. Put the end of task report from CLAUDE.md in the pull request description, and append an entry to docs/CHECKIN_LOG.md.

Hard limits:
1. Do not connect, request, or store any real account, token, key, or password. Use fakes in tests and placeholders in .env.example.
2. Everything is read only. Never add write scopes or calls to any outside service.
3. If a spec is unclear or two specs disagree, stop and ask me instead of guessing.
4. Do not start spec 04 or anything after spec 03. When all three pull requests are open, stop and summarize what is done, what is not, and what I must do myself.
```

## Which model to use
Use a faster model for the routine foundation specs and your strongest model for spec 17 and anything touching secrets, approvals, or money. The full list is in `docs/KICKOFF_PROMPTS.md` under "Which model for which spec".

## What only you can do (cannot be handed off)
1. Create the Google Cloud project and click through the consent screens (spec 04).
2. Make the read only deploy key for your vault repository (spec 05).
3. Create an Anthropic API key with a low spending limit (spec 06).
4. Check your college's policy on AI help and the terms for Pearson (spec 13).
5. Send the Cox IT question and wait for the answer (spec 11).
6. Pick a bank data service and read its terms (spec 16).
7. Get a Mac for the iPhone app (spec 10).

## After phase A is merged
Use the reusable prompt (Prompt 1) in `docs/KICKOFF_PROMPTS.md` for each next spec, in the order in `specs/01_overview.md`. From spec 04 on, you will be asked for things only you can provide, such as the Google credentials. Do not paste secrets into the chat. Put them in the environment settings of the cloud session or in a local `.env` file, as Claude Code instructs.

## Other ways to run the same handoff
1. The Claude desktop app has a Code tab. It can run sessions on your computer or in the cloud.
2. The terminal version of Claude Code works the same way and uses `CLAUDE.md` automatically. The setup checklist in `docs/SETUP_CHECKLIST.md` covers it.
3. In cloud sessions only the repository is used (your local plugin settings are not), so Superpowers may not be available. That is fine: `CLAUDE.md` describes the same steps by hand.
