package com.clouddesk.task.controller;

import com.clouddesk.task.dto.CreateTaskRequest;
import com.clouddesk.task.dto.UpdateTaskRequest;
import com.clouddesk.task.dto.TaskResponseDto;
import com.clouddesk.task.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskService taskService;

    @GetMapping
    public ResponseEntity<List<TaskResponseDto>> getTasks(
            @RequestParam(required = false) final String projectId,
            @RequestParam(required = false) final Map<String, String> filters) {
        log.info("Fetching tasks for projectId={}", projectId);
        if (projectId != null && filters != null && !filters.isEmpty()) {
            final List<TaskResponseDto> tasks = taskService.getTasksWithFilter(projectId, filters);
            return ResponseEntity.ok(tasks);
        }
        if (projectId != null) {
            final List<TaskResponseDto> tasks = taskService.getTasksByProject(projectId);
            return ResponseEntity.ok(tasks);
        }
        final List<TaskResponseDto> tasks = taskService.getAllTasks();
        return ResponseEntity.ok(tasks);
    }

    @GetMapping("/{taskId}")
    public ResponseEntity<TaskResponseDto> getTask(@PathVariable final String taskId) {
        log.info("Fetching task with id={}", taskId);
        final TaskResponseDto task = taskService.getTaskById(taskId);
        return ResponseEntity.ok(task);
    }

    @PostMapping
    public ResponseEntity<TaskResponseDto> createTask(
            @Valid @RequestBody final CreateTaskRequest request) {
        log.info("Creating task for projectId={}", request.getProjectId());
        final TaskResponseDto created = taskService.createTask(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/{taskId}")
    public ResponseEntity<TaskResponseDto> updateTask(
            @PathVariable final String taskId,
            @Valid @RequestBody final UpdateTaskRequest request) {
        log.info("Updating task id={}", taskId);
        final TaskResponseDto updated = taskService.updateTask(taskId, request);
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping("/{taskId}")
    public ResponseEntity<Void> deleteTask(@PathVariable final String taskId) {
        log.info("Deleting task id={}", taskId);
        taskService.deleteTask(taskId);
        return ResponseEntity.noContent().build();
    }
}
