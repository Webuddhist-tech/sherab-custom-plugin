# sherab-custom-plugin

Custom Open edX plugins for the **Sherab / WeBuddhist Academy** platform, packaged
together as a single installable distribution (`custom-extensions`). The package
bundles four independent Django apps that plug into the LMS and/or CMS via the
[Open edX plugin framework](https://edx.readthedocs.io/projects/edx-django-utils/en/latest/edx_django_utils.plugins.html)
(`edx_django_utils.plugins`) — no edx-platform core code is modified.

| App | Runs in | Purpose |
| --- | --- | --- |
| [`ai_course_creator`](#ai_course_creator) | CMS (Studio) | Conversational AI ("Sherab") that designs and generates whole courses, and edits existing sections, using Google Gemini. |
| [`course_partnerships`](#course_partnerships) | LMS | Partner organizations, centers, categories, and course-creator profiles, with branding assets and a mobile API. |
| [`user_extension`](#user_extension) | LMS | Extends user profiles with partner relationships; auto-approves ID verification on registration. |
| [`wishlist`](#wishlist) | LMS | Personal per-user course wishlist. |

---

## Installation

The plugin is installed into the edx-platform virtualenv. Under Tutor it is mounted
and listed as an extra pip requirement so it is picked up on image build / dev mount.

`config.yml`:

```yaml
OPENEDX_EXTRA_PIP_REQUIREMENTS:
  - google-api-python-client
  - google-genai
MOUNTS:
  - /path/to/sherab-custom-plugin   # dev: live-mounted into LMS & CMS
```

Python dependencies are listed in [`requirements/common.in`](requirements/common.in)
and installed automatically by `setup.py`.

The apps register through the entry points in [`setup.py`](setup.py):

```
cms.djangoapp:  ai_course_creator, course_partnerships, user_extension
lms.djangoapp:  course_partnerships, user_extension, wishlist
```

After installing or changing models, run migrations for the relevant process, e.g.:

```bash
tutor dev exec cms ./manage.py cms migrate ai_course_creator
tutor dev exec lms ./manage.py lms migrate course_partnerships
```

---

## `ai_course_creator`

A **Studio-only (CMS)** conversational assistant — "Sherab" — that helps a course
creator design a course through chat, then generates the real Open edX course
structure for them. It also powers a per-section "Edit with SherabAI" sidebar for
improving an existing section. All LLM calls are **server-side only**; the Gemini
API key is never sent to the browser.

### Two flows

**1. Whole-course creator.** From an empty course outline the creator chats with
Sherab through a guided, four-phase flow (Learner → Transformation → Materials &
Assessment → Generate). When the conversation is ready, Sherab generates the full
outline and writes it into the course as **draft** sections, subsections, units,
and components.

**2. Per-section editor.** From a populated outline the creator opens a section in
the "Edit with SherabAI" sidebar. The conversation is anchored on that section's
**zero-to-hero transformation** (what a learner can do after the section that they
couldn't before). Sherab proposes concrete edits; nothing is written until the
creator clicks **Apply changes**, and edits are strictly scoped to that one section.

### Components

- **`models.py`**
  - `ChatSession` — one conversation, unique per `(user, course_id, section_locator)`.
    `section_locator` is empty for the creator flow and the chapter usage key for the
    per-section editor, so each section keeps its own thread. Caches the generated
    `course_json`, the display `current_phase`, the `generation_status` lifecycle, and
    the `created_section_locators` (for rollback / detecting existing Sherab content).
  - `ChatMessage` — a user/assistant turn within a session.
  - `UploadedMaterial` — course material shared by the creator (file/link/text),
    stored as extracted plain text (the binary is not retained).

- **`services/llm_client.py`** — thin wrapper over the `google-genai` SDK. Streams
  replies (`stream_reply`), makes JSON-mode generation calls (`complete_json`), loads
  the bundled skill as the system instruction, and parses/strips the embedded
  `COURSE_JSON` and `SECTION_EDITS` marker blocks. Handles rate-limit (429), 503
  "high demand", and oversized-request (413) errors with backoff/retry and
  user-friendly messages.

- **`services/generator.py`** — orchestrates two-stage, resumable course generation:
  a small **skeleton** call (titles + objectives + component plan), then one
  **content** call per section (lesson HTML + assessments). Yields progress events
  consumed by `GenerateCourseView`.

- **`services/course_builder.py`** — turns the generated `COURSE_JSON` into real
  Open edX structure by calling `contentstore`/modulestore directly (chapter →
  sequential → vertical → component). Builds CAPA problem OLX for several question
  types. Also exposes `user_can_author` (the author-permission check) and
  `delete_sections` (rollback).

- **`services/section_editor.py`** — `read_section` serializes one chapter subtree to
  a JSON tree (usage keys + content) for the LLM; `apply_section_edits` applies an
  operation list (`rename` / `editContent` / `add` / `delete` / `reorder`) strictly
  scoped to that chapter. Every usage key the model supplies is validated against the
  chapter's own descendant set before anything is mutated.

- **`services/materials.py`** — extracts plain text from PDF / DOCX / PPTX / plain
  text uploads, pasted text, and public URLs; truncates to the per-request context
  budget.

- **`skill/`** and **`skill_section_editor/`** — the `SKILL.md` prompt files (plus
  `skill/references/*.md`) that define Sherab's persona and conversation rules for the
  creator flow and the section editor respectively. Loaded as the model's system
  instruction.

- **`helpers.py`** — view helpers: SSE framing (`sse`), session lookup
  (`get_or_create_session`), edit-and-resend truncation (`truncate_for_edit`), the
  shared course-key + author-permission guard (`require_course_author`), and feature/
  limit settings accessors.

### API endpoints

All require an authenticated user; course-mutating endpoints additionally check
author access. Mounted at the site root, so paths are absolute on the Studio host.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/ai-course-creator/chat/` | Stream the assistant's next reply (SSE). |
| POST | `/api/ai-course-creator/upload/` | Add a material (file / link / text). |
| DELETE | `/api/ai-course-creator/material/<pk>/` | Delete an uploaded material. |
| POST | `/api/ai-course-creator/generate/` | Generate + write the course (SSE). |
| GET | `/api/ai-course-creator/config/` | Feature-flag state for the Studio UI. |
| GET / DELETE | `/api/ai-course-creator/session/` | Fetch (resume) or reset a conversation. |
| GET | `/api/ai-course-creator/section-content/` | Read one section's content tree. |
| POST | `/api/ai-course-creator/section-chat/` | Stream a per-section editor reply (SSE). |
| POST | `/api/ai-course-creator/apply-section/` | Apply the latest proposed section edits. |

### Settings

Defaults are set in `settings/common.py` / `settings/production.py`; the Gemini
credentials are normally injected into CMS settings from Tutor `config.yml` via the
`configuration_plugin` patch.

| Setting | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | `""` | Google Gemini API key (server-side only). |
| `GEMINI_MODEL` | `gemini-1.5-pro` | Model id (e.g. `gemini-2.5-flash-lite`). |
| `AI_COURSE_CREATOR_ENABLED` | `True` | Master on/off switch for the feature. |
| `AI_COURSE_CREATOR_MAX_UPLOAD_BYTES` | `25 MB` | Max uploaded-material size. |
| `AI_COURSE_CREATOR_MAX_CONTEXT_CHARS` | `16000` | Max material text per request. |

Tutor wiring — set the values in `config.yml`:

```yaml
GEMINI_API_KEY: "AQ.xxxxxxxx"
GEMINI_MODEL: gemini-2.5-flash-lite
```

and inject them into CMS settings in `configuration_plugins.yml`:

```yaml
patches:
  openedx-cms-production-settings: |
    GEMINI_API_KEY = "{{ GEMINI_API_KEY }}"
    GEMINI_MODEL = "{{ GEMINI_MODEL }}"
```

then `tutor config save` and restart CMS.

> **Note:** the bundled skill is read once and cached (`lru_cache`) for the process
> lifetime, so restart the CMS after editing any `SKILL.md` to pick up changes.

The matching frontend lives in the **`frontend-app-authoring`** MFE under
`src/ai-course-creator/` (the creator modal and the section-editor sidebar).

---

## `course_partnerships`

**LMS-only.** Manages partner organizations, their sub-centers, course categories,
and instructor/course-creator profiles — with branding assets — and links them to
courses. Provides partner/center detail pages and a mobile-app JSON API.

### Models

- `Partner` — schools / partner organizations (logo, banner, rich-text description;
  can activate school-admin features).
- `Center` — sub-entities under a `Partner` (logo, banner, description).
- `Category` — course categories, optionally tied to a partner; can be shown on the homepage.
- `EnhancedCourse` — links a `CourseOverview` to its `Partner` / `Center` / `Category`.
- `PartnerOrganizationMapping` — maps a `Partner` to an `Organization`, with a mobile-app
  visibility toggle and optional display-name override.
- `CourseCreator` — instructor profiles (name, title, years of experience, bio, picture).
- `HeroCourse` — courses curated for the homepage hero cards (see `/api/courses/hero/`
  below). `order`: display position. `is_active`: whether it's used as a curated pick.
  `new_until`: shows a "New course" badge until this date, independent of `is_active`.

### API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/schools/<slug>/` | Partner detail page (centers, categories, courses, creators). |
| GET | `/schools/<partner_slug>/<center_slug>/` | Center detail page. |
| GET | `/api/partners/` | Mobile-app JSON of partner-organization mappings. |
| GET | `/api/partners/homepage/` | All partners, for the homepage schools-and-partners carousel. |
| GET | `/api/categories/homepage/` | Homepage course categories, each with its visible courses. |
| GET | `/api/courses/hero/` | Courses for the homepage hero cards. Personalized: a signed-in caller gets their most recent enrollments, newest first, with curated `HeroCourse` picks filling any leftover slot; a signed-out caller gets the curated picks alone. Each card also reports `is_new` (true while the course's `HeroCourse.new_until` date has not passed) and `is_enrolled` (true for a card sourced from the caller's own enrollments, false for a curated pick they have not joined). |

### Management commands

| Command | Purpose |
| --- | --- |
| `assign_course_partners` | Auto-assign partners to courses lacking one, from org→partner mappings. |
| `check_partner_logos` | Show current storage locations / URLs for logos and creator profiles. |
| `check_storage_settings` | Validate the S3 storage backend config for partner/center/creator assets. |
| `fix_logo_paths` | Correct malformed logo/banner paths in the DB (`--dry-run` supported). |

### Behaviour & settings

- **Signals:** on course publish, creates/updates the `EnhancedCourse` row and
  auto-assigns a partner from the org mapping; on course delete, removes it.
- `settings/common.py` adds `ckeditor` to `INSTALLED_APPS` for the rich-text fields.
- Asset storage backends are read from Django config (`PARTNER_LOGO_BACKEND`,
  `CENTER_LOGO_BACKEND`, `COURSE_CREATOR_STORAGE_BACKEND`), wired via the
  `tutor-contrib-s3` plugin.

---

## `user_extension`

**LMS-only.** Extends user profiles with partner-organization relationships and
streamlines onboarding.

- **Model:** `ExtendedUserProfile` — OneToOne with `User`; associates users with a
  `Partner` and stores admin relationships with timestamps.
- **Signals:**
  - `sync_extended_profile` — create an `ExtendedUserProfile` whenever a `User` is created.
  - `auto_approve_id_verification_on_registration` — create an approved
    `ManualVerification` for every new user, bypassing the standard ID-verification flow.
- **Management command:** `approve_id_verification` — bulk-approve ID verification
  (`--username`, `--all`, `--batch-size`, `--dry-run`).
- No REST endpoints; no settings injected.

---

## `wishlist`

**LMS-only.** A personal per-user course wishlist.

- **Model:** `Wishlist` — one entry per `(user, course)` pair.
- **API endpoints:**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/wishlist/change-status/` | Add/remove a course (`wishlist_action` = `add` / `remove`). |
| GET | `/wishlist/` | List the authenticated user's wishlisted courses. |

- No settings injected; no active signals.

---

## Development

- **Formatting:** Black, line length 120 (see [`pyproject.toml`](pyproject.toml)).
- **Making migrations** (from the edx-platform dir / inside the container):

  ```bash
  ./manage.py cms makemigrations ai_course_creator
  ./manage.py cms migrate ai_course_creator
  ```

- **Dev mount:** with the plugin in `MOUNTS`, code changes are live; the CMS still
  needs a restart to reload a changed `SKILL.md` (it is cached per process).

  ```bash
  tutor dev restart cms
  ```

## License

Proprietary.
