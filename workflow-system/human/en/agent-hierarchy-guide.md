---
title: "Agent Hierarchy Guide"
description: "Project, Wave, and Task responsibilities and escalation."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-28T04:45:44Z"
source_version: "19.0.0"
---

# Agent Hierarchy Guide

Project, Wave, and Task responsibilities and escalation.

## L0 Project

Confirms the goal, checklist, priorities, preflight, and round selection with
the human. It verifies evidence and decides advance, retry, escalate, or abort.
It never performs delegated work.

## L1 Wave

Dispatches at most five L2 Tasks with disjoint writable ownership, detects
conflicts, and aggregates StatusReports. It never implements or edits Task
output.

## L2 Task

Receives one atomic TaskDispatch, writes only owned files, runs bounded
verification, and returns falsifiable evidence. It cannot spawn another agent.

## Messages and escalation

TaskDispatch moves down; StatusReport moves up. Exception escalation follows
Task → Wave → Project → Human. Free-form shared state is not an artifact
contract.
