package com.clouddesk.search.service;

import com.clouddesk.search.dto.SearchResultItem;
import com.clouddesk.search.dto.SearchResultResponse;
import java.util.List;
import java.util.Map;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class SearchService {

    private static final Logger log = LoggerFactory.getLogger(SearchService.class);

    private static final String INDEX_PROJECTS = "clouddesk-projects";
    private static final String INDEX_TASKS = "clouddesk-tasks";
    private static final String INDEX_DOCUMENTS = "clouddesk-documents";
    private static final int SUGGESTION_LIMIT = 5;

    private static final Map<String, String> TYPE_INDEX_MAP = Map.of(
            "project", INDEX_PROJECTS,
            "task", INDEX_TASKS,
            "document", INDEX_DOCUMENTS
    );

    private final RestHighLevelClient elasticsearchClient;

    public SearchService(final RestHighLevelClient elasticsearchClient) {
        this.elasticsearchClient = elasticsearchClient;
    }

    public SearchResultResponse search(final String query, final String type,
                                       final String workspaceId, final String customerId,
                                       final int page, final int pageSize) {
        try {
            final String[] indices = resolveIndices(type);
            final BoolQueryBuilder boolQuery = buildSearchQuery(query, workspaceId, customerId);

            final SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
                    .query(boolQuery)
                    .from(page * pageSize)
                    .size(pageSize);

            final SearchRequest searchRequest = new SearchRequest(indices);
            searchRequest.source(sourceBuilder);

            final SearchResponse response = elasticsearchClient.search(searchRequest, RequestOptions.DEFAULT);
            return mapResponse(response);
        } catch (final Exception e) {
            log.error("Search failed: query='{}', error={}", query, e.getMessage(), e);
            throw new RuntimeException("Search operation failed", e);
        }
    }

    public SearchResultResponse suggest(final String query, final String workspaceId, final String customerId) {
        try {
            final String[] indices = { INDEX_PROJECTS, INDEX_TASKS, INDEX_DOCUMENTS };
            final BoolQueryBuilder boolQuery = buildSearchQuery(query, workspaceId, customerId);

            final SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
                    .query(boolQuery)
                    .from(0)
                    .size(SUGGESTION_LIMIT);

            final SearchRequest searchRequest = new SearchRequest(indices);
            searchRequest.source(sourceBuilder);

            final SearchResponse response = elasticsearchClient.search(searchRequest, RequestOptions.DEFAULT);
            return mapResponse(response);
        } catch (final Exception e) {
            log.error("Suggestion query failed: query='{}', error={}", query, e.getMessage(), e);
            throw new RuntimeException("Suggestion operation failed", e);
        }
    }

    private String[] resolveIndices(final String type) {
        if (type != null && TYPE_INDEX_MAP.containsKey(type.toLowerCase())) {
            return new String[]{ TYPE_INDEX_MAP.get(type.toLowerCase()) };
        }
        return new String[]{ INDEX_PROJECTS, INDEX_TASKS, INDEX_DOCUMENTS };
    }

    private BoolQueryBuilder buildSearchQuery(final String query, final String workspaceId, final String customerId) {
        return QueryBuilders.boolQuery()
                .must(QueryBuilders.multiMatchQuery(query, "title", "description", "content")
                        .fuzziness("AUTO"))
                .filter(QueryBuilders.termQuery("workspace_id", workspaceId))
                .filter(QueryBuilders.termQuery("customer_id", customerId));
    }

    private SearchResultResponse mapResponse(final SearchResponse response) {
        final List<SearchResultItem> items = java.util.Arrays.stream(response.getHits().getHits())
                .map(this::mapHit)
                .toList();

        final long totalHits = response.getHits().getTotalHits().value;
        return new SearchResultResponse(items, totalHits);
    }

    private SearchResultItem mapHit(final SearchHit hit) {
        final Map<String, Object> source = hit.getSourceAsMap();
        return new SearchResultItem(
                hit.getId(),
                hit.getIndex(),
                (String) source.getOrDefault("title", ""),
                (String) source.getOrDefault("description", ""),
                hit.getScore()
        );
    }
}
