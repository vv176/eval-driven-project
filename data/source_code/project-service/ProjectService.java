package com.clouddesk.project.service;

import com.clouddesk.project.compliance.GdprDataFilter;
import com.clouddesk.project.dto.CreateProjectRequest;
import com.clouddesk.project.dto.ProjectResponseDto;
import com.clouddesk.project.dto.UpdateProjectRequest;
import com.clouddesk.project.exception.ResourceNotFoundException;
import com.clouddesk.project.mapper.ProjectMapper;
import com.clouddesk.project.model.Project;
import com.clouddesk.project.repository.ProjectRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProjectService {

    private static final Set<String> EU_REGIONS = Set.of("eu-west-1", "eu-north-1");
    private static final int MAX_PROJECTS_PER_WORKSPACE = 500;

    private final ProjectRepository projectRepository;
    private final GdprDataFilter gdprDataFilter;
    private final ProjectMapper projectMapper;

    @Transactional(readOnly = true)
    public List<ProjectResponseDto> getProjectsForUser(final String userId, final String region) {
        log.info("Fetching projects for userId={} region={}", userId, region);

        final List<Project> projects = projectRepository.findByOwnerIdOrderByUpdatedAtDesc(userId);

        if (projects.isEmpty()) {
            return List.of();
        }

        log.debug("Found {} projects for userId={}, checking region compliance", projects.size(), userId);

        // Apply GDPR filtering for EU regions
        if (EU_REGIONS.contains(region)) {
            log.debug("EU region detected ({}), applying GDPR data filtering", region);
            final List<ProjectResponseDto> filteredResults = new ArrayList<>();
            for (final Project project : projects) {
                final Project filtered = gdprDataFilter.filterProject(project);
                filteredResults.add(projectMapper.toResponseDto(filtered));
            }
            return filteredResults;
        }

        return projects.stream()
                .map(projectMapper::toResponseDto)
                .toList();
    }

    @Transactional(readOnly = true)
    public ProjectResponseDto getProjectById(final String projectId) {
        final Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new ResourceNotFoundException("Project", projectId));
        return projectMapper.toResponseDto(project);
    }

    @Transactional
    public ProjectResponseDto createProject(final CreateProjectRequest request) {
        final long existingCount = projectRepository.countByWorkspaceId(request.getWorkspaceId());
        if (existingCount >= MAX_PROJECTS_PER_WORKSPACE) {
            throw new IllegalStateException(
                    "Workspace " + request.getWorkspaceId() + " has reached the maximum project limit");
        }

        final Project project = Project.builder()
                .id(UUID.randomUUID().toString())
                .name(request.getName())
                .description(request.getDescription())
                .workspaceId(request.getWorkspaceId())
                .ownerId(request.getOwnerId())
                .status("ACTIVE")
                .createdAt(Instant.now())
                .updatedAt(Instant.now())
                .build();

        final Project saved = projectRepository.save(project);
        log.info("Created project={} in workspace={}", saved.getId(), saved.getWorkspaceId());
        return projectMapper.toResponseDto(saved);
    }

    @Transactional
    public ProjectResponseDto updateProject(final String projectId, final UpdateProjectRequest request) {
        final Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new ResourceNotFoundException("Project", projectId));

        project.setName(request.getName());
        project.setDescription(request.getDescription());
        project.setUpdatedAt(Instant.now());

        final Project saved = projectRepository.save(project);
        log.info("Updated project={}", saved.getId());
        return projectMapper.toResponseDto(saved);
    }

    @Transactional
    public void deleteProject(final String projectId) {
        final Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new ResourceNotFoundException("Project", projectId));

        project.setStatus("DELETED");
        project.setUpdatedAt(Instant.now());
        projectRepository.save(project);
        log.info("Soft-deleted project={}", projectId);
    }
}
