# Changelog

## [0.24.2](https://github.com/djkix/magazine-search/compare/v0.24.1...v0.24.2) (2026-09-11)


### Bug Fixes

* **gemini:** borner aussi le nombre total de tentatives ([c5b6e77](https://github.com/djkix/magazine-search/commit/c5b6e77eb5eac03175114b0f95dd63c4a6fd8495))
* **gemini:** borner les appels a l'API ([38f0b76](https://github.com/djkix/magazine-search/commit/38f0b76af715c43ceb705dc312b476ae214cc846))

## [0.24.1](https://github.com/djkix/magazine-search/compare/v0.24.0...v0.24.1) (2026-09-11)


### Bug Fixes

* **logs:** écrire les horodatages dans le fuseau local, décalage inclus ([8bf946c](https://github.com/djkix/magazine-search/commit/8bf946c9bf4d58561b2236bda132ace2c7a9536d))

## [0.24.0](https://github.com/djkix/magazine-search/compare/v0.23.3...v0.24.0) (2026-09-11)


### Features

* **deploiement:** sauvegarder avant migration et sortir de la boucle d'echec ([165cd07](https://github.com/djkix/magazine-search/commit/165cd0778e8ec1ea31242f00a205f1724aa43f94))


### Bug Fixes

* **docker:** détecter le nom de code Debian au lieu de le figer en dur ([54bc1d8](https://github.com/djkix/magazine-search/commit/54bc1d879ede0e47c11a6936ab1e54cc5530bc95))

## [0.23.3](https://github.com/djkix/magazine-search/compare/v0.23.2...v0.23.3) (2026-09-11)


### Bug Fixes

* **ocr:** réparer la structure du PDF via qpdf en dernier recours ([0df3610](https://github.com/djkix/magazine-search/commit/0df3610187d155c0a1a4dfbd224afbcb0d7ec861))

## [0.23.2](https://github.com/djkix/magazine-search/compare/v0.23.1...v0.23.2) (2026-09-11)


### Bug Fixes

* **db:** ne pas recreer un index deja pose par 0005 ([cb664b2](https://github.com/djkix/magazine-search/commit/cb664b22291dd3f07d94647e394957cadf78df01))

## [0.23.1](https://github.com/djkix/magazine-search/compare/v0.23.0...v0.23.1) (2026-09-10)


### Bug Fixes

* **lecteur:** conserver les resultats de recherche apres un clic ([b209494](https://github.com/djkix/magazine-search/commit/b209494881a8c05b1398a46ed5425442bee2b9e9))
* **lecteur:** ramener la fleche de retour vers la collection du numero ([bab7d30](https://github.com/djkix/magazine-search/commit/bab7d30bf0a60aa0113a0b73f3e1d608d22aec2f))

## [0.23.0](https://github.com/djkix/magazine-search/compare/v0.22.10...v0.23.0) (2026-09-10)


### Features

* **admin:** afficher l'avancement de la thematisation ([5bf4e29](https://github.com/djkix/magazine-search/commit/5bf4e292e51d74be53b63298e5ef5de09ba8be5b))
* **themes:** page thematiques triee par occurrences ([d11ae27](https://github.com/djkix/magazine-search/commit/d11ae27b8691b986c5e36734164ae9848bd4ce96))


### Bug Fixes

* **themes:** surligner le bon terme dans les titres d'articles ([a5319e2](https://github.com/djkix/magazine-search/commit/a5319e2c81ad249c5c4a34a4e6e8b8196305ba92))

## [0.22.10](https://github.com/djkix/magazine-search/compare/v0.22.9...v0.22.10) (2026-09-10)


### Bug Fixes

* **ocr:** retenter en --force-ocr sur un flux image corrompu ([348c5bc](https://github.com/djkix/magazine-search/commit/348c5bcc2f18f61097dcaca0c444b67ac18c250f))

## [0.22.9](https://github.com/djkix/magazine-search/compare/v0.22.8...v0.22.9) (2026-09-10)


### Bug Fixes

* **ocr:** remonter la cause reelle d'un echec ocrmypdf ([4e7754e](https://github.com/djkix/magazine-search/commit/4e7754ec1c24e8bfdb8ef5d4c614316630bc079c))

## [0.22.8](https://github.com/djkix/magazine-search/compare/v0.22.7...v0.22.8) (2026-09-10)


### Bug Fixes

* **sommaire:** ne plus fabriquer d'entrees a partir de prose ([f1a396a](https://github.com/djkix/magazine-search/commit/f1a396a79d5945c09c4907f971d668f674281511))

## [0.22.7](https://github.com/djkix/magazine-search/compare/v0.22.6...v0.22.7) (2026-09-10)


### Bug Fixes

* **admin:** separer reextraction du sommaire et OCR complet ([1b3006e](https://github.com/djkix/magazine-search/commit/1b3006ee19a50791515705118ba1fee376b43d9f))

## [0.22.6](https://github.com/djkix/magazine-search/compare/v0.22.5...v0.22.6) (2026-09-10)


### Bug Fixes

* **sommaire:** accepter le separateur entre numero et titre ([3ec82b8](https://github.com/djkix/magazine-search/commit/3ec82b83a84892ed18eff2c0be9ec2f9dc8bc715))

## [0.22.5](https://github.com/djkix/magazine-search/compare/v0.22.4...v0.22.5) (2026-09-10)


### Bug Fixes

* **sommaire:** reconnaître un intitulé de rubrique tout en minuscules ([1c9f7f9](https://github.com/djkix/magazine-search/commit/1c9f7f964c07dfe2d2c4b148e62b0331fc8ba744))

## [0.22.4](https://github.com/djkix/magazine-search/compare/v0.22.3...v0.22.4) (2026-09-10)


### Bug Fixes

* ne plus dupliquer numéro/date quand le nom de collection est absent ([4b09d47](https://github.com/djkix/magazine-search/commit/4b09d471a51d705cff3eef3157756badf51d64f6))

## [0.22.3](https://github.com/djkix/magazine-search/compare/v0.22.2...v0.22.3) (2026-09-10)


### Bug Fixes

* **sommaire:** consigner pourquoi aucune entrée n'a été extraite ([f573f6b](https://github.com/djkix/magazine-search/commit/f573f6b88351580f5e873022e1d846104f498fd8))

## [0.22.2](https://github.com/djkix/magazine-search/compare/v0.22.1...v0.22.2) (2026-09-10)


### Bug Fixes

* **themes:** ramener THEME_BATCH_SIZE à 20 d'après la mesure réelle ([c6fb13b](https://github.com/djkix/magazine-search/commit/c6fb13bc8a6b2e775d14801ad87b56db9d9ec209))

## [0.22.1](https://github.com/djkix/magazine-search/compare/v0.22.0...v0.22.1) (2026-09-10)


### Bug Fixes

* **themes:** ramener THEME_BATCH_SIZE à 20 d'après la mesure réelle ([63b4722](https://github.com/djkix/magazine-search/commit/63b4722ca303760a254f435255aaaf54081efd63))

## [0.22.0](https://github.com/djkix/magazine-search/compare/v0.21.0...v0.22.0) (2026-09-10)


### Features

* étendre "magazine - numéro - Mois année" aux résultats de recherche globale ([651aac6](https://github.com/djkix/magazine-search/commit/651aac661e38fd64c096d290b16903a995134fb4))


### Bug Fixes

* **themes:** ne plus détruire les thèmes avant régénération ([bda7190](https://github.com/djkix/magazine-search/commit/bda7190fc8a009fb61685d8058a24cb40963c40c))

## [0.21.0](https://github.com/djkix/magazine-search/compare/v0.20.5...v0.21.0) (2026-09-10)


### Features

* afficher "magazine - numéro - Mois année" au lieu du nom de fichier brut ([fc22843](https://github.com/djkix/magazine-search/commit/fc22843800dae0bae79b56adff7228ad3c5d5be5))

## [0.20.5](https://github.com/djkix/magazine-search/compare/v0.20.4...v0.20.5) (2026-09-10)


### Bug Fixes

* résoudre le conflit de dépendances httpx et la panne CI de test_authorization ([9abe3c2](https://github.com/djkix/magazine-search/commit/9abe3c25660a07e6303d850fd1ef0959b2cc27af))

## [0.20.4](https://github.com/djkix/magazine-search/compare/v0.20.3...v0.20.4) (2026-09-09)


### Bug Fixes

* don't let progress-cleanup failures swallow the original error or leak connections ([eb91660](https://github.com/djkix/magazine-search/commit/eb91660c305a15a3d148dda7ef92e8908e3c57c0))

## [0.20.3](https://github.com/djkix/magazine-search/compare/v0.20.2...v0.20.3) (2026-09-09)


### Bug Fixes

* bound admin lists, dry-run dedup, ocrmypdf timeout, sanitized errors ([9074fa0](https://github.com/djkix/magazine-search/commit/9074fa0a0f74a5955a78b4184a39a9612545bbd7))
* bound Meilisearch client with an explicit HTTP timeout ([c7e61ff](https://github.com/djkix/magazine-search/commit/c7e61ff0f55cd8c7f6046baa63ec2777ad1a94db))
* ocr_timeout_seconds setting, atomic Redis incr+expire for Gemini quota ([be8cddd](https://github.com/djkix/magazine-search/commit/be8cdddcf5bd351fe787502e3bceb8485f651d95))

## [0.20.2](https://github.com/djkix/magazine-search/compare/v0.20.1...v0.20.2) (2026-09-09)


### Bug Fixes

* JWT hardening, timing-safe login, LIKE escaping, close API docs ([8c45d09](https://github.com/djkix/magazine-search/commit/8c45d09f0533524a9bf7de7c7ff5f36b91e888af))

## [0.20.1](https://github.com/djkix/magazine-search/compare/v0.20.0...v0.20.1) (2026-09-09)


### Bug Fixes

* clear stale session cookie on 401 instead of looping to login ([a17b3f5](https://github.com/djkix/magazine-search/commit/a17b3f54e9e7822f2096ba80ca7005a3356a54d0))

## [0.20.0](https://github.com/djkix/magazine-search/compare/v0.19.1...v0.20.0) (2026-09-09)


### Features

* **frontend:** en-têtes de sécurité HTTP et script typecheck ([7ebc4af](https://github.com/djkix/magazine-search/commit/7ebc4af34d169e927708e52eda5ab0e3eb16f801))


### Bug Fixes

* **backend:** fail-fast sur les secrets, CORS strict, rate limiting Redis ([21937e4](https://github.com/djkix/magazine-search/commit/21937e46bd66245a298e9e53db1b46b32306cd8e))
* **infra:** fermer le backend, cloisonner les secrets, sauvegarder Postgres ([e1e0869](https://github.com/djkix/magazine-search/commit/e1e086914ef2ba3b87ede2dbbcd0fa9c89b06b8a))
* revue de sécurité — secrets, CORS, rate limiting, backup Postgres ([4024e0b](https://github.com/djkix/magazine-search/commit/4024e0b8fa77addea3e7628581d39a43bdb58794))

## [0.19.1](https://github.com/djkix/magazine-search/compare/v0.19.0...v0.19.1) (2026-09-08)


### Bug Fixes

* find-in-document search state wiped by page navigation ([4fa4292](https://github.com/djkix/magazine-search/commit/4fa4292814042acc60876c8979340fedd1934c94))

## [0.19.0](https://github.com/djkix/magazine-search/compare/v0.18.0...v0.19.0) (2026-09-08)


### Features

* date/issue number on search results, find-in-document navigation ([d9f3976](https://github.com/djkix/magazine-search/commit/d9f39768af1d337371ff55eb8b65402a0eba4d31))

## [0.18.0](https://github.com/djkix/magazine-search/compare/v0.17.3...v0.18.0) (2026-09-07)


### Features

* visually separate normal issues from HS/SP in the library grid ([5d14829](https://github.com/djkix/magazine-search/commit/5d14829826e1339d7799abe5fb9892f56049b2cd))

## [0.17.3](https://github.com/djkix/magazine-search/compare/v0.17.2...v0.17.3) (2026-09-07)


### Bug Fixes

* retired Gemini model, show per-article detail in theme view ([33c1e06](https://github.com/djkix/magazine-search/commit/33c1e0619ae9aaaa36b7fa38f684454f5b614de1))

## [0.17.2](https://github.com/djkix/magazine-search/compare/v0.17.1...v0.17.2) (2026-09-06)


### Bug Fixes

* batch the "regenerate all themes" bulk action instead of one request per magazine ([2d230bf](https://github.com/djkix/magazine-search/commit/2d230bf131d497c1c4946dd66b2d515830775b3c))

## [0.17.1](https://github.com/djkix/magazine-search/compare/v0.17.0...v0.17.1) (2026-09-04)


### Bug Fixes

* prevent DuplicatePreparedStatement from a connection shared across fork ([2555b0d](https://github.com/djkix/magazine-search/commit/2555b0d8c6e9909a47151f5060c4918cf4aa0ca1))

## [0.17.0](https://github.com/djkix/magazine-search/compare/v0.16.4...v0.17.0) (2026-09-03)


### Features

* publication date in viewer search results, fix quota counter inflation ([8c53790](https://github.com/djkix/magazine-search/commit/8c53790fe6c8ef762001c5d25814034c6073978d))

## [0.16.4](https://github.com/djkix/magazine-search/compare/v0.16.3...v0.16.4) (2026-09-02)


### Bug Fixes

* false sommaire-heading match and word-level column splitting ([e896d9e](https://github.com/djkix/magazine-search/commit/e896d9e2dabf42d20ff6c5a1c6f64732c272be9f))

## [0.16.3](https://github.com/djkix/magazine-search/compare/v0.16.2...v0.16.3) (2026-09-02)


### Bug Fixes

* prevent and clean up duplicate article rows from concurrent extraction ([bb68548](https://github.com/djkix/magazine-search/commit/bb685487a4d19572b8ffae889fdbc40e0a943d21))

## [0.16.2](https://github.com/djkix/magazine-search/compare/v0.16.1...v0.16.2) (2026-09-02)


### Bug Fixes

* dot-leader parsing, garbled-text detection, and theme quota leak ([e50c723](https://github.com/djkix/magazine-search/commit/e50c723ae0cfb168ac55c730e924f070cfab16bc))

## [0.16.1](https://github.com/djkix/magazine-search/compare/v0.16.0...v0.16.1) (2026-09-02)


### Bug Fixes

* try all sommaire reading-order strategies and keep the best result ([8a64c8a](https://github.com/djkix/magazine-search/commit/8a64c8a2a62d2ce42aa4287973ac68f7c23ac2a9))

## [0.16.0](https://github.com/djkix/magazine-search/compare/v0.15.2...v0.16.0) (2026-09-02)


### Features

* auto-refresh admin dashboard and show OCR progress percentage ([b5de082](https://github.com/djkix/magazine-search/commit/b5de0824bb0ec6a4352faf72ca285f587941d6ba))

## [0.15.2](https://github.com/djkix/magazine-search/compare/v0.15.1...v0.15.2) (2026-09-02)


### Bug Fixes

* try alternate reading orders only as a fallback, not by default ([42ec65f](https://github.com/djkix/magazine-search/commit/42ec65f30c2606577fdcecf4b1bf7af5c251bdbc))

## [0.15.1](https://github.com/djkix/magazine-search/compare/v0.15.0...v0.15.1) (2026-09-01)


### Bug Fixes

* track real last-activity time for magazines instead of first-added date ([e3afe81](https://github.com/djkix/magazine-search/commit/e3afe81296a5a711093ab01383b64d97f97d332e))

## [0.15.0](https://github.com/djkix/magazine-search/compare/v0.14.1...v0.15.0) (2026-09-01)


### Features

* add year/HS/SP sidebar filter to the collection sommaires view ([1291626](https://github.com/djkix/magazine-search/commit/1291626edf731dbc2263b50e45de4ace7e61ad08))


### Bug Fixes

* surface queued/pending magazines on the admin dashboard ([6daa32d](https://github.com/djkix/magazine-search/commit/6daa32d67f78125e315d8d8588d101ecdaf8a546))

## [0.14.1](https://github.com/djkix/magazine-search/compare/v0.14.0...v0.14.1) (2026-09-01)


### Bug Fixes

* paginate "Tous" article view instead of requesting an oversized limit ([fb17333](https://github.com/djkix/magazine-search/commit/fb1733321181f8879c8051b63be66c4fd933bfde))


### Performance Improvements

* prepare for a much larger library (800+ magazines) ([c9252cf](https://github.com/djkix/magazine-search/commit/c9252cf5307941f0325d2b4c8f1c298b0739f7ab))

## [0.14.0](https://github.com/djkix/magazine-search/compare/v0.13.3...v0.14.0) (2026-09-01)


### Features

* add "sans sommaire" dashboard filter and bulk reprocess action ([73577b5](https://github.com/djkix/magazine-search/commit/73577b5486e7cbea777fcb2ed178003cd6fe53ed))


### Bug Fixes

* read rotated log backups and keep exception tracebacks in logs ([76f7a0a](https://github.com/djkix/magazine-search/commit/76f7a0afb96cb3ca393176ad7ea274e76c888c8a))

## [0.13.3](https://github.com/djkix/magazine-search/compare/v0.13.2...v0.13.3) (2026-08-31)


### Bug Fixes

* recognize multi-word sommaire headings and search further into the magazine ([7facbca](https://github.com/djkix/magazine-search/commit/7facbca55bdf73b766a1acbde16135d427dd2b01))
* reconstruct visual reading order for multi-column pages ([0497a9b](https://github.com/djkix/magazine-search/commit/0497a9bae1f475159ff914bc471ac35c4e22dca1))

## [0.13.2](https://github.com/djkix/magazine-search/compare/v0.13.1...v0.13.2) (2026-08-31)


### Bug Fixes

* filter repeating boilerplate lines, handle mixed sommaire sub-styles ([971f6fd](https://github.com/djkix/magazine-search/commit/971f6fd17098d148def9c8e9bb2959b4d60c1712))
* report sommaire re-extraction count from the backfill action ([840baae](https://github.com/djkix/magazine-search/commit/840baaeb7067e39ef01b16d081cc714c16ce4617))

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
