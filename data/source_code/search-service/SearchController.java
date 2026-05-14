package com.clouddesk.search.controller;

import com.clouddesk.search.dto.SearchResultResponse;
import com.clouddesk.search.service.SearchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/search")
public class SearchController {

    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE = 100;

    private final SearchService searchService;

    public SearchController(final SearchService searchService) {
        this.searchService = searchService;
    }

    @GetMapping
    public ResponseEntity<SearchResultResponse> search(
            @RequestParam("q") final String query,
            @RequestParam(value = "type", required = false) final String type,
            @RequestParam(value = "workspace_id") final String workspaceId,
            @RequestParam(value = "page", defaultValue = "0") final int page,
            @RequestParam(value = "size", defaultValue = "20") final int size,
            @RequestHeader("X-Customer-Id") final String customerId) {

        log.info("Search request: query='{}', type={}, workspaceId={}, customerId={}",
                query, type, workspaceId, customerId);

        if (query == null || query.isBlank()) {
            return ResponseEntity.badRequest().build();
        }

        final int pageSize = Math.min(size, MAX_PAGE_SIZE);

        final SearchResultResponse results = searchService.search(
                query, type, workspaceId, customerId, page, pageSize
        );

        log.info("Search completed: totalHits={}, returned={}", results.getTotalHits(), results.getItems().size());
        return ResponseEntity.ok(results);
    }

    @GetMapping("/suggestions")
    public ResponseEntity<SearchResultResponse> suggest(
            @RequestParam("q") final String query,
            @RequestParam(value = "workspace_id") final String workspaceId,
            @RequestHeader("X-Customer-Id") final String customerId) {

        log.info("Suggestion request: query='{}', workspaceId={}", query, workspaceId);

        final SearchResultResponse results = searchService.suggest(query, workspaceId, customerId);
        return ResponseEntity.ok(results);
    }
}
