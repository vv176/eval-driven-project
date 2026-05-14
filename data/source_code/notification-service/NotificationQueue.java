package com.clouddesk.notification.queue;

import com.clouddesk.notification.dto.NotificationRequest;
import com.clouddesk.notification.service.NotificationService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class NotificationQueue {

    private static final String QUEUE_KEY = "notifications:pending";
    private static final String DEAD_LETTER_KEY = "notifications:dead_letter";
    private static final String RETRY_COUNT_PREFIX = "notifications:retry:";
    private static final int BATCH_SIZE = 50;
    private static final int MAX_RETRIES = 3;
    private static final long BASE_BACKOFF_MS = 1000L;

    private final RedisTemplate<String, String> redisTemplate;
    private final NotificationService notificationService;
    private final ObjectMapper objectMapper;

    @Scheduled(fixedDelay = 2000)
    public void pollAndProcess() {
        final List<String> batch = fetchBatch();
        if (batch.isEmpty()) {
            return;
        }

        log.info("Processing batch of {} notifications from queue", batch.size());
        for (final String message : batch) {
            processMessage(message);
        }
    }

    private List<String> fetchBatch() {
        final List<String> batch = new ArrayList<>();
        for (int i = 0; i < BATCH_SIZE; i++) {
            final String message = redisTemplate.opsForList().leftPop(QUEUE_KEY);
            if (message == null) {
                break;
            }
            batch.add(message);
        }
        return batch;
    }

    private void processMessage(final String message) {
        try {
            final NotificationRequest request = objectMapper.readValue(message, NotificationRequest.class);
            notificationService.sendNotification(request);
            clearRetryCount(request.getId());
        } catch (Exception e) {
            log.error("Failed to process notification message: {}", e.getMessage());
            handleFailure(message);
        }
    }

    private void handleFailure(final String message) {
        try {
            final NotificationRequest request = objectMapper.readValue(message, NotificationRequest.class);
            final String retryKey = RETRY_COUNT_PREFIX + request.getId();
            final Long retryCount = redisTemplate.opsForValue().increment(retryKey);
            redisTemplate.expire(retryKey, Duration.ofHours(1));

            if (retryCount != null && retryCount <= MAX_RETRIES) {
                final long backoffMs = BASE_BACKOFF_MS * (long) Math.pow(2, retryCount - 1);
                log.warn("Scheduling retry {} for notification id={} in {}ms",
                        retryCount, request.getId(), backoffMs);
                redisTemplate.opsForList().rightPush(QUEUE_KEY, message);
            } else {
                log.error("Max retries exceeded for notification id={}, moving to dead letter queue",
                        request.getId());
                redisTemplate.opsForList().rightPush(DEAD_LETTER_KEY, message);
            }
        } catch (Exception e) {
            log.error("Failed to handle notification failure, dropping message: {}", e.getMessage());
        }
    }

    private void clearRetryCount(final String notificationId) {
        redisTemplate.delete(RETRY_COUNT_PREFIX + notificationId);
    }
}
