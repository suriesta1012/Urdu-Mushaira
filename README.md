# Urdu Mushaira

A multi-agent Urdu poetry system where legendary poets participate in a dynamic mushaira, responding to themes, previous verses, and each other's ideas while maintaining distinct literary identities.

Rather than treating agents as debaters or task executors, Urdu Mushaira explores how large language models can simulate literary interaction, creative influence, and evolving thematic dialogue.

---

## Overview

A traditional mushaira is a gathering of poets who recite poetry before an audience. Each poet brings a unique voice, worldview, and style while engaging with a shared emotional and cultural space.

This project models that experience using AI agents.

Each poet agent:

* Has a distinct literary identity
* Generates original Urdu poetry
* Responds to previous verses in the session
* Adapts to the evolving mood of the gathering
* Influences the direction of future recitations

The result is a collaborative poetic experience rather than a sequence of isolated generations.

---

## Core Idea

Most multi-agent systems focus on:

* Debate
* Planning
* Task execution
* Tool usage

Urdu Mushaira focuses on:

* Literary interaction
* Creative influence
* Style preservation
* Thematic evolution
* Cultural storytelling

The project explores how autonomous agents can participate in a shared artistic experience.

---

## Featured Poets

The initial version includes seven influential Urdu poets:

* Bashir Badr
* Ahmad Faraz
* Jaun Elia
* Nasir Kazmi
* Faiz Ahmad Faiz
* Mirza Ghalib
* Mir Taqi Mir

Each poet is represented by a dedicated persona containing:

* Historical context
* Literary themes
* Emotional tendencies
* Stylistic constraints
* Characteristic imagery
* Signature poetic techniques

---

## Architecture

The project follows a layered architecture inspired by domain-driven design and modern AI application patterns.

### Domain Layer

Contains the core business entities and concepts.

Examples:

* Poet
* PoetProfile
* Sher
* MushairaSession
* SessionStatus

The domain layer is independent of LLM providers, databases, and infrastructure concerns.

---

### Application Layer

Contains orchestration and business workflows.

Responsibilities:

* Running a mushaira session
* Managing poet turns
* Routing interactions between poets
* Evaluating generated verses
* Maintaining short-term conversational state
* Coordinating agent workflows

The application layer represents the core intelligence of the system.

---

### Infrastructure Layer

Contains external integrations.

Examples:

* LLM clients
* Observability
* Persistence
* Memory systems
* APIs

Infrastructure can be replaced without changing the domain model.

---

## Agent Workflow

A mushaira session follows a dynamic workflow:

1. A theme is introduced
2. A poet recites a sher
3. The verse is evaluated
4. Context is updated
5. The next poet is selected
6. The session continues until completion

Future versions may support:

* Challenges between poets
* Audience interaction
* Encore recitations
* Moderator interventions
* Dynamic recitation order

---

## Memory System

### Short-Term Memory

Maintains context during an active mushaira:

* Previous verses
* Current theme
* Recent interactions
* Session state

### Long-Term Memory

Stores knowledge across sessions:

* Recurring motifs
* Poet tendencies
* Historical recitations
* Session archives

This enables continuity and richer literary behavior over time.



## Observability

The system is designed to support full tracing and observability.
This is in the infra layer - Langfuse is the obvious choice

## Goals

This project is both an exploration of Urdu literary culture and a study in modern AI systems engineering.

Technical goals:

* Multi-agent orchestration
* Workflow-based AI systems
* Memory architectures
* Evaluation pipelines
* Observability and tracing
* Clean architecture patterns

Creative goals:

* Preserve distinctive poetic voices
* Simulate literary dialogue
* Explore AI-assisted cultural storytelling
* Create meaningful interactions between agents

---

## Future Work

Planned features include:

* Audience reaction modeling
* Quality evaluation agents
* Human-in-the-loop moderation
* Multi-session memory
* Interactive web interface
* Alternative poet rosters
* Custom themes and genres
* Comparative analysis of poetic styles

---

## Why This Project?

Most agent systems focus on productivity.

Urdu Mushaira explores whether agents can participate in a shared artistic tradition while maintaining identity, memory, and creative influence.

The project serves as an experiment in multi-agent creativity, cultural preservation, and AI system design.
