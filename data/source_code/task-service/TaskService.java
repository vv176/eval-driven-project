package com.clouddesk.task.service;

import com.clouddesk.task.dto.CreateTaskRequest;
import com.clouddesk.task.dto.UpdateTaskRequest;
import com.clouddesk.task.dto.TaskResponseDto;
import com.clouddesk.task.exception.ResourceNotFoundException;
import com.clouddesk.task.exception.BadRequestException;
import com.clouddesk.task.mapper.TaskMapper;
import com.clouddesk.task.model.Task;
import com.clouddesk.task.repository.TaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpClientErrorException;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskService {

    private static final String PROJECT_SERVICE_URL = "http://project-service:8081/api/v1/projects";

    private final TaskRepository taskRepository;
    private final TaskMapper taskMapper;
    private final RestTemplate restTemplate;

    @Transactional
    public TaskResponseDto createTask(final CreateTaskRequest request) {
        validateProjectExists(request.getProjectId());
        final Task task = Task.builder()
                .id(UUID.randomUUID().toString())
                .title(request.getTitle())
                .description(request.getDescription())
                .projectId(request.getProjectId())
                .assigneeId(request.getAssigneeId())
                .status("OPEN")
                .priority(request.getPriority())
                .createdAt(Instant.now())
                .updatedAt(Instant.now())
                .build();
        final Task saved = taskRepository.save(task);
        log.info("Created task id={} for project={}", saved.getId(), saved.getProjectId());
        return taskMapper.toDto(saved);
    }

    @Transactional
    public TaskResponseDto updateTask(final String taskId, final UpdateTaskRequest request) {
        final Task existing = taskRepository.findById(taskId)
                .orElseThrow(() -> new ResourceNotFoundException("Task not found: " + taskId));
        existing.setTitle(request.getTitle() != null ? request.getTitle() : existing.getTitle());
        existing.setDescription(request.getDescription() != null ? request.getDescription() : existing.getDescription());
        existing.setStatus(request.getStatus() != null ? request.getStatus() : existing.getStatus());
        existing.setPriority(request.getPriority() != null ? request.getPriority() : existing.getPriority());
        existing.setAssigneeId(request.getAssigneeId() != null ? request.getAssigneeId() : existing.getAssigneeId());
        existing.setUpdatedAt(Instant.now());
        final Task updated = taskRepository.save(existing);
        log.info("Updated task id={}", updated.getId());
        return taskMapper.toDto(updated);
    }

    @Transactional
    public void deleteTask(final String taskId) {
        if (!taskRepository.existsById(taskId)) {
            throw new ResourceNotFoundException("Task not found: " + taskId);
        }
        taskRepository.deleteById(taskId);
        log.info("Deleted task id={}", taskId);
    }

    @Transactional(readOnly = true)
    public TaskResponseDto getTaskById(final String taskId) {
        final Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new ResourceNotFoundException("Task not found: " + taskId));
        return taskMapper.toDto(task);
    }

    @Transactional(readOnly = true)
    public List<TaskResponseDto> getTasksByProject(final String projectId) {
        return taskRepository.findByProjectId(projectId).stream()
                .map(taskMapper::toDto)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<TaskResponseDto> getTasksWithFilter(final String projectId, final Map<String, String> filters) {
        return taskRepository.findTasksWithCustomFilter(projectId, filters).stream()
                .map(taskMapper::toDto)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<TaskResponseDto> getAllTasks() {
        return taskRepository.findAll().stream()
                .map(taskMapper::toDto)
                .collect(Collectors.toList());
    }

    private void validateProjectExists(final String projectId) {
        try {
            restTemplate.getForEntity(PROJECT_SERVICE_URL + "/" + projectId, Void.class);
        } catch (HttpClientErrorException.NotFound e) {
            throw new BadRequestException("Project does not exist: " + projectId);
        }
    }
}
