# Changelog

## [0.13.1](https://github.com/djkix/magazine-search/compare/v0.13.0...v0.13.1) (2026-08-31)


### Bug Fixes

* locate the real sommaire page and recognize more layouts ([7585d65](https://github.com/djkix/magazine-search/commit/7585d658253ef530621996b59ef52d1deaf8a17f))

## [0.13.0](https://github.com/djkix/magazine-search/compare/v0.12.0...v0.13.0) (2026-08-31)


### Features

* expose today's Gemini request usage in settings and logs ([4f3f64a](https://github.com/djkix/magazine-search/commit/4f3f64a4adebad95e22429f3945e8cd1f7a8ed4e))

## [0.12.0](https://github.com/djkix/magazine-search/compare/v0.11.0...v0.12.0) (2026-08-29)


### Features

* add per-minute Gemini rate limiting and quota self-healing ([ceed07e](https://github.com/djkix/magazine-search/commit/ceed07ed7de2f794639a029324e0324dec957eb3))
* batch sommaire/theme extraction across several magazines per request ([4872061](https://github.com/djkix/magazine-search/commit/4872061e3181539a2465bd7fd96e8f089ebab166))


### Bug Fixes

* load PDFs via HTTP Range requests instead of downloading whole file ([4610528](https://github.com/djkix/magazine-search/commit/461052802122c5dbbf50766fa067eddbbc814d0a))

## [0.11.0](https://github.com/djkix/magazine-search/compare/v0.10.1...v0.11.0) (2026-08-29)


### Features

* self-throttle Gemini calls to stay under the account's daily quota ([d1d5ec4](https://github.com/djkix/magazine-search/commit/d1d5ec4f69965e92a5354a8c2ca634b084af9204))


### Bug Fixes

* recover magazines orphaned by a worker restart mid-job ([4df9d90](https://github.com/djkix/magazine-search/commit/4df9d90bb592e0c0b01505460874cc4d2419b166))

## [0.10.1](https://github.com/djkix/magazine-search/compare/v0.10.0...v0.10.1) (2026-08-29)


### Bug Fixes

* stop OCR crashing on NUL bytes, surface silent sommaire/thème failures ([0574271](https://github.com/djkix/magazine-search/commit/0574271754dfe3f39eb63d2440c29934c17c694b))

## [0.10.0](https://github.com/djkix/magazine-search/compare/v0.9.0...v0.10.0) (2026-08-29)


### Features

* add year/HS/SP sidebar filter and clickable dashboard status counters ([d0221ed](https://github.com/djkix/magazine-search/commit/d0221edecadc21fd4e07def7982889c3855294ff))


### Bug Fixes

* auto-fail hung OCR jobs and correct HS/Spécial year/numéro parsing ([a8fe466](https://github.com/djkix/magazine-search/commit/a8fe466d776436748b88004310d9df2d99278c46))

## [0.9.0](https://github.com/djkix/magazine-search/compare/v0.8.1...v0.9.0) (2026-08-28)


### Features

* replace manual collection-wide theme summary with automatic per-magazine themes ([5f06e45](https://github.com/djkix/magazine-search/commit/5f06e451f1cb31b68220c43450edc9ed25759260))
* show cross-magazine search results in the PDF viewer sidebar ([9717369](https://github.com/djkix/magazine-search/commit/9717369b0cf3ae25b03711f40ddf3f56d3db3190))


### Bug Fixes

* second TS build error in collection sommaire search view ([a19294d](https://github.com/djkix/magazine-search/commit/a19294d477e0afd6e2698da94120569a282656d5))
* TS build error in collection sommaire pagination ([79244af](https://github.com/djkix/magazine-search/commit/79244af15a81e029721a5cca937ca5efaa6ac8bf))

## [0.8.1](https://github.com/djkix/magazine-search/compare/v0.8.0...v0.8.1) (2026-08-28)


### Bug Fixes

* remove hover zoom on library/collection cover thumbnails ([eb2438c](https://github.com/djkix/magazine-search/commit/eb2438cd82404d6fabe38293b7957553aed8792c))

## [0.8.0](https://github.com/djkix/magazine-search/compare/v0.7.1...v0.8.0) (2026-08-28)


### Features

* parse issue number/date/month from title, add Gemini thematic sommaire ([33139e1](https://github.com/djkix/magazine-search/commit/33139e12ad4a8f8de7e08c4859d980fb00d94d66))

## [0.7.1](https://github.com/djkix/magazine-search/compare/v0.7.0...v0.7.1) (2026-08-28)


### Bug Fixes

* search tags scope directly, no collection drill-down step ([d83fe81](https://github.com/djkix/magazine-search/commit/d83fe8198e086993e3362a0c37dd60188c87ba7b))

## [0.7.0](https://github.com/djkix/magazine-search/compare/v0.6.1...v0.7.0) (2026-08-28)


### Features

* color-code search result occurrence counts from gray to green ([7dd2d0d](https://github.com/djkix/magazine-search/commit/7dd2d0da332f5d5ddd61e486efd3e9ef417b1bfc))

## [0.6.1](https://github.com/djkix/magazine-search/compare/v0.6.0...v0.6.1) (2026-08-28)


### Bug Fixes

* derive collection from the top-level NAS directory, not the immediate parent ([1adff77](https://github.com/djkix/magazine-search/commit/1adff77e844b7c60133715b9e02ed2cf9512dac8))

## [0.6.0](https://github.com/djkix/magazine-search/compare/v0.5.0...v0.6.0) (2026-08-28)


### Features

* rename category to tag (many-to-many), issue metadata, magazine-grouped search ([02ea114](https://github.com/djkix/magazine-search/commit/02ea114095037e7af7fb500f1c9971ab263cc5dd))


### Bug Fixes

* backfill collections for pre-existing magazines, persist scan progress, surface OCR errors ([9fe5641](https://github.com/djkix/magazine-search/commit/9fe564128df5a21cf4977fdee9f2be6918d14645))
* detect relocated PDFs during scan, rename button, tidy error display ([07ad3a3](https://github.com/djkix/magazine-search/commit/07ad3a3ee5bed13c1868bf5653f3d9049b590702))

## [0.5.0](https://github.com/djkix/magazine-search/compare/v0.4.0...v0.5.0) (2026-08-27)


### Features

* add a progress bar to the admin dashboard scan job status ([dfa355c](https://github.com/djkix/magazine-search/commit/dfa355cf224d79263b66223016c9fd3a6399af50))
* add an admin Logs page with level/component filters and rotation ([e96adf0](https://github.com/djkix/magazine-search/commit/e96adf095fb46427b405355ba5bece3cbdf31334))
* derive collections automatically from the NAS directory structure ([7afe086](https://github.com/djkix/magazine-search/commit/7afe08696a5207642463d736dff428b4378e5917))
* extract per-magazine table of contents via Gemini ([43b8c3d](https://github.com/djkix/magazine-search/commit/43b8c3df4d5d3d0f2bf6414f825bf86a8a962dcb))
* group magazines by category (theme) across sommaires and library ([2255a50](https://github.com/djkix/magazine-search/commit/2255a5084c6cf6b1f959c7b3cbcad4e7c5c56b4c))
* publish images directly on push to main, cap worker CPU/memory ([56ac8e6](https://github.com/djkix/magazine-search/commit/56ac8e68103cae9eea15d502c7776b1fc0e0d9cf))
* restructure categories into a two-level category/collection hierarchy ([36dfea0](https://github.com/djkix/magazine-search/commit/36dfea04bafe53ecc93aeb1b025927a2d1881fb7))
* search filter by collection, rank results by magazine relevance and recency ([674f9f6](https://github.com/djkix/magazine-search/commit/674f9f61ed1d150fca44f7d872ab044b7e1a6549))
* two-level library view grouped by collection ([a1e6693](https://github.com/djkix/magazine-search/commit/a1e6693c9bda923c9c0743be062336ed94d6556a))
* two-level sommaires view grouped by collection ([c67a1b8](https://github.com/djkix/magazine-search/commit/c67a1b88459d1d02dfa8d626ca3169c3fdda482a))
* wire category filtering into full-text search ([9080dea](https://github.com/djkix/magazine-search/commit/9080dea6591640e038bab7d59f551c7ef8a300b4))


### Bug Fixes

* bump pydantic to satisfy google-genai's dependency constraint ([526153c](https://github.com/djkix/magazine-search/commit/526153c058ddc483fb360ff5de7c1ad2b86edb7a))
* capture uvicorn logs, add Gemini model picker, restore version badge, continuous-scroll viewer ([3787fb9](https://github.com/djkix/magazine-search/commit/3787fb90d9d62a9d94f2d0844d1fa6b523ee8c0e))
* pin pikepdf&lt;10 and preserve search query across viewer navigation ([60c42a0](https://github.com/djkix/magazine-search/commit/60c42a05a206c298eb567d9d75042b7f9b06cad6))
* show the last real release version instead of dev-&lt;sha&gt; in the UI ([cc5b873](https://github.com/djkix/magazine-search/commit/cc5b873da991443cd961af9c46f706eb9200ac82))
* TS build error in PdfViewer, sync page counter to scroll, add reprocess action ([976466a](https://github.com/djkix/magazine-search/commit/976466a755abe98bd14886d1215c22136ae9c974))

## [0.4.0](https://github.com/djkix/magazine-search/compare/v0.3.1...v0.4.0) (2026-08-27)


### Features

* add a retry button for magazines that failed processing ([9ff9fc3](https://github.com/djkix/magazine-search/commit/9ff9fc3a2b33fb7a83e3ee683036f5f655f057cb))


### Bug Fixes

* stop NAS_MOUNT_PATH host value leaking into the container ([b1a7ff5](https://github.com/djkix/magazine-search/commit/b1a7ff532bf95cbb3fb5ac3c79941dbcc0989112))

## [0.3.1](https://github.com/djkix/magazine-search/compare/v0.3.0...v0.3.1) (2026-08-26)


### Bug Fixes

* exclude /api from the auth-redirect middleware matcher ([7d9f783](https://github.com/djkix/magazine-search/commit/7d9f7830aeccd16c6a64ebddd2757f4b9e6668df))

## [0.3.0](https://github.com/djkix/magazine-search/compare/v0.2.0...v0.3.0) (2026-08-26)


### Features

* proxy /api through the frontend so only one port needs exposing ([1fed57d](https://github.com/djkix/magazine-search/commit/1fed57da5c0b792a161d62c43f3686d8c748cea2))

## [0.2.0](https://github.com/djkix/magazine-search/compare/v0.1.5...v0.2.0) (2026-08-26)


### Features

* display app version in the UI and publish it with releases ([c0f63c5](https://github.com/djkix/magazine-search/commit/c0f63c519bb87af6c3634406d2c87fc7eca7ede8))


### Bug Fixes

* address top 10 findings from full codebase review ([e8c1244](https://github.com/djkix/magazine-search/commit/e8c1244418cde8eb010b4fb6b6dc9d3f40fe6c13))
* fall back to /api when NEXT_PUBLIC_API_URL is baked in empty ([7d91515](https://github.com/djkix/magazine-search/commit/7d91515a14acb270469a07f649d31036c5690924))

## [0.1.5](https://github.com/djkix/magazine-search/compare/v0.1.4...v0.1.5) (2026-08-26)


### Bug Fixes

* add missing email-validator dependency for pydantic EmailStr ([f55364f](https://github.com/djkix/magazine-search/commit/f55364fdf74bc4a6c6dcd1931a0fca7b3df7fe66))
* pull GHCR images in docker-compose.yml instead of local builds ([3e967a3](https://github.com/djkix/magazine-search/commit/3e967a374194f7443240f3fe7aacd4fbe4025fc5))

## [0.1.4](https://github.com/djkix/magazine-search/compare/v0.1.3...v0.1.4) (2026-08-26)


### Bug Fixes

* serve pdfjs-dist worker as a static file instead of bundling it ([4436ccf](https://github.com/djkix/magazine-search/commit/4436ccf1b42e9d31fc9dec48015aefeff00d6548))
* serve pdfjs-dist worker as a static file instead of bundling it ([43ee277](https://github.com/djkix/magazine-search/commit/43ee277871ceafa7c20f5fe50f5a701e27f3f8ca))

## [0.1.3](https://github.com/djkix/magazine-search/compare/v0.1.2...v0.1.3) (2026-08-26)


### Bug Fixes

* separate CI and publish GHA cache scopes to avoid write conflicts ([c9abc89](https://github.com/djkix/magazine-search/commit/c9abc89de28a35df76c5a0cec3e400a0157e4a20))
* separate CI and publish GHA cache scopes to avoid write conflicts ([e72afd0](https://github.com/djkix/magazine-search/commit/e72afd0693f68bea758dc96312d132a67b973813))
* skip Terser minification for pdfjs-dist worker file ([41e8b88](https://github.com/djkix/magazine-search/commit/41e8b88e856558b5dbd1b0aa8a5f8fa20eab3aa9))
* skip Terser minification for pdfjs-dist worker file ([436acf4](https://github.com/djkix/magazine-search/commit/436acf41b566d4ef68f1e67de25adc987e2b2c36))

## [0.1.2](https://github.com/djkix/magazine-search/compare/v0.1.1...v0.1.2) (2026-08-26)


### Performance Improvements

* enable GitHub Actions cache in CI docker builds ([b478c45](https://github.com/djkix/magazine-search/commit/b478c452411e69491a9ebe60bd4dbb96cb09779f))
* enable GitHub Actions cache in CI docker builds ([263bdff](https://github.com/djkix/magazine-search/commit/263bdff0e5cf7701e2e0a930a2ab05344a54fb20))

## [0.1.1](https://github.com/djkix/magazine-search/compare/v0.1.0...v0.1.1) (2026-08-26)


### Bug Fixes

* cap CI and image build jobs with timeout-minutes ([3c99323](https://github.com/djkix/magazine-search/commit/3c993234c8cc2895eb8b0c55e81c4c76a3139455))
* publish latest tag alongside semver on release ([b989d86](https://github.com/djkix/magazine-search/commit/b989d869f59e49bcfae9c50832682bcbbe635de7))


### Performance Improvements

* enable GitHub Actions cache for docker builds ([ce757d2](https://github.com/djkix/magazine-search/commit/ce757d2b052ef1fa08d877844deede35b20077e5))
