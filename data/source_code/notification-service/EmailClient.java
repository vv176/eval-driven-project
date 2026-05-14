package com.clouddesk.notification.email;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Slf4j
@Component
public class EmailClient {

    private static final int RATE_LIMIT_PER_MINUTE = 100;
    private static final long RATE_WINDOW_MS = 60_000L;

    private final RestTemplate restTemplate;
    private final String sendGridApiKey;
    private final String sendGridUrl;
    private final String fromAddress;
    private final Map<String, String> templateMapping;
    private final AtomicInteger requestCount = new AtomicInteger(0);
    private volatile long windowStart = Instant.now().toEpochMilli();

    public EmailClient(final RestTemplate restTemplate,
                       @Value("${clouddesk.email.sendgrid.api-key}") final String sendGridApiKey,
                       @Value("${clouddesk.email.sendgrid.url}") final String sendGridUrl,
                       @Value("${clouddesk.email.from}") final String fromAddress) {
        this.restTemplate = restTemplate;
        this.sendGridApiKey = sendGridApiKey;
        this.sendGridUrl = sendGridUrl;
        this.fromAddress = fromAddress;
        this.templateMapping = new ConcurrentHashMap<>();
        this.templateMapping.put("TASK_CREATED", "d-abc123-task-created");
        this.templateMapping.put("TASK_UPDATED", "d-abc124-task-updated");
        this.templateMapping.put("TASK_ASSIGNED", "d-abc125-task-assigned");
        this.templateMapping.put("TASK_COMPLETED", "d-abc126-task-completed");
        this.templateMapping.put("COMMENT_ADDED", "d-abc127-comment-added");
    }

    public void send(final String toAddress, final String subject,
                     final String body, final String notificationType) {
        checkRateLimit();

        final String templateId = templateMapping.getOrDefault(notificationType, null);
        final HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(sendGridApiKey);

        final Map<String, Object> payload = buildPayload(toAddress, subject, body, templateId);
        final HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

        try {
            restTemplate.postForEntity(sendGridUrl + "/v3/mail/send", request, Void.class);
            log.info("Email sent to={} subject={}", toAddress, subject);
        } catch (Exception e) {
            log.error("Failed to send email to={}: {}", toAddress, e.getMessage());
            throw new RuntimeException("Email delivery failed", e);
        }
    }

    private Map<String, Object> buildPayload(final String toAddress, final String subject,
                                              final String body, final String templateId) {
        if (templateId != null) {
            return Map.of(
                    "personalizations", java.util.List.of(Map.of("to", java.util.List.of(Map.of("email", toAddress)))),
                    "from", Map.of("email", fromAddress),
                    "subject", subject,
                    "template_id", templateId,
                    "content", java.util.List.of(Map.of("type", "text/plain", "value", body))
            );
        }
        return Map.of(
                "personalizations", java.util.List.of(Map.of("to", java.util.List.of(Map.of("email", toAddress)))),
                "from", Map.of("email", fromAddress),
                "subject", subject,
                "content", java.util.List.of(Map.of("type", "text/plain", "value", body))
        );
    }

    private void checkRateLimit() {
        final long now = Instant.now().toEpochMilli();
        if (now - windowStart > RATE_WINDOW_MS) {
            windowStart = now;
            requestCount.set(0);
        }
        if (requestCount.incrementAndGet() > RATE_LIMIT_PER_MINUTE) {
            log.warn("Email rate limit exceeded, throttling");
            throw new RuntimeException("Email rate limit exceeded, try again later");
        }
    }
}
