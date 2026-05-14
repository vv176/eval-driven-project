package com.clouddesk.project.repository;

import com.clouddesk.project.model.Project;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public interface ProjectRepository extends JpaRepository<Project, String> {

    List<Project> findByOwnerIdOrderByUpdatedAtDesc(String ownerId);

    List<Project> findByWorkspaceIdAndStatus(String workspaceId, String status);

    List<Project> findByWorkspaceId(String workspaceId);

    Optional<Project> findByIdAndOwnerId(String id, String ownerId);

    long countByWorkspaceId(String workspaceId);

    long countByWorkspaceIdAndStatus(String workspaceId, String status);

    @Query("SELECT p FROM Project p WHERE p.workspaceId = :workspaceId " +
           "AND p.status = 'ACTIVE' ORDER BY p.updatedAt DESC")
    List<Project> findActiveByWorkspaceId(@Param("workspaceId") String workspaceId);

    @Query("SELECT p FROM Project p WHERE p.ownerId = :ownerId " +
           "AND p.updatedAt > :since ORDER BY p.updatedAt DESC")
    List<Project> findRecentlyUpdatedByOwnerId(
            @Param("ownerId") String ownerId,
            @Param("since") Instant since);

    @Query("SELECT p FROM Project p WHERE p.workspaceId = :workspaceId " +
           "AND p.name LIKE %:searchTerm% AND p.status = 'ACTIVE'")
    List<Project> searchByName(
            @Param("workspaceId") String workspaceId,
            @Param("searchTerm") String searchTerm);

    @Query(value = "SELECT p.* FROM projects p " +
           "INNER JOIN workspace_members wm ON p.workspace_id = wm.workspace_id " +
           "WHERE wm.user_id = :userId AND p.status = 'ACTIVE' " +
           "ORDER BY p.updated_at DESC LIMIT :limit",
           nativeQuery = true)
    List<Project> findAccessibleProjects(
            @Param("userId") String userId,
            @Param("limit") int limit);

    @Query("SELECT DISTINCT p.workspaceId FROM Project p WHERE p.ownerId = :ownerId")
    List<String> findDistinctWorkspaceIdsByOwnerId(@Param("ownerId") String ownerId);
}
