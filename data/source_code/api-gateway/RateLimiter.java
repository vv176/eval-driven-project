package com.clouddesk.gateway;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class RateLimiter {

    private static final Logger log = LoggerFactory.getLogger(RateLimiter.class);

    private static final long REFILL_INTERVAL_MS = 1000L;
    private static final Map<String, Integer> TIER_LIMITS = Map.of(
            "platinum", 1000,
            "gold", 500,
            "silver", 200,
            "bronze", 50
    );
    private static final int DEFAULT_LIMIT = 50;

    private final ConcurrentHashMap<String, TokenBucket> buckets = new ConcurrentHashMap<>();

    public boolean isAllowed(final String customerId, final String accountTier) {
        if (customerId == null || customerId.isBlank()) {
            log.warn("Request missing customer ID, rejecting");
            return false;
        }

        final int maxTokens = TIER_LIMITS.getOrDefault(
                accountTier != null ? accountTier.toLowerCase() : "bronze",
                DEFAULT_LIMIT
        );

        final TokenBucket bucket = buckets.computeIfAbsent(
                customerId,
                id -> new TokenBucket(maxTokens, maxTokens, System.currentTimeMillis())
        );

        return bucket.tryConsume(maxTokens);
    }

    public void resetBucket(final String customerId) {
        buckets.remove(customerId);
        log.info("Reset rate limit bucket for customer={}", customerId);
    }

    public int getRemainingTokens(final String customerId) {
        final TokenBucket bucket = buckets.get(customerId);
        return bucket != null ? bucket.getAvailableTokens() : -1;
    }

    private static class TokenBucket {
        private int availableTokens;
        private final int maxTokens;
        private long lastRefillTimestamp;

        TokenBucket(final int availableTokens, final int maxTokens, final long lastRefillTimestamp) {
            this.availableTokens = availableTokens;
            this.maxTokens = maxTokens;
            this.lastRefillTimestamp = lastRefillTimestamp;
        }

        synchronized boolean tryConsume(final int maxCapacity) {
            refill(maxCapacity);
            if (availableTokens > 0) {
                availableTokens--;
                return true;
            }
            return false;
        }

        synchronized int getAvailableTokens() {
            return availableTokens;
        }

        private void refill(final int maxCapacity) {
            final long now = System.currentTimeMillis();
            final long elapsed = now - lastRefillTimestamp;
            if (elapsed >= REFILL_INTERVAL_MS) {
                final long periods = elapsed / REFILL_INTERVAL_MS;
                availableTokens = Math.min(maxCapacity, availableTokens + (int) (periods * maxCapacity));
                lastRefillTimestamp = now;
            }
        }
    }
}
