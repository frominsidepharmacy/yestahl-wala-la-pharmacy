# Production workflow contract

This is the source of truth for both Instagram content systems. It records stable production behavior and contains no credentials. Tokens stay in encrypted GitHub secrets and connection credentials stay in Activepieces.

## Accounts and schedules

| Series | Instagram | Preview schedule (Asia/Dubai) | Design skill |
|---|---|---|---|
| من جوة الصيدلية | `@dramrouaboubakr` | 12:00 Skin Care, 17:00 Vitamins, 22:00 Personal Care | `artifact-template-reference-design-2` |
| من جوة البيزنس | `@dramrou.business` | 13:00 and 21:00 | `artifact-template-reference-design` |

The streams use separate Meta tokens, Instagram user IDs, preview artifacts, publication-key namespaces, and publishing branches. Business keys begin with `biz-`. A change to one stream must not alter the other stream's schedule, credentials, assets, or approval state.

Current non-secret identities are `INSTAGRAM_USER_ID=28801746372751606` and `BUSINESS_INSTAGRAM_USER_ID=29437654965823129`. Validate the token-returned username and ID before publishing. If Meta legitimately changes an ID after reconnection, update the matching GitHub variable; never bypass validation.

## Content and design contract

Every carousel is six separate 1080×1350 PNG slides with safe margins, strong RTL hierarchy, readable Arabic, consistent numbering, exact approved copy, and a `qc_report.json` with overall status `PASS`.

Pharmacy requirements:

- Match the retained torn-paper editorial reference, not a generic template.
- Show `من جوة الصيدلية | د. عمرو أبوبكر` on every slide.
- Never write a retailer or pharmacy name on artwork or in the caption.
- Skin Care: teal/mint. Personal Care: plum/coral. Vitamins: royal blue/sunshine. Product colors are supporting accents only.
- Rotate Personal Care across deodorant, baby care, mother care, feminine wash, oral care, hair care, body care, and other distinct subcategories. Avoid the most recently used subcategory when alternatives exist.
- Confirm and display the verified original pre-offer price on the slides, not the temporary sale price. If a page shows a promotion but the original price cannot be verified, do not state a price as original and do not approve the carousel.
- When an offer exists, compare the same exact pack across the configured retailers. Put the best verified offer price and retailer name in the caption only, together with the original price. Never put the retailer name on the artwork.
- Name the primary active ingredient and explain its practical role in clear Arabic. Research beyond the retailer page and add a competitive advantage only when it is explicitly written in a product source or supported by a clear source.
- Make the written usage directions prominent. Record written side effects/warnings and list other verified pack sizes when the source provides them; do not invent missing sizes or adverse effects.
- Use the selected product's exact pack, warnings, and topic. Do not copy retailer prose or fill space with generic text.
- Avoid weak stock disclaimers such as “يختلف من شخص لآخر”، “كل جسم غير الثاني”، or “كل بشرة مختلفة”. Write with expert confidence and use specific limitations or warnings only when they materially affect the decision.
- Boots, BinSina, Life, Aster, and other configured UAE retailers may establish availability, pack, and price; they are not medical evidence. Trace factual/medical claims to the evidence bundle and flag unsupported wording for the user's decision instead of inventing a claim.

Business requirements:

- Match the retained premium cartoon-office reference: warm cinematic depth, expressive consistent characters, navy/yellow/crimson hierarchy, paint strokes, speech bubbles, and editorial props.
- Show `من جوة البيزنس | د. عمرو أبوبكر` on every slide; never show pharmacy branding.
- Slide 1 contains the actual topic title and hook, not a reusable dictionary of office phrases.
- Copy is specific, useful, creative, and about the carousel topic. Use a comic “هو قال / هو قصده” contrast only when requested or genuinely suited to the topic.
- Do not invent statistics, quotations, attributions, or business claims.

The user is the final creative approver. The automation must not send or publish artwork that failed exact-copy, reference-fidelity, account-branding, dimensions, factual/medical, or visual-integrity checks.

