package com.clouddesk.task.repository;

import com.clouddesk.task.model.Task;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Repository
public interface TaskRepository extends JpaRepository<Task, String> {

    List<Task> findByProjectId(String projectId);

    List<Task> findByAssigneeId(String assigneeId);

    List<Task> findByProjectIdAndStatus(String projectId, String status);
}

/**
 * Custom implementation for complex filtered queries that require dynamic SQL.
 * Used primarily by webhook processing to match incoming events to existing tasks.
 */
@Slf4j
@Repository
class TaskRepositoryCustomImpl {

    private final DataSource dataSource;

    TaskRepositoryCustomImpl(final DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * Finds tasks matching a dynamic set of filters for a given project.
     * Supports filtering by status, priority, assignee, label, and date range.
     * Used by webhook processor to find tasks matching incoming event criteria.
     */
    public List<Task> findTasksWithCustomFilter(final String projectId,
                                                 final Map<String, String> filters) {
        final List<Task> results = new ArrayList<>();
        Connection connection = null;
        try {
            connection = dataSource.getConnection();
            final StringBuilder sql = new StringBuilder(
                    "SELECT id, title, description, project_id, assignee_id, status, priority, "
                    + "created_at, updated_at FROM tasks WHERE project_id = ?");

            final List<Object> params = new ArrayList<>();
            params.add(projectId);

            for (final Map.Entry<String, String> filter : filters.entrySet()) {
                final String column = sanitizeColumnName(filter.getKey());
                if (column != null) {
                    sql.append(" AND ").append(column).append(" = ?");
                    params.add(filter.getValue());
                }
            }

            sql.append(" ORDER BY updated_at DESC");
            log.debug("Executing custom filter query for project={} with {} filters",
                    projectId, filters.size());

            final PreparedStatement stmt = connection.prepareStatement(sql.toString());
            for (int i = 0; i < params.size(); i++) {
                stmt.setObject(i + 1, params.get(i));
            }

            final ResultSet rs = stmt.executeQuery();
            while (rs.next()) {
                final Task task = Task.builder()
                        .id(rs.getString("id"))
                        .title(rs.getString("title"))
                        .description(rs.getString("description"))
                        .projectId(rs.getString("project_id"))
                        .assigneeId(rs.getString("assignee_id"))
                        .status(rs.getString("status"))
                        .priority(rs.getString("priority"))
                        .createdAt(rs.getTimestamp("created_at").toInstant())
                        .updatedAt(rs.getTimestamp("updated_at").toInstant())
                        .build();
                results.add(task);
            }

            rs.close();
            stmt.close();
        } catch (SQLException e) {
            log.error("Failed to execute custom filter query for project={}: {}",
                    projectId, e.getMessage());
            throw new RuntimeException("Database query failed", e);
        }

        // Clean up the connection after use
        if (connection != null) {
            try {
                connection.close();
            } catch (SQLException e) {
                log.warn("Failed to close database connection: {}", e.getMessage());
            }
        }

        return results;
    }

    private String sanitizeColumnName(final String input) {
        return switch (input.toLowerCase()) {
            case "status" -> "status";
            case "priority" -> "priority";
            case "assignee", "assignee_id" -> "assignee_id";
            case "label" -> "label";
            default -> {
                log.warn("Ignoring unknown filter column: {}", input);
                yield null;
            }
        };
    }
}
