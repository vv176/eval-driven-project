package com.clouddesk.project.controller;

import com.clouddesk.project.dto.CreateProjectRequest;
import com.clouddesk.project.dto.UpdateProjectRequest;
import com.clouddesk.project.dto.ProjectResponseDto;
import com.clouddesk.project.service.ProjectService;
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
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/v1/projects")
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectService projectService;

    @GetMapping
    public ResponseEntity<List<ProjectResponseDto>> listProjects(
            @RequestHeader("X-User-Id") final String userId,
            @RequestHeader("X-Region") final String region) {
        log.info("Listing projects for userId={} in region={}", userId, region);
        final List<ProjectResponseDto> projects = projectService.getProjectsForUser(userId, region);
        return ResponseEntity.ok(projects);
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProjectResponseDto> getProject(
            @PathVariable("id") final String projectId,
            @RequestHeader("X-User-Id") final String userId) {
        log.info("Fetching project={} for userId={}", projectId, userId);
        final ProjectResponseDto project = projectService.getProjectById(projectId);
        return ResponseEntity.ok(project);
    }

    @PostMapping
    public ResponseEntity<ProjectResponseDto> createProject(
            @Valid @RequestBody final CreateProjectRequest request,
            @RequestHeader("X-User-Id") final String userId) {
        log.info("Creating project for userId={} in workspace={}", userId, request.getWorkspaceId());
        final ProjectResponseDto created = projectService.createProject(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<ProjectResponseDto> updateProject(
            @PathVariable("id") final String projectId,
            @Valid @RequestBody final UpdateProjectRequest request,
            @RequestHeader("X-User-Id") final String userId) {
        log.info("Updating project={} for userId={}", projectId, userId);
        final ProjectResponseDto updated = projectService.updateProject(projectId, request);
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteProject(
            @PathVariable("id") final String projectId,
            @RequestHeader("X-User-Id") final String userId) {
        log.info("Deleting project={} for userId={}", projectId, userId);
        projectService.deleteProject(projectId);
        return ResponseEntity.noContent().build();
    }
}
