# 13 — Related-posts scoring: drop the O(n²) and the payload bloat

**Size:** S · **Backlog #4** · **Breaking:** none visible

## Context

`_set_navigation_links` scores every post against every other post
(O(n²) tag intersections) and stores **full post dicts** (content, raw
markdown, metadata) in `post['related_posts']` — which also balloons
`all_blog_posts` when serialized or handed to scripts. Irrelevant at 5
posts; hostile at 500.

## Design

1. Build an inverted index once: `tag -> [post indices]`. Candidate set for
   each post = union of its tags' lists (typically tiny). Score candidates
   only; keep the adjacency-bonus fallback for tagless posts by seeding
   candidates with the `k` nearest neighbors by date.
2. Store lightweight refs:
   `{'title', 'full_url', 'date_formatted', 'excerpt'}` — audit bundled
   templates for the fields actually referenced (blog templates use title +
   url today) and include exactly those plus excerpt.
3. Count comes from `blog.related_posts` (plan 12); `0` skips the whole
   computation.

## Files

`sonne/processors/blog_processor.py` (`_set_navigation_links`),
`CHANGELOG.md` (internal note; "related_posts entries are now summaries" —
technically observable from templates that reached into `.content`, so list
the available fields).

## Tests

- related posts prefer shared-tag posts over adjacent ones (fixture with
  distinct tag clusters);
- tagless post still gets neighbors;
- entries expose exactly the documented fields (guards against templates
  depending on full dicts silently);
- micro-benchmark style sanity: 200 generated posts finish the nav pass
  well under a second (loose bound, no flakes).
