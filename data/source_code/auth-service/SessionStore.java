package com.clouddesk.auth.service;

import java.time.Duration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Service
public class SessionStore {

    private static final Logger log = LoggerFactory.getLogger(SessionStore.class);

    private static final String SESSION_KEY_PREFIX = "session:";
    private static final Duration SESSION_TTL = Duration.ofDays(7);
    private static final Duration EXTENDED_TTL = Duration.ofDays(30);

    private final StringRedisTemplate redisTemplate;

    public SessionStore(final StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public void createSession(final String userId, final String sessionId) {
        final String key = buildKey(userId, sessionId);
        redisTemplate.opsForValue().set(key, "active", SESSION_TTL);
        log.info("Created session: userId={}, sessionId={}, ttl={}", userId, sessionId, SESSION_TTL);
    }

    public boolean isSessionValid(final String userId, final String sessionId) {
        final String key = buildKey(userId, sessionId);
        final String value = redisTemplate.opsForValue().get(key);
        final boolean isValid = "active".equals(value);
        log.debug("Session check: userId={}, sessionId={}, valid={}", userId, sessionId, isValid);
        return isValid;
    }

    public void invalidateSession(final String userId, final String sessionId) {
        final String key = buildKey(userId, sessionId);
        redisTemplate.delete(key);
        log.info("Invalidated session: userId={}, sessionId={}", userId, sessionId);
    }

    public void invalidateAllSessions(final String userId) {
        final String pattern = SESSION_KEY_PREFIX + userId + ":*";
        final var keys = redisTemplate.keys(pattern);
        if (keys != null && !keys.isEmpty()) {
            redisTemplate.delete(keys);
            log.info("Invalidated all {} sessions for userId={}", keys.size(), userId);
        }
    }

    public void extendSession(final String userId, final String sessionId) {
        final String key = buildKey(userId, sessionId);
        final Boolean result = redisTemplate.expire(key, EXTENDED_TTL);
        if (Boolean.TRUE.equals(result)) {
            log.info("Extended session TTL: userId={}, sessionId={}, newTtl={}", userId, sessionId, EXTENDED_TTL);
        } else {
            log.warn("Failed to extend session (not found): userId={}, sessionId={}", userId, sessionId);
        }
    }

    public long getActiveSessionCount(final String userId) {
        final String pattern = SESSION_KEY_PREFIX + userId + ":*";
        final var keys = redisTemplate.keys(pattern);
        return keys != null ? keys.size() : 0;
    }

    private String buildKey(final String userId, final String sessionId) {
        return SESSION_KEY_PREFIX + userId + ":" + sessionId;
    }
}
