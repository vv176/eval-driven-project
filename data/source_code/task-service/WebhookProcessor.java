package com.clouddesk.task.webhook;

import com.clouddesk.task.dto.CreateTaskRequest;
import com.clouddesk.task.dto.TaskResponseDto;
import com.clouddesk.task.dto.UpdateTaskRequest;
import com.clouddesk.task.model.Task;
import com.clouddesk.task.repository.TaskRepositoryCustomImpl;
import com.clouddesk.task.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class WebhookProcessor {

    private static final int BATCH_THREAD_POOL_SIZE = 10;
    private static final String SOURCE_GITHUB = "github";
    private static final String SOURCE_JIRA = "jira";
    private static final String SOURCE_SLACK = "slack";

    private final TaskService taskService;
    private final TaskRepositoryCustomImpl taskRepositoryCustom;
    private final ExecutorService batchExecutor = Executors.newFixedThreadPool(BATCH_THREAD_POOL_SIZE);

    public TaskResponseDto processWebhook(final WebhookPayload payload) {
        log.info("Processing webhook from source={} for project={}", payload.getSource(), payload.getProjectId());

        final Map<String, String> filters = buildFiltersFromPayload(payload);
        final List<Task> matchingTasks = taskRepositoryCustom.findTasksWithCustomFilter(
                payload.getProjectId(), filters);

        if (!matchingTasks.isEmpty()) {
            final Task existingTask = matchingTasks.get(0);
            log.info("Found existing task id={} matching webhook criteria, updating",
                    existingTask.getId());
            final UpdateTaskRequest updateRequest = mapToUpdateRequest(payload);
            return taskService.updateTask(existingTask.getId(), updateRequest);
        }

        log.info("No matching task found, creating new task from webhook");
        final CreateTaskRequest createRequest = mapToCreateRequest(payload);
        return taskService.createTask(createRequest);
    }

    public List<TaskResponseDto> processBatch(final List<WebhookPayload> payloads) {
        log.info("Processing batch of {} webhooks", payloads.size());
        final List<CompletableFuture<TaskResponseDto>> futures = payloads.stream()
                .map(payload -> CompletableFuture.supplyAsync(
                        () -> processWebhook(payload), batchExecutor))
                .collect(Collectors.toList());

        return futures.stream()
                .map(CompletableFuture::join)
                .collect(Collectors.toList());
    }

    private Map<String, String> buildFiltersFromPayload(final WebhookPayload payload) {
        final Map<String, String> filters = new HashMap<>();
        if (payload.getStatus() != null) {
            filters.put("status", payload.getStatus());
        }
        if (payload.getPriority() != null) {
            filters.put("priority", payload.getPriority());
        }
        if (payload.getAssigneeId() != null) {
            filters.put("assignee_id", payload.getAssigneeId());
        }
        if (payload.getLabel() != null) {
            filters.put("label", payload.getLabel());
        }
        return filters;
    }

    private CreateTaskRequest mapToCreateRequest(final WebhookPayload payload) {
        return CreateTaskRequest.builder()
                .title(payload.getTitle())
                .description(payload.getDescription())
                .projectId(payload.getProjectId())
                .assigneeId(payload.getAssigneeId())
                .priority(payload.getPriority() != null ? payload.getPriority() : "MEDIUM")
                .build();
    }

    private UpdateTaskRequest mapToUpdateRequest(final WebhookPayload payload) {
        return UpdateTaskRequest.builder()
                .title(payload.getTitle())
                .description(payload.getDescription())
                .status(payload.getStatus())
                .priority(payload.getPriority())
                .assigneeId(payload.getAssigneeId())
                .build();
    }
}
