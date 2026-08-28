# YouTube API Quota Exhaustion

## Symptoms

All YouTube API calls return 403 quotaExceeded. Publishing pipeline stalled.

## Impact

No new uploads, metadata updates, or analytics fetches possible until quota resets at midnight Pacific.

## Detection

Alert: `quota_remaining < 100 units` or `youtube_api_error_rate` spike with quotaExceeded reason.

## Mitigation

1. Immediately pause non-critical operations (analytics backfill, optional metadata refresh). 2. Enable emergency quota borrowing from secondary project if configured. 3. Alert channel owner to request quota increase from Google.

## Recovery

Wait for Pacific midnight reset. Resume operations gradually with priority queue.

## Post-Incident

Review quota allocation model. Identify the operation that caused exhaustion and optimize batching.
