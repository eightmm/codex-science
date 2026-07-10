# Science Skills

[![Install via skills.sh](https://img.shields.io/badge/skills.sh-install-green)](https://skills.sh/google-deepmind/science-skills)

A collection of agent skills for scientific research tasks, spanning genomics,
structural biology, cheminformatics, literature search, and more.

Each skill provides structured instructions, scripts, and resources that extend
an AI agent's capabilities for specialized scientific tasks.

## Skill Structure

Each skill directory contains:

-   **SKILL.md** — Main instruction file with YAML frontmatter and detailed
    markdown instructions
-   **scripts/** — Helper scripts and utilities
-   **references/** — Additional documentation and references (optional)

## Getting started with GDM Science Skills

Install the Science Skills bundle via
[npx](https://docs.npmjs.com/cli/commands/npx) using:

```bash
npx skills add google-deepmind/science-skills/
```

## Using science skills with [Google Antigravity](https://antigravity.google/)

If you're a new Google Antigravity user:

-   Launch the application after downloading Google Antigravity and check the
    box for Science at the 'Build with Google' step - this will install the
    curated collection of our Science Skills.

If you're an existing Google Antigravity user:

-   Update to the latest version then open Settings -> Customizations -> Build
    with Google Plugins (click on 'Customize' at the bottom of the page) ->
    Download the `Science` plugin

### Prerequisites

We use the `uv` package manager to handle dependencies. The first time you
trigger a Science Skill, the agent will ask for approval and install `uv`, and
then proceed to respond to your scientific query / task. We recommend restarting
Antigravity after this first time installation.

Some skills, such as AlphaGenome and OpenAlex, require an API key to function.
Others, such as ClinVar, benefit from an API key to unlock higher rate limits
but are still functional without one. The agent should prompt you to obtain the
API key and guide you through writing in the correct location. However, if you
would rather do this yourself, you can run a command like this in your terminal:
`echo "ALPHAGENOME_API_KEY=your_actual_api_key" >> ~/.env`

### Customizing or Creating Skills

If you want to customize an existing Science Skill or create a new skill of your
own, you should **not** modify the files inside the Antigravity Science plugin
installation directory, as your changes will be overwritten whenever the plugin
is updated. Instead, place your custom or modified skills elsewhere, e.g. in
your personal skills directory:

```
~/.gemini/config/skills/
```

## Links

You can find examples of Science Skills use cases, including a demo, at
[antigravity.google/use-cases/science](https://antigravity.google/use-cases/science).

We have also published a
[technical report](https://storage.googleapis.com/deepmind-media/papers/google_deepmind_science_skills_for_antigravity_towards_efficient_and_reliable_scientific_workflows.pdf)
on the Science Skills.

## Licensing & Disclaimer

Copyright 2026 Google LLC

All software is licensed under the Apache License, Version 2.0 (Apache 2.0); you
may not use this file except in compliance with the Apache 2.0 license. You may
obtain a copy of the Apache 2.0 license at:
https://www.apache.org/licenses/LICENSE-2.0

As set out in the attached file
‘[Skill Licences and Terms of Use](SKILL_LICENSES.md)’ certain third party data
sources referenced within individual Skill files have their own applicable
licenses and/or terms of use. See the
‘[Skill Licences and Terms of Use](SKILL_LICENSES.md)’ file for more
information. You are responsible for ensuring that your use of individual Skill
files complies with any such applicable licenses/ terms of use.

All other materials are licensed under the Creative Commons Attribution 4.0
International License (CC-BY). You may obtain a copy of the CC-BY license at:
https://creativecommons.org/licenses/by/4.0/legalcode

Unless required by applicable law or agreed to in writing, all software and
materials distributed here under the Apache 2.0 or CC-BY licenses are
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the licenses for the specific language governing
permissions and limitations under those licenses.

This is not an official Google product.
