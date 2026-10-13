---
topic: Continuing Education
date: "2026-04-05"
work directory: /Users/tom/Documents/school/
status: active
github:
---
## Overview

A living project for hands-on technical learning. When working on projects (RF automation, data analysis, etc.), we frequently build interactive visualizations and educational tools to understand concepts deeply. This project gives those artifacts a permanent home so they're reusable, findable, and publishable.

The three goals are:
1. **Preserve** useful Streamlit apps and educational visualizations in a consistent location (`/Users/tom/Documents/school/visualizations/`)
2. **Catalog** them here so they're discoverable via Obsidian search and backlinks
3. **Publish** selected ones to the blog (pelicantpc) as a new content type for interactive/static educational posts

## Project Scope

### Visualization Library (`~/Documents/school/visualizations/`)

Each visualization gets its own subdirectory with a standard structure:

```
visualizations/
├── ook-signal-explorer/
│   ├── signal_explorer.py          # Streamlit app
│   ├── README.md                   # What it teaches, how to run it
│   ├── requirements.txt            # or pyproject.toml
│   └── assets/                     # screenshots, sample data
├── next-project-viz/
│   └── ...
```

When a new visualization is created in a project repo (like radiofrequency), copy or symlink it into this library with its dependencies.

### Blog Integration (pelicantpc)

TBD — likely a custom Pelican content type that generates static chart assets from each Streamlit app at build time. See [[pelicantpc]] for the blog project.

[tasks]

## User Profiles

|     |     |
| --- | --- |
| Learner | Tom — wants to understand electronics, RF, and data concepts through interactive exploration |
| Builder | Claude — builds the visualizations and educational tools during project work |

## Milestones

- [x] First Streamlit visualization created (OOK Signal Explorer, 2026-04-05)
- [x] Streamlit skill drafted for consistent future builds
- [ ] Set up `~/Documents/school/visualizations/` directory structure
- [ ] Copy OOK Signal Explorer as first entry
- [ ] Define Pelican content type for interactive posts
- [ ] Publish first visualization to blog

## Risks and Issues

- **Streamlit apps aren't static** — they need a running Python process. For the blog, we'll need to either export static assets (charts as PNGs/SVGs) or host them somewhere (Streamlit Community Cloud, etc.)
- **Dependency drift** — each visualization may pin different library versions. Using per-project pyproject.toml or requirements.txt mitigates this.

## Communication Plan

This is a solo learning project. Progress tracked here and in individual project CLAUDE.md files (e.g., [[radiofrequency]]).

## Project Deliverables

- `~/Documents/school/visualizations/` directory with standard structure
- This Obsidian project note as the catalog/index
- Pelican content type definition (when blog integration is designed)
- Each visualization cataloged here with a link to its directory and source project

## Visualization Catalog

| Name | Source Project | Topics | Location | Blog Post |
|------|---------------|--------|----------|-----------|
| OOK Signal Explorer | [[radiofrequency]] | RF, OOK modulation, pulse-distance encoding, rtl_fm | `visualizations/ook-signal-explorer/` | — |

## Project Success Criteria

- Any educational visualization we build during project work gets preserved here within the same session
- Visualizations are runnable from their directory with `streamlit run <file>.py` and no extra setup beyond `pip install -r requirements.txt`
- At least one visualization published to the blog as proof of concept for the content type

## Conclusion

This is an ongoing project — it grows whenever we build something worth keeping during other work.

## Open Questions

- What's the right hosting approach for interactive Streamlit apps on the blog? Options: Streamlit Community Cloud (free), static export with screenshots, or a self-hosted solution.
- Should the visualization library be its own git repo, or just a directory?
- How should we handle visualizations that depend on project-specific data files (like the sofucor_fan.yaml)?
