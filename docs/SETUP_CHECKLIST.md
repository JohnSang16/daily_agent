# Setup checklist (do once, tick as you go)

## 1. Tools on your computer
1. Python 3.12, `uv`, Git, and the GitHub CLI.
2. Claude Code installed and signed in.
3. A Mac and Xcode, only needed later for spec 10.

## 2. Create the repository
1. Create a private GitHub repository named `daily_agent`.
2. Copy this folder into it, initialize git, and push.
3. Install the pre commit hooks (ruff and a secret scanner) before your first real commit. Claude Code sets these up in spec 02.
4. Confirm `.env` and the `secrets/` folder are ignored by git.

## 3. Install Superpowers safely
1. Install it from the official Claude plugin marketplace inside Claude Code (see the Superpowers README for the exact command), then restart Claude Code.
2. Set the environment variable `SUPERPOWERS_DISABLE_TELEMETRY` to a true value in your shell profile to turn off its optional logo telemetry.
3. Keep permission prompts on. Review the plugin's changes before accepting any update.
4. Before installing any other skill or plugin (including your own jso and anything it offers to install), scan it with SkillSpector: install it with `uv tool install` from its GitHub repository, run `skillspector scan` on the skill folder, and read the findings. Treat scores as hints and read the flagged lines yourself.

## 4. Google Cloud (for Calendar now, Gmail in spec 06)
1. Create a Google Cloud project.
2. Enable the Google Calendar API and the Gmail API.
3. Configure the OAuth consent screen. Add yourself as a test user.
4. Create an OAuth client of type Desktop app and download the client file into `secrets/` (gitignored).
5. Note the publishing status question in spec 04 about refresh token expiry.

## 5. Obsidian vault repository
1. Confirm the vault is pushed to a private git repository.
2. Create a new SSH key pair just for this project and add the public half as a **read only deploy key** on that repository. Claude Code can walk you through generating the key.
3. Store the private key in `secrets/` locally and later in your host's secret store.
4. Decide which folders to ignore.

## 6. Anthropic API key
1. Create an API key in the Anthropic console for this project only.
2. Set a low monthly spending limit.
3. Put the key in `.env`, never in chat or in git.

## 7. College digest sample
Save one real digest email, with personal names, ids, and links redacted, into `tests/fixtures/digests/`. Note the sender address for `GMAIL_DIGEST_QUERY`.

## 8. Cox IT question (needed before spec 11)
Send this when ready. Do not use any Cox data in the project until you have a written answer.

Subject: Question about a personal tool reading my work calendar

Hello,

I am building a small personal scheduling tool for my own use. I would like to know whether it is allowed for a personal application I run to read my Outlook calendar, with read only access and storing only event titles and times. If this is not permitted, or if there are conditions about where the data may be stored, could you let me know?

Thank you for your guidance.

Best regards,
John Sang
Software Engineering Intern, Central Dispatch
Cox Automotive

## 9. Homework browser agent prerequisites (later, for spec 13)
1. Read your college's policy on AI assistance for coursework and write down what is allowed.
2. Read the terms of use for Pearson and your school's learning platform about automated access.
3. Create a Kernel account and read its current docs on live view, browser profiles, and managed login.
4. List the exact iCollege and Pearson domains the agent may visit.
5. Do not give the agent your college password. You will sign in yourself through the live view.

## 10. Accountability
1. Set a repeating phone reminder every 3 days named "Check in with Claude".
2. At each check in, run Prompt 2 in Claude Code and paste the output into our chat.
3. Keep `docs/CHECKIN_LOG.md` up to date.
