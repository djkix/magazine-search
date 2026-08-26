# Changelog

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
