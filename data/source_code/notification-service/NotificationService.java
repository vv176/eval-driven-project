package com.clouddesk.notification.service;

import com.clouddesk.notification.dto.NotificationRequest;
import com.clouddesk.notification.dto.TaskDetailsDto;
import com.clouddesk.notification.dto.ProjectDetailsDto;
import com.clouddesk.notification.email.EmailClient;
import com.clouddesk.notification.model.Notification;
import com.clouddesk.notification.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.ResourceAccessException;

import java.time.Instant;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private static final String TASK_SERVICE_URL = "http://task-service:8080/api/v1/tasks";
    private static final String PROJECT_SERVICE_URL = "http://project-service:8081/api/v1/projects";
    private static final int UPSTREAM_TIMEOUT_SECONDS = 5;

    private final NotificationRepository notificationRepository;
    private final EmailClient emailClient;
    private final RestTemplate restTemplate;

    public void sendNotification(final NotificationRequest request) {
        log.info("Processing notification type={} for user={}", request.getType(), request.getRecipientId());

        final TaskDetailsDto taskDetails = fetchTaskDetails(request.getTaskId());
        final ProjectDetailsDto projectDetails = fetchProjectDetails(request.getProjectId());

        final String subject = buildSubject(request.getType(), taskDetails, projectDetails);
        final String body = buildBody(request.getType(), taskDetails, projectDetails);

        final Notification notification = Notification.builder()
                .id(UUID.randomUUID().toString())
                .recipientId(request.getRecipientId())
                .channel(request.getChannel())
                .subject(subject)
                .body(body)
                .status("PENDING")
                .createdAt(Instant.now())
                .build();

        notificationRepository.save(notification);

        switch (request.getChannel()) {
            case "email" -> {
                emailClient.send(request.getRecipientEmail(), subject, body, request.getType());
                notification.setStatus("SENT");
            }
            case "in_app" -> {
                notification.setStatus("DELIVERED");
            }
            case "webhook" -> {
                log.info("Webhook notification queued for delivery");
                notification.setStatus("QUEUED");
            }
            default -> log.warn("Unknown notification channel: {}", request.getChannel());
        }

        notification.setSentAt(Instant.now());
        notificationRepository.save(notification);
        log.info("Notification id={} processed with status={}", notification.getId(), notification.getStatus());
    }

    private TaskDetailsDto fetchTaskDetails(final String taskId) {
        try {
            return restTemplate.getForObject(TASK_SERVICE_URL + "/" + taskId, TaskDetailsDto.class);
        } catch (ResourceAccessException e) {
            log.error("Failed to fetch task details for taskId={}: {}", taskId, e.getMessage());
            throw new RuntimeException("Task service unavailable", e);
        }
    }

    private ProjectDetailsDto fetchProjectDetails(final String projectId) {
        try {
            return restTemplate.getForObject(PROJECT_SERVICE_URL + "/" + projectId, ProjectDetailsDto.class);
        } catch (ResourceAccessException e) {
            log.error("Failed to fetch project details for projectId={}: {}", projectId, e.getMessage());
            throw new RuntimeException("Project service unavailable", e);
        }
    }

    private String buildSubject(final String type, final TaskDetailsDto task, final ProjectDetailsDto project) {
        return String.format("[%s] %s: %s", project.getName(), type, task.getTitle());
    }

    private String buildBody(final String type, final TaskDetailsDto task, final ProjectDetailsDto project) {
        return String.format("Task \"%s\" in project \"%s\" has been %s.\n\nStatus: %s\nPriority: %s\nAssignee: %s",
                task.getTitle(), project.getName(), type.toLowerCase(),
                task.getStatus(), task.getPriority(), task.getAssigneeName());
    }
}
