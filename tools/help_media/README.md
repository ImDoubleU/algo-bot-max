# Help Media Builder

Build-time tooling only. The miniapp needs no Python, Playwright or ffmpeg at runtime.
The output is ordinary H.264 MP4, 960x720 PNG and UTF-8 WebVTT.

## Windows Commands

Run from `D:/algo_bot_max`, with the **local demo server** already on `127.0.0.1:8766`:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.venv-support/Scripts/python.exe -m pip install -r tools/help_media/requirements.txt
.venv-support/Scripts/python.exe tools/help_media/build.py --check
.venv-support/Scripts/python.exe tools/help_media/build.py
.venv-support/Scripts/python.exe tools/help_media/verify.py --decode
.venv-support/Scripts/python.exe -m ruff check tools/help_media
```

The installed Edge browser is used in headless mode. Node is used only to evaluate
FAQ declarations in a new, empty VM context. Set `HELP_MEDIA_NODE` to override the
default Codex-provided Node executable path.

An independently owned staff batch can be built with `--staff-only`. For a quick
visual review, use `--only 'Как загрузить учеников из Excel?' --staff-only`.
Partial builds **never** publish the catalog. `--fresh` ignores source-shot cache.

## Sources and Contract

- `extract_faq.cjs`: reads current FAQ metadata, without calling application code.
- `scenarios.py`: explicit staff shot lists and reviewed DOM selector aliases.
- `scenario_family.py`: independently maintained family-safe shot lists.
- `review_family.py`, `review_staff.py`: explicit, topic-specific video scripts
  reviewed independently from the longer FAQ text; `review.py` requires full coverage.
- `screens.py`: actual miniapp DOM rendered with demo or browser-memory fixtures.
- `external.py`, `templates/external.html`: marked reconstructions of external
  mail, MAX, spreadsheet and device screens, with no working invitations.
- `assets/parent-invitation.png`: the supplied real email screenshot used for
  parent registration (overview, then a close-up of the actual invitation link).
  The personal QR, recipient name and pupil records are covered before import;
  the unredacted source is never shipped. This email is not a reconstruction.
- `capture.py`: local-only request guard, exact visible-target checks and crops.
- `templates/scene.html`: red rectangles/arrows, pointer motion and click marks.
- `build.py`: chapter timing, captions, posters, MP4 encoding and catalog output.
- `verify.py`: current FAQ coverage, roles, captions, media structure and decoding.

Generated `app-help-media-catalog.js` declares `HELP_MEDIA_CATALOG` keyed by the
**exact current FAQ question**. Each record has `id`, `title`, `duration` in
seconds, and `steps: [[seconds, title, text], ...]`. The matching files are
`assets/help/guides/<id>.mp4`, `.png` and `.vtt`. `HELP_TOP_GUIDES` supplies native
picker metadata and explicit audiences; every top guide includes `staff`.

Coverage is driven by `item.video === true`, not by a historical FAQ count. The
builder rejects missing reviews, missing/hidden/oversized targets and staff screens
inside a family-visible recording. Video chapters are intentionally shorter than
FAQ answers: no automatic outcome repetition or common support tutorial is added.
Each troubleshooting plan contains only its own checks and relevant next action.
Click animation requires an explicitly reviewed click and an actual clickable DOM
target. Observation frames are highlighted without a fictitious click.

## Safety and Limitations

Only the unsigned `demo=1` local routes are opened. All backend endpoints,
non-GET requests and external hosts are blocked. Browser contexts are disposable.
Nothing is sent to MAX, email, the signed database, production or a VPS.

Forms unavailable in demo (including import preview, invitation results, owner
tickets, notification preferences and some confirmations) use **the real app
markup with isolated in-memory fixtures**, marked as reconstructions. External
apps are illustrative reconstructions, not pixel-exact recordings of a specific
MAX/mail/Excel version. Account-check panels are explanatory, not a role-picker
screen in MAX. Mail invitations use the underlined word `ссылке`; all displayed
addresses in reconstructed screens use `example.invalid`. The supplied email
retains public school contacts as image pixels, with personal data and its QR
covered. Other QR images are deliberate non-working examples.

The final focused step explains what a user must verify. Reconstructed confirmations are
not evidence that a backend write, delivery or real support submission occurred.
The dedicated support guide covers sending and the example confirmation number;
other clips do not repeat that entire flow. Clips are silent; captions and chapter text carry
the instructions. Runtime controls, role filtering and autoplay policy are owned
by the miniapp, not this builder.

Ignored `.cache/` contains disposable source shots, frame sequences, DOM inventory
and request audit. No auth credentials or signed sessions are used or stored.
`editorial-review.json` in that cache records every reviewed question, rationale,
old/new duration, caption and target for inspection before publishing.
