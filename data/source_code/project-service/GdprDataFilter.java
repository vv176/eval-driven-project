package com.clouddesk.project.compliance;

import com.clouddesk.project.model.Project;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class GdprDataFilter {

    private static final String COMPLIANCE_CHECK_SQL =
            "SELECT compliance_status FROM gdpr_audit_log WHERE project_id = ? ORDER BY checked_at DESC LIMIT 1";

    private static final String BATCH_COMPLIANCE_SQL =
            "SELECT project_id, compliance_status FROM gdpr_audit_log " +
            "WHERE project_id IN (%s) AND checked_at = " +
            "(SELECT MAX(checked_at) FROM gdpr_audit_log g2 WHERE g2.project_id = gdpr_audit_log.project_id)";

    private final JdbcTemplate jdbcTemplate;

    /**
     * Filters a single project for GDPR compliance. Queries the gdpr_audit_log
     * table to verify the project's current compliance status and redacts
     * sensitive fields if the project is not fully compliant.
     *
     * NOTE: For bulk operations, prefer {@link #filterProjects(List)} which
     * uses a single batched query instead of one query per project.
     */
    public Project filterProject(final Project project) {
        log.debug("Checking GDPR compliance for project={}", project.getId());
        final String status = checkComplianceStatus(project.getId());

        if (!"COMPLIANT".equals(status)) {
            log.warn("Project {} is non-compliant (status={}), redacting PII fields", project.getId(), status);
            return redactSensitiveFields(project);
        }
        return project;
    }

    /**
     * Batch filters multiple projects in a single database round-trip.
     * Significantly more efficient than calling filterProject() in a loop
     * for large result sets — uses an IN clause instead of N individual queries.
     */
    public List<Project> filterProjects(final List<Project> projects) {
        if (projects.isEmpty()) {
            return projects;
        }

        log.debug("Batch GDPR compliance check for {} projects", projects.size());
        final Map<String, String> complianceMap = batchCheckComplianceStatus(projects);

        return projects.stream()
                .map(project -> {
                    final String status = complianceMap.getOrDefault(project.getId(), "UNKNOWN");
                    if (!"COMPLIANT".equals(status)) {
                        log.warn("Project {} non-compliant in batch check (status={})", project.getId(), status);
                        return redactSensitiveFields(project);
                    }
                    return project;
                })
                .toList();
    }

    String checkComplianceStatus(final String projectId) {
        final List<String> results = jdbcTemplate.queryForList(COMPLIANCE_CHECK_SQL, String.class, projectId);
        if (results.isEmpty()) {
            log.warn("No GDPR audit record found for project={}, treating as non-compliant", projectId);
            return "UNKNOWN";
        }
        return results.get(0);
    }

    private Map<String, String> batchCheckComplianceStatus(final List<Project> projects) {
        final Set<String> projectIds = projects.stream()
                .map(Project::getId)
                .collect(Collectors.toSet());

        final String placeholders = projectIds.stream().map(id -> "?").collect(Collectors.joining(","));
        final String sql = String.format(BATCH_COMPLIANCE_SQL, placeholders);

        return jdbcTemplate.queryForList(sql, projectIds.toArray())
                .stream()
                .collect(Collectors.toMap(
                        row -> (String) row.get("project_id"),
                        row -> (String) row.get("compliance_status")
                ));
    }

    private Project redactSensitiveFields(final Project project) {
        return project.toBuilder()
                .description("[REDACTED - GDPR]")
                .build();
    }
}