### The “يستاهل ولا لأ؟” decision

Every pharmacy carousel must finish with one unambiguous verdict: `يستاهل`, `يستاهل بشروط واضحة`, or `لا يستاهل`. State the decisive reason in the same block. The verdict is based primarily on documented active-ingredient value, written usage clarity, written safety/side effects, a verified competitive advantage, exact-pack availability, and value against the original price plus the best verified offer. Ratings, reviews, brand fame, and discount percentage can make a topic interesting but cannot by themselves make a product worth buying.

## Preview and approval lifecycle

1. Generate the complete six-slide carousel and a topic/product-specific caption.
2. Run deterministic and visual QC. Correct only failed items and repeat QC; do not send a failed design.
3. Upload an immutable private Actions artifact containing slides, caption, metadata, manifest, content hash, and QC report.
4. Send the Telegram album, caption, and approval controls.
5. Wait for explicit approval from the authorized user. Closing the local computer does not stop cloud-hosted steps.
6. Activepieces parses the callback, verifies the sender, and routes only when `dispatch` exactly matches the text `true`.
7. Immediately answer the callback: `⏳ تم استلام موافقتك وبدأ النشر… سيصلك رابط البوست هنا بعد النجاح.`
8. Dispatch `.github/workflows/publish.yml` on `main` with `publication_key`, `content_hash`, and `artifact_run_id` from the approved callback.
9. GitHub verifies the immutable manifest, stages only those assets, exposes them through GitHub Pages, and calls the official Meta API.
10. Retrieve the Instagram permalink and send it to Telegram as final proof.

`EDIT`, `REGENERATE`, `REJECT`, and `APPROVE ALL` remain separate routes. Any edit or regeneration creates a new version/hash and requires a new approval.

## Publishing invariants

- Keep `REQUIRE_MANUAL_APPROVAL=true`, `ALLOW_PAID_SERVICES=false`, and `FREE_AI_ENABLED=false`.
- Never publish a hash different from the approved manifest.
- Use the single global Actions concurrency group `instagram-publish-pages`. The repository has one shared Pages deployment, so publication must be serial.
- After Pages deployment, poll every media URL until HTTP 200 with an image content type, for up to 120 seconds, before creating Meta containers.
- Poll every Meta child container to `FINISHED`, then create and poll the carousel parent, publish once, and retrieve the permalink.
- Put a unique publication marker in the caption and search recent media for it before any retry. This prevents duplicates after uncertain timeouts.
- A complete successful job sends the permalink to Telegram. A green run without an accessible permalink is not complete.

## Failure recovery

Use the first failed run as evidence; do not repeatedly click or redispatch blindly.

- Approval recorded but Router false: use **Exactly matches (Text)** `true`, not **Is true (Boolean)**.
- No GitHub run: ensure the Activepieces GitHub step targets `publish.yml`, not `telegram_control.yml`, and maps all three inputs.
- Media URL 404: keep global serialization and URL-readiness polling; do not overlap Pages deployments.
- Meta 400: inspect the response body surfaced by `src/instagram.py`, then verify URL reachability and token/account pairing.
- Account mismatch: confirm Meta returned the intended username, update only the corresponding GitHub user-ID variable, then retry the same approved artifact once.
- Uncertain publish result: let the caption-marker lookup determine whether it already published before retrying.

After one corrected retry, stop if the same failure repeats. Preserve the approved artifact and report the exact blocker instead of experimenting against live accounts.

## Acceptance check

End-to-end success requires observable evidence that:

- Telegram received the preview and controls.
- Approval produced the immediate callback acknowledgement.
- Router selected the publish branch.
- The correct `publish.yml` account branch ran.
- Manifest/hash verification passed.
- Meta returned a media ID and permalink.
- Telegram received that permalink.
- The link opens on the intended Instagram account.

Run local regression tests with `.venv/bin/pytest -q`. The baseline after the September 10, 2026 production repair is 61 passing tests.
