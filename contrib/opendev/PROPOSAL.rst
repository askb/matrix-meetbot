..
   SPDX-License-Identifier: Apache-2.0
   SPDX-FileCopyrightText: 2026 The Linux Foundation

=========================================================
Proposal: a Matrix-native meeting bot for OpenDev
=========================================================

This file holds (1) a short message to start the discussion in
``#opendev:opendev.org`` and on ``service-discuss@lists.opendev.org``, and
(2) a mini-spec / StoryBoard description to file once there is interest.

Both reference the OpenDev Matrix infra-spec, which lists "meetbot
replacement" as an unassigned work item:
https://docs.opendev.org/opendev/infra-specs/latest/specs/matrix.html


1. Discussion message (paste into Matrix / mailing list)
========================================================

Subject: Matrix-native meeting bot (meetbot replacement) -- POC + offer to drive

Hi all,

The Matrix spec lists a "meetbot replacement" as a TBD work item so that
projects on the opendev.org homeserver get native meetings without relying on
the OFTC bridge. I've built a working proof-of-concept and would like to drive
this to completion if the team agrees on the approach.

What the POC does:

* Reuses opendev/meetbot's existing meeting **engine** unchanged, so minutes
  and logs are byte-for-byte the OpenDev format (same #commands, same
  meetings.opendev.org layout, UTC).
* Adds a small Matrix transport (currently matrix-nio) that feeds room messages
  into the engine and posts replies / sets the room topic.
* Ships a functional gate that **spins up a disposable Synapse in the job**,
  runs the bot, replays a scripted meeting and asserts the minute/log output --
  exactly the "dynamically spin up a Matrix server in a gate test job" pattern
  the spec calls out. (POC currently runs it on GitHub Actions; trivially
  portable to a Zuul job -- mapping included.)

Questions for the team before I propose code:

1. Appetite: do you want the native Matrix meetbot now?
2. Repo: extend ``opendev/meetbot`` with a Matrix transport (shared engine,
   single codebase) or a new repo (e.g. ``opendev/matrix-meetbot``) like the
   Matrix gerritbot? The spec allows either.
3. Library: I used matrix-nio (Python). Is there a preferred Matrix client
   stack for consistency with gerritbot/other bots that I should adopt instead?
4. Deployment: run it as a container on eavesdrop02 via system-config, with a
   ``@meetbot:opendev.org`` bot account -- any constraints I should design for?

Happy to demo live and to bring the work up under the ``matrix`` Gerrit topic.

Thanks!


2. Mini-spec / StoryBoard description
=====================================

Title: Matrix-native meeting bot (meetbot replacement)

Problem
  Projects using the opendev.org Matrix homeserver currently get meeting
  support only by bridging into the IRC Limnoria/Meetbot via OFTC. The Matrix
  spec identifies a native "meetbot replacement" as desirable but unassigned.

Proposed change
  Add a Matrix transport that drives the existing opendev/meetbot meeting
  engine, preserving the exact command vocabulary and the
  meetings.opendev.org output format. No engine changes; transport-only.

Scope
  * Connect a bot account to the homeserver, join configured rooms, accept
    invites.
  * Map Matrix events to engine ``addline`` calls; ``/me`` -> ACTION; ignore
    own messages and pre-join history.
  * Persist minutes/logs to the eavesdrop log volume; set
    ``logUrlPrefix`` = https://meetings.opendev.org/ so links resolve.
  * Restart resilience (resume an in-progress meeting without re-posting).

Testing
  Functional Zuul job boots a disposable Synapse, runs the bot, replays a
  meeting, asserts minutes/logs. Unit tests for the engine + dispatch.

Deployment
  Ansible role + room list in opendev/system-config
  (inventory/service/group_vars/eavesdrop.yaml); bot token as a secret.

Out of scope (future)
  statusbot/eavesdrop Matrix replacements; SSO-hosted user accounts.

Gerrit topic
  ``matrix``
