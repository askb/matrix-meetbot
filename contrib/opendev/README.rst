..
   SPDX-License-Identifier: Apache-2.0
   SPDX-FileCopyrightText: 2026 The Linux Foundation

==========================================
OpenDev migration kit (Zuul + deployment)
==========================================

This directory contains everything needed to move the Matrix meetbot from a
personal GitHub-Actions POC onto OpenDev's infrastructure. **Nothing here runs
on GitHub** -- the POC repo gates on GitHub Actions; these files are the
OpenDev/Zuul equivalents, kept together so the migration is copy-paste ready.

Why GitHub Actions is POC-only
==============================

GHA is fine for demos and personal iteration but is **not** a production host
for an OpenDev service:

* Jobs are ephemeral and time-limited (max 6h); scheduled runs are best-effort.
  A meetbot must be online 24/7 to answer ``#startmeeting`` at any time.
* No persistent storage; minutes live at ``meetings.opendev.org``.
* No stable inbound networking (the POC needed a cloudflared tunnel).
* OpenDev runs **self-hosted open infra (Zuul)**, not proprietary CI.

In production the bot runs as a long-lived container on
``eavesdrop02.opendev.org`` (alongside Limnoria/Meetbot), deployed by Ansible in
``opendev/system-config``, talking to the real ``opendev.org`` homeserver.

GitHub Actions -> Zuul mapping
==============================

============================  ==================================================
GHA (.github/workflows/ci.yaml)  Zuul equivalent (this directory)
============================  ==================================================
``unit`` job (pytest)         ``openstack-tox-py311`` -> ``tox.ini`` ``[testenv]``
(lint, implicit)              ``openstack-tox-pep8``  -> ``tox.ini`` ``[testenv:pep8]``
``functional`` job            ``meetbot-matrix-functional`` (zuul.d/jobs.yaml)
``actions/checkout``          Zuul prepares ``{{ zuul.project.src_dir }}``
``setup-python`` + pip        ``pre-run`` playbook: ``ensure-pip``
Docker (for Synapse)          ``pre-run`` playbook: ``ensure-docker``
the functional shell steps    ``run-functional.sh`` (single source of truth)
``upload-artifact``           ``post-run`` playbook -> Zuul build logs
``on: [push, pull_request]``  ``check`` + ``gate`` pipelines (zuul.d/project.yaml)
============================  ==================================================

The functional logic is intentionally factored into ``run-functional.sh`` so
the **same** code path runs locally, in GitHub Actions, and in Zuul. The Zuul
``run.yaml`` playbook just invokes that script.

Files
=====

* ``zuul.d/jobs.yaml`` -- the ``meetbot-matrix-functional`` job definition.
* ``zuul.d/project.yaml`` -- ``check``/``gate`` pipeline wiring.
* ``playbooks/functional/{pre,run,post}.yaml`` -- node prep, run, artifact pull.
* ``run-functional.sh`` -- Synapse + bot + replay + assertions.
* ``tox.ini`` -- ``py311`` (unit) and ``pep8`` (lint) envs.
* ``bindep.txt`` -- binary deps (Docker comes from ``ensure-docker``).
* ``PROPOSAL.rst`` -- ready-to-send design-discussion message / mini-spec.

On actual migration
====================

1. Decide repo placement with OpenDev (extend ``opendev/meetbot`` vs a new
   ``opendev/matrix-meetbot`` repo). See ``PROPOSAL.rst``.
2. Move ``zuul.d/`` and ``playbooks/`` to the repo root (drop the
   ``contrib/opendev/`` prefix and update the playbook paths in jobs.yaml).
3. Add the deployment role + room list to ``opendev/system-config``
   (``inventory/service/group_vars/eavesdrop.yaml``), with the
   ``@meetbot:opendev.org`` token as an Ansible-vault/Zuul secret.
4. Switch config to production: ``MEETBOT_HOMESERVER`` = the opendev.org
   homeserver, ``MEETBOT_BASE_URL=https://meetings.opendev.org/``, persistent
   ``MEETBOT_OUTPUT_DIR``. This is a **config-only** change to the bot code.

Licensing note
==============

These OpenDev-destined files are ``Apache-2.0`` (OpenStack/OpenDev default).
The vendored meeting engine under ``meetbot/engine/`` keeps its upstream
``BSD-3-Clause`` license; SPDX headers make the mix explicit and REUSE-clean.
