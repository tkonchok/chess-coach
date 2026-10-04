# Dependency license inventory

Reviewed installed package metadata on 2026-10-02. The project is GPL-3.0-or-later; see LICENSE and NOTICE. Public distribution remains pending container verification. The Docker build preserves Debian Stockfish notices, its exact package version, and corresponding source archives in `/app/notices/stockfish`. Verify these files in the built image before distributing it.

| Dependency | Installed version | License metadata |
|---|---|---|
| chess | 1.11.2 | GPL-3.0+ |
| Flask | 3.1.3 | BSD-3-Clause |
| Authlib | 1.8.0 | BSD-3-Clause |
| gunicorn | 23.0.0 | MIT |
| requests | 2.32.5 | Apache-2.0 |
| certifi | 2026.7.22 | MPL-2.0 |
| playwright | 1.63.0 | Apache-2.0 |

Stockfish is installed by Debian's package manager in the Dockerfile; the Dockerfile retains its installed notices and matching source archives. Local engine results used Stockfish 19, while the clean Debian image ships Stockfish 15.1-4, recorded in `/app/notices/stockfish/VERSION`. Engine-version differences can change selected positions.

Primary notices: [python-chess GPL license](https://github.com/niklasf/python-chess/blob/master/LICENSE.txt), [Stockfish source and license](https://github.com/official-stockfish/Stockfish), [Debian source packages](https://sources.debian.org/src/stockfish/). Review transitive package notices from the built image as part of its pending distribution check. The browser uses existing local SVG pieces from python-chess rather than downloading a board library from a CDN.

No dependency is fetched by the application at browser runtime. Pinned direct Python versions are in `requirements.txt`; transitive versions and the Debian base/engine are not fully locked. Record the image digest and dependency inventory for a reproducible released build.
