package com.clouddesk.gateway;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
@ConfigurationProperties(prefix = "clouddesk.gateway")
public class GatewayConfig {

    private String projectServiceUrl = "http://project-service:8081";
    private String taskServiceUrl = "http://task-service:8082";
    private String searchServiceUrl = "http://search-service:8083";
    private String authServiceUrl = "http://auth-service:8084";

    private int connectionTimeoutMs = 3000;
    private int readTimeoutMs = 5000;
    private int maxRetries = 3;
    private int retryBackoffMs = 500;

    private int circuitBreakerFailureThreshold = 5;
    private int circuitBreakerResetTimeoutMs = 30000;
    private int circuitBreakerHalfOpenRequests = 3;

    @Bean
    public RestTemplate gatewayRestTemplate() {
        return new RestTemplate();
    }

    public String getProjectServiceUrl() { return projectServiceUrl; }
    public void setProjectServiceUrl(final String url) { this.projectServiceUrl = url; }

    public String getTaskServiceUrl() { return taskServiceUrl; }
    public void setTaskServiceUrl(final String url) { this.taskServiceUrl = url; }

    public String getSearchServiceUrl() { return searchServiceUrl; }
    public void setSearchServiceUrl(final String url) { this.searchServiceUrl = url; }

    public String getAuthServiceUrl() { return authServiceUrl; }
    public void setAuthServiceUrl(final String url) { this.authServiceUrl = url; }

    public int getConnectionTimeoutMs() { return connectionTimeoutMs; }
    public void setConnectionTimeoutMs(final int ms) { this.connectionTimeoutMs = ms; }

    public int getReadTimeoutMs() { return readTimeoutMs; }
    public void setReadTimeoutMs(final int ms) { this.readTimeoutMs = ms; }

    public int getMaxRetries() { return maxRetries; }
    public void setMaxRetries(final int retries) { this.maxRetries = retries; }

    public int getRetryBackoffMs() { return retryBackoffMs; }
    public void setRetryBackoffMs(final int ms) { this.retryBackoffMs = ms; }

    public int getCircuitBreakerFailureThreshold() { return circuitBreakerFailureThreshold; }
    public void setCircuitBreakerFailureThreshold(final int t) { this.circuitBreakerFailureThreshold = t; }

    public int getCircuitBreakerResetTimeoutMs() { return circuitBreakerResetTimeoutMs; }
    public void setCircuitBreakerResetTimeoutMs(final int ms) { this.circuitBreakerResetTimeoutMs = ms; }

    public int getCircuitBreakerHalfOpenRequests() { return circuitBreakerHalfOpenRequests; }
    public void setCircuitBreakerHalfOpenRequests(final int n) { this.circuitBreakerHalfOpenRequests = n; }
}
