# CookDex

<p>
  <img alt="Release" src="https://img.shields.io/github/v/release/thekannen/cookdex?color=f47a2a&label=release">
  <img alt="Mealie 3.21 to 3.29" src="https://img.shields.io/badge/Mealie-3.21%E2%80%933.29-4caf50?labelColor=2e7d32&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/thekannen/cookdex?color=f47a2a">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ed?logo=docker&logoColor=white">
</p>

CookDex is a web UI for keeping a self-hosted [Mealie](https://mealie.io) recipe library clean, searchable, and well organized: import recipes, clean messy scraper results, keep categories and tags consistent, schedule maintenance jobs, and review library health. Every cleanup task previews its changes first.

**Documentation: [knownframe.com/cookdex/docs](https://knownframe.com/cookdex/docs/)**

![CookDex overview](https://knownframe.com/branding/cookdex-overview.png)

A clean library also makes native Mealie clients better.
[Forked](https://apps.apple.com/us/app/forked-recipes/id6760947117), also from
Knownframe, turns your recipes into swipe-based discovery, meal plans, and one
persistent shopping list on your iPhone. Its roadmap and feature requests are at
[Knownframe/forked-for-mealie](https://github.com/Knownframe/forked-for-mealie).

## Quick Start

```bash
mkdir -p cookdex && cd cookdex
curl -fsSL https://raw.githubusercontent.com/thekannen/cookdex/main/compose.ghcr.yml -o compose.yaml
docker compose pull cookdex
docker compose up -d cookdex
```

Open `https://your-server:4820/cookdex`, accept the self-signed certificate warning, and create the first admin account. Then follow [Getting started](https://knownframe.com/cookdex/docs/getting-started/).

## Documentation

- [Install](https://knownframe.com/cookdex/docs/install/): volumes, image tags, secrets and updating
- [Getting started](https://knownframe.com/cookdex/docs/getting-started/): first login and a first safe run
- [Task reference](https://knownframe.com/cookdex/docs/tasks/): every task's options; see also [Scheduling and automations](https://knownframe.com/cookdex/docs/scheduling/) and [Safety policies](https://knownframe.com/cookdex/docs/safety-policies/)
- [Data maintenance](https://knownframe.com/cookdex/docs/data-maintenance/) · [Database connection](https://knownframe.com/cookdex/docs/database-connection/) · [Recipe Dredger](https://knownframe.com/cookdex/docs/recipe-dredger/)
- [Troubleshooting](https://knownframe.com/cookdex/docs/troubleshooting/) · [Privacy and safety](https://knownframe.com/cookdex/docs/privacy-and-safety/)

For contributors: [Local Dev](docs/LOCAL_DEV.md), [API routes](docs/API.md), [Providers](docs/PROVIDERS.md), [CONTRIBUTING.md](CONTRIBUTING.md).

## Getting Help

- The **Help** page inside CookDex documents every task and setting in place.
- Bugs and feature requests: [open an issue](https://github.com/thekannen/CookDex/issues).

## Contributing

CookDex is AGPL-3.0 and contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). If CookDex is useful to you, starring the repo helps other Mealie users find it.

## Support

CookDex is free and built in my spare time. If it saves you time, [sponsoring on GitHub](https://github.com/sponsors/thekannen) helps cover hosting and the test Mealie instance every release is checked against. One-time tips are welcome too.
