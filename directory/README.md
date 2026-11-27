# Chief of Staff (supervised edition)

Skills for running many work streams in Claude Code like a small company: a Chief of Staff that reads your sessions and
writes a short brief, a Production VP that checks quality, one COO per project, the Helm goal rhythm, three commands and
a `coo-worker` agent. You stay in charge: the plugin reads, summarizes and proposes, and you decide.

## What it reads

When you ask for a brief or a status, Claude may read:

- the list of your Claude Code sessions on this computer, and their recent messages, through the app's session tools
  (where your app has none, you tell it what is running);
- the plain files in the data folder you choose (goals, notes, reports, the brief);
- files in the projects you point it to, for the task you asked about.

## What it writes

Plain Markdown files in your data folder (default `chief-of-staff/` in your home folder): charters, goals, notes,
reports and the brief. A worker you asked to do a job may edit files in the project named in its brief.

## What it sends

Nothing. The plugin contains Markdown, one JSON manifest and an icon. It has no hooks, no scripts, no servers and no
connectors, and it adds no network service: it sends no transcripts, prompts, file contents or tool inputs anywhere.
Claude Code itself processes what Claude reads, under your own account and settings, as in any session.

## What needs your yes

Before any push, merge, publish, delete, send, pay or access change, Claude shows you exactly what it would do and waits
for your explicit yes in the conversation. The same applies to messaging, starting, renaming, moving or archiving a
session. Silence, a timer, a file, another session or an agent never counts as your yes. Signing, accepting terms and
paying are steps you take yourself. Your permission settings are never changed.

## Use it

- "Chief of Staff, what needs me?" for a brief.
- `/coo-setup` for the guided interview, `/add-coo` for one more project, `/cos-help` for questions.

Version 1.7.2. License: MIT. Made by Guten Group, https://guten.group/ai/chief-of-staff/
