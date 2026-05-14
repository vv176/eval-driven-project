package com.clouddesk.search.service;

import java.util.Map;
import org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.client.indices.CreateIndexRequest;
import org.elasticsearch.client.indices.GetIndexRequest;
import org.elasticsearch.client.indices.PutMappingRequest;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.xcontent.XContentType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class IndexManager {

    private static final Logger log = LoggerFactory.getLogger(IndexManager.class);

    private static final int DEFAULT_SHARDS = 3;
    private static final int DEFAULT_REPLICAS = 2;
    private static final String ANALYSIS_CONFIG = """
            {
              "analyzer": {
                "clouddesk_analyzer": {
                  "type": "custom",
                  "tokenizer": "standard",
                  "filter": ["lowercase", "stop", "snowball"]
                }
              }
            }
            """;

    private final RestHighLevelClient elasticsearchClient;

    public IndexManager(final RestHighLevelClient elasticsearchClient) {
        this.elasticsearchClient = elasticsearchClient;
    }

    public void createIndex(final String indexName, final String mappingJson) {
        try {
            if (indexExists(indexName)) {
                log.info("Index already exists: {}", indexName);
                return;
            }

            final CreateIndexRequest request = new CreateIndexRequest(indexName);
            request.settings(Settings.builder()
                    .put("index.number_of_shards", DEFAULT_SHARDS)
                    .put("index.number_of_replicas", DEFAULT_REPLICAS)
                    .loadFromSource(ANALYSIS_CONFIG, XContentType.JSON));

            if (mappingJson != null) {
                request.mapping(mappingJson, XContentType.JSON);
            }

            elasticsearchClient.indices().create(request, RequestOptions.DEFAULT);
            log.info("Created index: {}", indexName);
        } catch (final Exception e) {
            log.error("Failed to create index={}: {}", indexName, e.getMessage(), e);
            throw new RuntimeException("Index creation failed for " + indexName, e);
        }
    }

    public void deleteIndex(final String indexName) {
        try {
            if (!indexExists(indexName)) {
                log.warn("Cannot delete non-existent index: {}", indexName);
                return;
            }

            final DeleteIndexRequest request = new DeleteIndexRequest(indexName);
            elasticsearchClient.indices().delete(request, RequestOptions.DEFAULT);
            log.info("Deleted index: {}", indexName);
        } catch (final Exception e) {
            log.error("Failed to delete index={}: {}", indexName, e.getMessage(), e);
            throw new RuntimeException("Index deletion failed for " + indexName, e);
        }
    }

    public void updateMapping(final String indexName, final String mappingJson) {
        try {
            final PutMappingRequest request = new PutMappingRequest(indexName);
            request.source(mappingJson, XContentType.JSON);
            elasticsearchClient.indices().putMapping(request, RequestOptions.DEFAULT);
            log.info("Updated mapping for index: {}", indexName);
        } catch (final Exception e) {
            log.error("Failed to update mapping for index={}: {}", indexName, e.getMessage(), e);
            throw new RuntimeException("Mapping update failed for " + indexName, e);
        }
    }

    public boolean indexExists(final String indexName) {
        try {
            final GetIndexRequest request = new GetIndexRequest(indexName);
            return elasticsearchClient.indices().exists(request, RequestOptions.DEFAULT);
        } catch (final Exception e) {
            log.error("Failed to check index existence for {}: {}", indexName, e.getMessage());
            return false;
        }
    }
}
