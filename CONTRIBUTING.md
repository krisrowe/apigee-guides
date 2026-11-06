# Contributing

This repository holds Markdown architecture guides and the Jekyll layout used by GitHub Pages.

## 1. Site Structure

- **Markdown Source:** Guides live as standalone `.md` files and are indexed from [README.md](README.md) (`index.html` via `jekyll-readme-index`).
- **Layout & Diagrams:** [_config.yml](_config.yml) and [_layouts/default.html](_layouts/default.html) render Markdown tables and ```` ```mermaid ```` diagrams automatically on GitHub Pages while preserving GitHub-style heading anchors. `CONTRIBUTING.md` and `LICENSE` are excluded from the built site.

## 2. Editorial Conventions

- **Titles & Navigation:** Keep site headers, page titles, and prose focused directly on the technical subject matter. `apigeek.org` is used for custom-domain hosting and links rather than as a title or label in page copy.
- **Evidence & Tone:** Cite official product documentation and release notes inline, keep architectural comparisons neutral and constructive, and preserve the attribution footer in [_layouts/default.html](_layouts/default.html).
- **Examples & Identifiers:** Use reserved example domains (`example.com`, `internal.example.com`) and generic placeholders (`PROJECT_ID`, `ORGANIZATION_ID`, `123456789`) in configuration snippets.
